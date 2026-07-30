"""
BaseLayer Ollama Client Tests

Test suite for OllamaClient including model selection,
fallback chain, retry logic, and token usage tracking.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.llm.ollama_client import (
    OllamaClient,
    OllamaModel,
    OllamaResponse,
    OllamaChatMessage,
    OllamaChatOptions
)
from tests.agents.conftest import (
    mock_ollama_client,
    sample_ollama_response,
    LogCapture
)


class TestOllamaClient:
    """Test suite for OllamaClient functionality."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization with default parameters."""
        client = OllamaClient()
        
        assert client.base_url == "http://localhost:11434"
        assert client.timeout == 120
        assert client.max_retries == 3
        assert len(client.fallback_chain) > 0
        assert "llama2:7b" in client.fallback_chain
    
    @pytest.mark.asyncio
    async def test_client_initialization_custom_params(self):
        """Test client initialization with custom parameters."""
        custom_url = "http://custom:11434"
        custom_chain = ["model1", "model2"]
        
        client = OllamaClient(
            base_url=custom_url,
            timeout=60,
            max_retries=5,
            fallback_chain=custom_chain
        )
        
        assert client.base_url == custom_url
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.fallback_chain == custom_chain
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_ollama_client):
        """Test successful health check."""
        mock_ollama_client.client.get.return_value.status_code = 200
        
        result = await mock_ollama_client.health_check()
        
        assert result is True
        mock_ollama_client.client.get.assert_called_once_with(
            f"{mock_ollama_client.base_url}/api/tags"
        )
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_ollama_client):
        """Test health check failure."""
        mock_ollama_client.client.get.side_effect = Exception("Connection error")
        
        result = await mock_ollama_client.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_ollama_client):
        """Test successful model listing."""
        mock_response_data = {
            "models": [
                {
                    "name": "llama2:7b",
                    "size": "7B",
                    "digest": "abc123",
                    "modified_at": "2024-01-01",
                    "details": {
                        "family": "llama2",
                        "parameter_size": "7B",
                        "quantization_level": "Q4_0",
                        "format": "gguf"
                    }
                }
            ]
        }
        
        mock_ollama_client.client.get.return_value.status_code = 200
        mock_ollama_client.client.get.return_value.json.return_value = mock_response_data
        
        models = await mock_ollama_client.list_models()
        
        assert len(models) == 1
        assert models[0].name == "llama2:7b"
        assert models[0].size == "7B"
        assert models[0].family == "llama2"
        assert models[0].parameter_size == "7B"
        assert models[0].quantization_level == "Q4_0"
        assert models[0].format == "gguf"
    
    @pytest.mark.asyncio
    async def test_list_models_caching(self, mock_ollama_client):
        """Test model listing with caching."""
        mock_response_data = {"models": []}
        
        mock_ollama_client.client.get.return_value.status_code = 200
        mock_ollama_client.client.get.return_value.json.return_value = mock_response_data
        
        # First call
        models1 = await mock_ollama_client.list_models()
        
        # Second call should use cache
        models2 = await mock_ollama_client.list_models()
        
        assert models1 == models2
        # Should only call API once due to caching
        assert mock_ollama_client.client.get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_model_info_success(self, mock_ollama_client):
        """Test successful model info retrieval."""
        mock_models = [
            MagicMock(name="llama2:7b", size="7B"),
            MagicMock(name="llama2:13b", size="13B")
        ]
        
        mock_ollama_client._available_models = mock_models
        
        info = await mock_ollama_client.model_info("llama2:7b")
        
        assert info is not None
        assert info.name == "llama2:7b"
        assert info.size == "7B"
    
    @pytest.mark.asyncio
    async def test_model_info_not_found(self, mock_ollama_client):
        """Test model info when model not found."""
        mock_models = [
            MagicMock(name="llama2:7b", size="7B")
        ]
        
        mock_ollama_client._available_models = mock_models
        
        info = await mock_ollama_client.model_info("nonexistent:model")
        
        assert info is None
    
    @pytest.mark.asyncio
    async def test_generate_success(self, mock_ollama_client):
        """Test successful text generation."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        mock_ollama_client._execute_with_retry.return_value = sample_ollama_response()
        
        result = await mock_ollama_client.generate("Test prompt")
        
        assert result.model == "llama2:7b"
        assert result.response == "Test response from mock Ollama"
        assert result.done is True
        assert result.token_usage["prompt_tokens"] == 10
        assert result.token_usage["completion_tokens"] == 15
        
        mock_ollama_client._select_model.assert_called_once()
        mock_ollama_client._execute_with_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_with_options(self, mock_ollama_client):
        """Test text generation with custom options."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        mock_ollama_client._execute_with_retry.return_value = sample_ollama_response()
        
        options = OllamaChatOptions(
            temperature=0.5,
            top_p=0.8,
            max_predict=100
        )
        
        result = await mock_ollama_client.generate(
            "Test prompt",
            model="llama2:7b",
            options=options,
            system="System message"
        )
        
        assert result.model == "llama2:7b"
        mock_ollama_client._execute_with_retry.assert_called_once()
        
        # Check that options were passed correctly
        call_args = mock_ollama_client._execute_with_retry.call_args[0]
        request_data = call_args[2]  # data parameter
        
        assert request_data["model"] == "llama2:7b"
        assert request_data["system"] == "System message"
        assert request_data["options"]["temperature"] == 0.5
        assert request_data["options"]["top_p"] == 0.8
        assert request_data["options"]["num_predict"] == 100
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback(self, mock_ollama_client):
        """Test model selection with fallback chain."""
        # Mock available models
        mock_ollama_client._available_models = [
            MagicMock(name="llama2:7b", size="7B"),
            MagicMock(name="llama2:3b", size="3B")
        ]
        
        # First try preferred model (not available)
        result1 = await mock_ollama_client.generate("Test", model="llama2:13b")
        mock_ollama_client._execute_with_retry.return_value = sample_ollama_response()
        
        # Should fallback to 7b
        assert mock_ollama_client._select_model.call_args[0][0] == "llama2:13b"
        
        # Second try with available model
        result2 = await mock_ollama_client.generate("Test", model="llama2:7b")
        
        # Should use preferred model
        assert mock_ollama_client._select_model.call_args[0][0] == "llama2:7b"
    
    @pytest.mark.asyncio
    async def test_generate_retry_logic(self, mock_ollama_client):
        """Test retry logic on connection errors."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        
        # Fail first 2 attempts, succeed on 3rd
        call_count = 0
        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Attempt {call_count} failed")
            return sample_ollama_response()
        
        mock_ollama_client._execute_with_retry.side_effect = mock_execute
        
        result = await mock_ollama_client.generate("Test")
        
        assert result.response == "Test response from mock Ollama"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_generate_max_retries_exceeded(self, mock_ollama_client):
        """Test behavior when max retries exceeded."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        
        # Always fail
        mock_ollama_client._execute_with_retry.side_effect = Exception("Always fails")
        
        with pytest.raises(Exception):
            await mock_ollama_client.generate("Test")
    
    @pytest.mark.asyncio
    async def test_chat_success(self, mock_ollama_client):
        """Test successful chat completion."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        mock_ollama_client._execute_with_retry.return_value = sample_ollama_response()
        
        messages = [
            OllamaChatMessage(role="user", content="Hello"),
            OllamaChatMessage(role="assistant", content="Hi there!")
        ]
        
        result = await mock_ollama_client.chat(messages)
        
        assert result.model == "llama2:7b"
        assert result.response == "Test response from mock Ollama"
        assert result.done is True
        
        mock_ollama_client._execute_with_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stream_generate(self, mock_ollama_client):
        """Test streaming text generation."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        
        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            for i in range(3):
                yield OllamaResponse(
                    model="llama2:7b",
                    response=f"chunk_{i}",
                    done=(i == 2)
                )
        
        mock_ollama_client._stream_with_retry.side_effect = mock_stream
        
        chunks = []
        async for chunk in mock_ollama_client.stream_generate("Test"):
            chunks.append(chunk)
        
        assert len(chunks) == 3
        assert chunks[0].response == "chunk_0"
        assert chunks[0].done is False
        assert chunks[2].response == "chunk_2"
        assert chunks[2].done is True
    
    @pytest.mark.asyncio
    async def test_stream_chat(self, mock_ollama_client):
        """Test streaming chat completion."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        
        messages = [
            OllamaChatMessage(role="user", content="Hello")
        ]
        
        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            for i in range(2):
                yield OllamaResponse(
                    model="llama2:7b",
                    response=f"chat_chunk_{i}",
                    done=(i == 1)
                )
        
        mock_ollama_client._stream_with_retry.side_effect = mock_stream
        
        chunks = []
        async for chunk in mock_ollama_client.stream_chat(messages):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0].response == "chat_chunk_0"
        assert chunks[1].response == "chat_chunk_1"
        assert chunks[1].done is True
    
    @pytest.mark.asyncio
    async def test_pull_model_success(self, mock_ollama_client):
        """Test successful model pulling."""
        mock_ollama_client.client.stream.return_value.__aenter__.return_value.aiter_text.return_value = [
            '{"status": "pulling manifest"}',
            '{"status": "downloading"}',
            '{"status": "success"}'
        ]
        
        result = await mock_ollama_client.pull_model("llama2:7b")
        
        assert result is True
        mock_ollama_client.client.stream.assert_called_once_with(
            "POST",
            f"{mock_ollama_client.base_url}/api/pull",
            json={"name": "llama2:7b"}
        )
        
        # Check cache was cleared
        assert mock_ollama_client._available_models is None
    
    @pytest.mark.asyncio
    async def test_pull_model_failure(self, mock_ollama_client):
        """Test model pull failure."""
        mock_ollama_client.client.stream.side_effect = Exception("Pull failed")
        
        result = await mock_ollama_client.pull_model("llama2:7b")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_token_usage_tracking(self, mock_ollama_client):
        """Test token usage tracking across multiple requests."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        
        # Mock responses with different token usage
        responses = [
            OllamaResponse(
                model="llama2:7b",
                response="Response 1",
                token_usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
            ),
            OllamaResponse(
                model="llama2:7b",
                response="Response 2",
                token_usage={"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20}
            )
        ]
        
        mock_ollama_client._execute_with_retry.side_effect = responses
        
        # Generate two responses
        await mock_ollama_client.generate("Test 1")
        await mock_ollama_client.generate("Test 2")
        
        usage = mock_ollama_client.get_token_usage()
        
        assert usage["prompt_tokens"] == 13  # 5 + 8
        assert usage["completion_tokens"] == 22  # 10 + 12
        assert usage["total_tokens"] == 35  # 15 + 20
    
    @pytest.mark.asyncio
    async def test_token_usage_reset(self, mock_ollama_client):
        """Test token usage reset."""
        mock_ollama_client._select_model.return_value = "llama2:7b"
        mock_ollama_client._execute_with_retry.return_value = sample_ollama_response()
        
        # Generate response
        await mock_ollama_client.generate("Test")
        
        # Check usage
        usage_before = mock_ollama_client.get_token_usage()
        assert usage_before["total_tokens"] > 0
        
        # Reset usage
        mock_ollama_client.reset_token_usage()
        
        usage_after = mock_ollama_client.get_token_usage()
        assert usage_after["total_tokens"] == 0
        assert usage_after["prompt_tokens"] == 0
        assert usage_after["completion_tokens"] == 0
    
    @pytest.mark.asyncio
    async def test_client_close(self, mock_ollama_client):
        """Test client cleanup."""
        await mock_ollama_client.close()
        
        mock_ollama_client.client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_model_selection_no_available_models(self, mock_ollama_client):
        """Test model selection when no models available."""
        mock_ollama_client._available_models = []
        
        with pytest.raises(Exception):
            await mock_ollama_client.generate("Test")
    
    @pytest.mark.asyncio
    async def test_model_selection_preferred_available(self, mock_ollama_client):
        """Test model selection when preferred model is available."""
        mock_ollama_client._available_models = [
            MagicMock(name="llama2:7b", size="7B"),
            MagicMock(name="llama2:3b", size="3B")
        ]
        
        selected = await mock_ollama_client._select_model("llama2:7b")
        
        assert selected == "llama2:7b"
    
    @pytest.mark.asyncio
    async def test_model_selection_fallback_order(self, mock_ollama_client):
        """Test that fallback respects chain order."""
        mock_ollama_client._available_models = [
            MagicMock(name="model3", size="3B"),
            MagicMock(name="model2", size="2B"),
            MagicMock(name="model1", size="1B")
        ]
        
        mock_ollama_client.fallback_chain = ["model1", "model2", "model3"]
        
        # Should select model1 (first in fallback chain)
        selected = await mock_ollama_client._select_model("nonexistent")
        
        assert selected == "model1"


class TestOllamaResponse:
    """Test suite for OllamaResponse dataclass."""
    
    def test_response_creation(self):
        """Test OllamaResponse creation."""
        response = OllamaResponse(
            model="llama2:7b",
            created_at=1234567890,
            done=True,
            response="Test response",
            token_usage={"prompt_tokens": 10, "completion_tokens": 15}
        )
        
        assert response.model == "llama2:7b"
        assert response.created_at == 1234567890
        assert response.done is True
        assert response.response == "Test response"
        assert response.token_usage["prompt_tokens"] == 10
        assert response.token_usage["completion_tokens"] == 15
    
    def test_response_to_dict(self):
        """Test response dictionary conversion."""
        response = OllamaResponse(
            model="llama2:7b",
            done=True,
            response="Test response"
        )
        
        response_dict = response.__dict__
        
        assert response_dict["model"] == "llama2:7b"
        assert response_dict["done"] is True
        assert response_dict["response"] == "Test response"


class TestOllamaChatMessage:
    """Test suite for OllamaChatMessage dataclass."""
    
    def test_message_creation(self):
        """Test chat message creation."""
        message = OllamaChatMessage(
            role="user",
            content="Hello, world!"
        )
        
        assert message.role == "user"
        assert message.content == "Hello, world!"
    
    def test_message_roles(self):
        """Test valid message roles."""
        valid_roles = ["system", "user", "assistant"]
        
        for role in valid_roles:
            message = OllamaChatMessage(role=role, content="Test")
            assert message.role == role


class TestOllamaChatOptions:
    """Test suite for OllamaChatOptions dataclass."""
    
    def test_options_defaults(self):
        """Test default option values."""
        options = OllamaChatOptions()
        
        assert options.temperature == 0.7
        assert options.top_p == 0.9
        assert options.top_k == 40
        assert options.repeat_penalty == 1.1
        assert options.num_predict == -1
        assert options.num_ctx == 2048
        assert options.stream is False
        assert options.stop is None
        assert options.seed is None
    
    def test_options_custom_values(self):
        """Test custom option values."""
        options = OllamaChatOptions(
            temperature=0.5,
            top_p=0.8,
            top_k=20,
            repeat_penalty=1.2,
            num_predict=100,
            num_ctx=1024,
            stream=True,
            stop=["</s>"],
            seed=42
        )
        
        assert options.temperature == 0.5
        assert options.top_p == 0.8
        assert options.top_k == 20
        assert options.repeat_penalty == 1.2
        assert options.num_predict == 100
        assert options.num_ctx == 1024
        assert options.stream is True
        assert options.stop == ["</s>"]
        assert options.seed == 42
