"""
BaseLayer Ollama Client

Async Ollama client with fallback chain, retry logic,
and token usage tracking for GPU/CPU environments.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


@dataclass
class OllamaModel:
    """Ollama model information."""
    name: str
    size: str
    digest: str
    modified_at: str
    family: str
    parameter_size: str
    quantization_level: str
    format: str
    
    
@dataclass
class OllamaResponse:
    """Ollama API response wrapper."""
    model: str
    created_at: int
    done: bool
    done_reason: Optional[str]
    total_duration: Optional[int]
    load_duration: Optional[int]
    prompt_eval_count: Optional[int]
    prompt_eval_duration: Optional[int]
    eval_count: Optional[int]
    eval_duration: Optional[int]
    response: str
    context: Optional[List[int]]
    token_usage: Dict[str, int]


@dataclass
class OllamaChatMessage:
    """Chat message for Ollama chat API."""
    role: str
    content: str
    
    
@dataclass
class OllamaChatOptions:
    """Options for Ollama chat generation."""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    seed: Optional[int] = None
    num_predict: int = -1  # -1 for unlimited
    num_ctx: int = 2048
    stop: Optional[List[str]] = None
    stream: bool = False


class OllamaClient:
    """
    Async Ollama client with automatic fallback and retry.
    
    Handles GPU/CPU model selection, connection issues,
    and provides typed interfaces for all Ollama operations.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        max_retries: int = 3,
        fallback_chain: Optional[List[str]] = None
    ) -> None:
        """Initialize Ollama client."""
        self.base_url: str = base_url.rstrip('/')
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        
        # Model fallback chain: larger -> smaller models
        self.fallback_chain: List[str] = fallback_chain or [
            "llama2:70b",      # GPU only
            "llama2:34b",      # GPU only  
            "llama2:13b",      # GPU/CPU
            "llama2:7b",       # GPU/CPU
            "llama2:3b",       # CPU only
            "qwen:7b",         # CPU fallback
            "phi:3b"           # Smallest CPU model
        ]
        
        # HTTP client configuration
        self.client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5)
        )
        
        # Available models cache
        self._available_models: Optional[List[OllamaModel]] = None
        self._models_cache_time: Optional[float] = None
        
        # Token usage tracking
        self.token_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        logger.info(
            "Ollama client initialized",
            base_url=self.base_url,
            timeout=timeout,
            fallback_chain=self.fallback_chain
        )
    
    async def health_check(self) -> bool:
        """
        Check if Ollama server is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(
                "Ollama health check failed",
                base_url=self.base_url,
                error=str(e)
            )
            return False
    
    async def list_models(self) -> List[OllamaModel]:
        """
        List available models.
        
        Returns:
            List of available Ollama models
        """
        # Check cache
        current_time = time.time()
        if (
            self._available_models is not None and
            self._models_cache_time is not None and
            (current_time - self._models_cache_time) < 300  # 5 minute cache
        ):
            return self._available_models
        
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                model = OllamaModel(
                    name=model_data.get("name", ""),
                    size=model_data.get("size", ""),
                    digest=model_data.get("digest", ""),
                    modified_at=model_data.get("modified_at", ""),
                    family=model_data.get("details", {}).get("family", ""),
                    parameter_size=model_data.get("details", {}).get("parameter_size", ""),
                    quantization_level=model_data.get("details", {}).get("quantization_level", ""),
                    format=model_data.get("details", {}).get("format", "")
                )
                models.append(model)
            
            self._available_models = models
            self._models_cache_time = current_time
            
            logger.info(
                "Models listed successfully",
                count=len(models),
                models=[m.name for m in models]
            )
            
            return models
            
        except Exception as e:
            logger.error(
                "Failed to list models",
                error=str(e)
            )
            return []
    
    async def model_info(self, model_name: str) -> Optional[OllamaModel]:
        """
        Get information about a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model information or None if not found
        """
        models = await self.list_models()
        
        for model in models:
            if model.name == model_name:
                return model
        
        return None
    
    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.
        
        Args:
            model_name: Name of the model to pull
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                "Starting model pull",
                model=model_name
            )
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            ) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        try:
                            data = json.loads(chunk)
                            status = data.get("status", "")
                            logger.debug(
                                "Model pull progress",
                                model=model_name,
                                status=status
                            )
                        except json.JSONDecodeError:
                            continue
            
            logger.info(
                "Model pull completed",
                model=model_name
            )
            
            # Clear model cache
            self._available_models = None
            self._models_cache_time = None
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to pull model",
                model=model_name,
                error=str(e)
            )
            return False
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[OllamaChatOptions] = None,
        system: Optional[str] = None
    ) -> OllamaResponse:
        """
        Generate text completion.
        
        Args:
            prompt: Input prompt
            model: Model to use (will fallback if None)
            options: Generation options
            system: System message
            
        Returns:
            Generated response with metadata
        """
        # Select model
        selected_model = await self._select_model(model)
        
        # Prepare request
        request_data = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False
        }
        
        if options:
            request_data["options"] = {
                "temperature": options.temperature,
                "top_p": options.top_p,
                "top_k": options.top_k,
                "repeat_penalty": options.repeat_penalty,
                "num_predict": options.num_predict,
                "num_ctx": options.num_ctx
            }
            
            if options.seed is not None:
                request_data["options"]["seed"] = options.seed
            
            if options.stop:
                request_data["options"]["stop"] = options.stop
        
        if system:
            request_data["system"] = system
        
        # Execute with retry
        return await self._execute_with_retry(
            "POST",
            f"{self.base_url}/api/generate",
            request_data,
            selected_model
        )
    
    async def chat(
        self,
        messages: List[OllamaChatMessage],
        model: Optional[str] = None,
        options: Optional[OllamaChatOptions] = None
    ) -> OllamaResponse:
        """
        Generate chat completion.
        
        Args:
            messages: List of chat messages
            model: Model to use (will fallback if None)
            options: Generation options
            
        Returns:
            Generated response with metadata
        """
        # Select model
        selected_model = await self._select_model(model)
        
        # Prepare request
        request_data = {
            "model": selected_model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "stream": False
        }
        
        if options:
            request_data["options"] = {
                "temperature": options.temperature,
                "top_p": options.top_p,
                "top_k": options.top_k,
                "repeat_penalty": options.repeat_penalty,
                "num_predict": options.num_predict,
                "num_ctx": options.num_ctx
            }
            
            if options.seed is not None:
                request_data["options"]["seed"] = options.seed
            
            if options.stop:
                request_data["options"]["stop"] = options.stop
        
        # Execute with retry
        return await self._execute_with_retry(
            "POST",
            f"{self.base_url}/api/chat",
            request_data,
            selected_model
        )
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[OllamaChatOptions] = None,
        system: Optional[str] = None
    ):
        """
        Stream text completion.
        
        Args:
            prompt: Input prompt
            model: Model to use (will fallback if None)
            options: Generation options
            system: System message
            
        Yields:
            Partial response chunks
        """
        # Select model
        selected_model = await self._select_model(model)
        
        # Prepare request
        request_data = {
            "model": selected_model,
            "prompt": prompt,
            "stream": True
        }
        
        if options:
            request_data["options"] = {
                "temperature": options.temperature,
                "top_p": options.top_p,
                "top_k": options.top_k,
                "repeat_penalty": options.repeat_penalty,
                "num_predict": options.num_predict,
                "num_ctx": options.num_ctx
            }
            
            if options.seed is not None:
                request_data["options"]["seed"] = options.seed
            
            if options.stop:
                request_data["options"]["stop"] = options.stop
        
        if system:
            request_data["system"] = system
        
        # Stream with retry
        async for chunk in self._stream_with_retry(
            "POST",
            f"{self.base_url}/api/generate",
            request_data,
            selected_model
        ):
            yield chunk
    
    async def stream_chat(
        self,
        messages: List[OllamaChatMessage],
        model: Optional[str] = None,
        options: Optional[OllamaChatOptions] = None
    ):
        """
        Stream chat completion.
        
        Args:
            messages: List of chat messages
            model: Model to use (will fallback if None)
            options: Generation options
            
        Yields:
            Partial response chunks
        """
        # Select model
        selected_model = await self._select_model(model)
        
        # Prepare request
        request_data = {
            "model": selected_model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "stream": True
        }
        
        if options:
            request_data["options"] = {
                "temperature": options.temperature,
                "top_p": options.top_p,
                "top_k": options.top_k,
                "repeat_penalty": options.repeat_penalty,
                "num_predict": options.num_predict,
                "num_ctx": options.num_ctx
            }
            
            if options.seed is not None:
                request_data["options"]["seed"] = options.seed
            
            if options.stop:
                request_data["options"]["stop"] = options.stop
        
        # Stream with retry
        async for chunk in self._stream_with_retry(
            "POST",
            f"{self.base_url}/api/chat",
            request_data,
            selected_model
        ):
            yield chunk
    
    async def _select_model(self, preferred_model: Optional[str]) -> str:
        """
        Select best available model with fallback chain.
        
        Args:
            preferred_model: Preferred model name
            
        Returns:
            Selected model name
        """
        models = await self.list_models()
        available_names = [model.name for model in models]
        
        # If preferred model is available, use it
        if preferred_model and preferred_model in available_names:
            return preferred_model
        
        # Try fallback chain
        for candidate in self.fallback_chain:
            if candidate in available_names:
                logger.info(
                    "Using fallback model",
                    preferred=preferred_model,
                    selected=candidate
                )
                return candidate
        
        # No models available
        raise BaseLayerError(
            f"No models available. Preferred: {preferred_model}, "
            f"available: {available_names}"
        )
    
    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        data: Dict[str, Any],
        model: str
    ) -> OllamaResponse:
        """
        Execute request with retry logic.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            model: Model being used
            
        Returns:
            Ollama response
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, json=data)
                response.raise_for_status()
                
                result_data = response.json()
                
                # Parse response
                ollama_response = OllamaResponse(
                    model=result_data.get("model", model),
                    created_at=result_data.get("created_at", 0),
                    done=result_data.get("done", True),
                    done_reason=result_data.get("done_reason"),
                    total_duration=result_data.get("total_duration"),
                    load_duration=result_data.get("load_duration"),
                    prompt_eval_count=result_data.get("prompt_eval_count"),
                    prompt_eval_duration=result_data.get("prompt_eval_duration"),
                    eval_count=result_data.get("eval_count"),
                    eval_duration=result_data.get("eval_duration"),
                    response=result_data.get("response", ""),
                    context=result_data.get("context"),
                    token_usage=self._extract_token_usage(result_data)
                )
                
                # Update token usage
                self._update_token_usage(ollama_response.token_usage)
                
                if attempt > 0:
                    logger.info(
                        "Request succeeded after retry",
                        model=model,
                        attempt=attempt + 1,
                        total_attempts=self.max_retries + 1
                    )
                
                return ollama_response
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    
                    logger.warning(
                        "Request failed, retrying",
                        model=model,
                        attempt=attempt + 1,
                        total_attempts=self.max_retries + 1,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Request failed after all retries",
                        model=model,
                        total_attempts=self.max_retries + 1,
                        error=str(e)
                    )
        
        raise BaseLayerError(
            f"Request failed after {self.max_retries + 1} attempts: {str(last_error)}"
        ) from last_error
    
    async def _stream_with_retry(
        self,
        method: str,
        url: str,
        data: Dict[str, Any],
        model: str
    ):
        """
        Stream request with retry logic.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            model: Model being used
            
        Yields:
            Response chunks
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.client.stream(method, url, json=data) as response:
                    response.raise_for_status()
                    
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            try:
                                chunk_data = json.loads(chunk)
                                
                                # Convert to response format
                                ollama_response = OllamaResponse(
                                    model=chunk_data.get("model", model),
                                    created_at=chunk_data.get("created_at", 0),
                                    done=chunk_data.get("done", False),
                                    done_reason=chunk_data.get("done_reason"),
                                    total_duration=chunk_data.get("total_duration"),
                                    load_duration=chunk_data.get("load_duration"),
                                    prompt_eval_count=chunk_data.get("prompt_eval_count"),
                                    prompt_eval_duration=chunk_data.get("prompt_eval_duration"),
                                    eval_count=chunk_data.get("eval_count"),
                                    eval_duration=chunk_data.get("eval_duration"),
                                    response=chunk_data.get("response", ""),
                                    context=chunk_data.get("context"),
                                    token_usage=self._extract_token_usage(chunk_data)
                                )
                                
                                yield ollama_response
                                
                            except json.JSONDecodeError:
                                # Yield raw chunk if not valid JSON
                                yield chunk_data.get("response", chunk)
                
                return
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    
                    logger.warning(
                        "Stream request failed, retrying",
                        model=model,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Stream request failed after all retries",
                        model=model,
                        error=str(e)
                    )
        
        raise BaseLayerError(
            f"Stream request failed after {self.max_retries + 1} attempts: {str(last_error)}"
        ) from last_error
    
    def _extract_token_usage(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Extract token usage from response data."""
        return {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": (
                data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            )
        }
    
    def _update_token_usage(self, usage: Dict[str, int]) -> None:
        """Update cumulative token usage."""
        self.token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get current token usage statistics."""
        return self.token_usage.copy()
    
    def reset_token_usage(self) -> None:
        """Reset token usage statistics."""
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        logger.info("Token usage reset")
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
        
        logger.info("Ollama client closed")


# Global client instance
ollama_client = OllamaClient()
