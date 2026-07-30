"""
CODX Embedding Generator

Text embedding generation for CODX knowledge engine
with multiple model support and optimization.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
import numpy as np
from abc import ABC, abstractmethod
import json
import tiktoken

from ..models.vector_embedding import VectorEmbedding, EmbeddingModel, EmbeddingStatus, VectorStoreType
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class EmbeddingModelProvider(ABC):
    """
    Abstract base class for embedding model providers.
    """
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass
    
    @abstractmethod
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        pass
    
    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """Get token count for text."""
        pass


class OpenAIEmbeddingProvider(EmbeddingModelProvider):
    """
    OpenAI embedding model provider.
    """
    
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        """Initialize OpenAI embedding provider."""
        self.api_key = api_key
        self.model = model
        self.client = None
        self.tokenizer = None
        
        # Initialize OpenAI client
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
            
            # Initialize tokenizer
            self.tokenizer = tiktoken.encoding_for_model(model)
            
        except ImportError:
            logger.error("OpenAI library not available")
            raise BaseLayerError("OpenAI library not available")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            logger.info(
                "OpenAI embedding generated",
                model=self.model,
                text_length=len(text),
                embedding_dimension=len(embedding)
            )
            
            return embedding
            
        except Exception as e:
            logger.error(
                "OpenAI embedding generation failed",
                error=str(e),
                model=self.model,
                text_length=len(text)
            )
            raise BaseLayerError(f"OpenAI embedding generation failed: {str(e)}") from e
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using OpenAI."""
        try:
            embeddings = []
            
            # Process in batches to avoid rate limits
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch_texts
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                
                # Add delay to avoid rate limits
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            logger.info(
                "OpenAI batch embeddings generated",
                model=self.model,
                text_count=len(texts),
                embedding_count=len(embeddings)
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "OpenAI batch embedding generation failed",
                error=str(e),
                model=self.model,
                text_count=len(texts)
            )
            raise BaseLayerError(f"OpenAI batch embedding generation failed: {str(e)}") from e
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information."""
        return {
            "provider": "openai",
            "model": self.model,
            "dimension": 1536,  # text-embedding-ada-002 dimension
            "max_tokens": 8191,
            "cost_per_1k_tokens": 0.0004,  # Approximate cost
            "batch_size": 100,
            "rate_limit": {
                "requests_per_minute": 3000,
                "tokens_per_minute": 250000
            }
        }
    
    def get_token_count(self, text: str) -> int:
        """Get token count using OpenAI tokenizer."""
        if not self.tokenizer:
            return len(text.split())
        
        return len(self.tokenizer.encode(text))


class SentenceTransformersProvider(EmbeddingModelProvider):
    """
    Sentence Transformers embedding model provider.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize Sentence Transformers provider."""
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        
        # Initialize model
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.tokenizer = self.model.tokenizer
            
        except ImportError:
            logger.error("Sentence Transformers library not available")
            raise BaseLayerError("Sentence Transformers library not available")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Sentence Transformers."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self.model.encode, text
            )
            
            # Convert to list if needed
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            
            logger.info(
                "Sentence Transformers embedding generated",
                model=self.model_name,
                text_length=len(text),
                embedding_dimension=len(embedding)
            )
            
            return embedding
            
        except Exception as e:
            logger.error(
                "Sentence Transformers embedding generation failed",
                error=str(e),
                model=self.model_name,
                text_length=len(text)
            )
            raise BaseLayerError(f"Sentence Transformers embedding generation failed: {str(e)}") from e
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using Sentence Transformers."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self.model.encode, texts
            )
            
            # Convert to list of lists if needed
            if hasattr(embeddings, 'tolist'):
                embeddings = embeddings.tolist()
            
            logger.info(
                "Sentence Transformers batch embeddings generated",
                model=self.model_name,
                text_count=len(texts),
                embedding_count=len(embeddings)
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "Sentence Transformers batch embedding generation failed",
                error=str(e),
                model=self.model_name,
                text_count=len(texts)
            )
            raise BaseLayerError(f"Sentence Transformers batch embedding generation failed: {str(e)}") from e
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Sentence Transformers model information."""
        return {
            "provider": "sentence_transformers",
            "model": self.model_name,
            "dimension": self.model.get_sentence_embedding_dimension() if self.model else 384,
            "max_tokens": 512,  # Typical for sentence transformers
            "cost_per_1k_tokens": 0.0,  # Free
            "batch_size": 32,  # Typical batch size
            "rate_limit": {
                "requests_per_minute": float('inf'),
                "tokens_per_minute": float('inf')
            }
        }
    
    def get_token_count(self, text: str) -> int:
        """Get token count using Sentence Transformers tokenizer."""
        if not self.tokenizer:
            return len(text.split())
        
        tokens = self.tokenizer.tokenize(text)
        return len(tokens)


class EmbeddingGenerator:
    """
    Main embedding generator for CODX knowledge engine.
    
    Provides unified interface for multiple embedding
    model providers with optimization and caching.
    """
    
    def __init__(self, provider: EmbeddingModelProvider):
        """Initialize embedding generator."""
        self.provider = provider
        self.embedding_cache: Dict[str, List[float]] = {}
        self.cache_ttl = 3600  # 1 hour
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # Performance metrics
        self.generation_stats = {
            "total_embeddings": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "generation_time_ms": 0,
            "tokens_processed": 0,
            "errors": 0
        }
        
        logger.info(
            "Embedding generator initialized",
            provider=provider.__class__.__name__,
            model_info=provider.get_model_info()
        )
    
    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True,
        normalize: bool = True
    ) -> List[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embedding
            
        Returns:
            Generated embedding vector
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(text)
            if use_cache and self._is_cache_valid(cache_key):
                self.generation_stats["cache_hits"] += 1
                cached_embedding = self.embedding_cache[cache_key]
                
                logger.info(
                    "Embedding retrieved from cache",
                    text_length=len(text),
                    cache_key=cache_key
                )
                
                return cached_embedding
            
            self.generation_stats["cache_misses"] += 1
            
            # Generate embedding
            embedding = await self.provider.generate_embedding(text)
            
            # Normalize if requested
            if normalize:
                embedding = self._normalize_embedding(embedding)
            
            # Update cache
            if use_cache:
                self._cache_embedding(cache_key, embedding)
            
            # Update statistics
            generation_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            token_count = self.provider.get_token_count(text)
            
            self.generation_stats.update({
                "total_embeddings": self.generation_stats["total_embeddings"] + 1,
                "generation_time_ms": self.generation_stats["generation_time_ms"] + generation_time,
                "tokens_processed": self.generation_stats["tokens_processed"] + token_count
            })
            
            logger.info(
                "Embedding generated successfully",
                text_length=len(text),
                token_count=token_count,
                embedding_dimension=len(embedding),
                generation_time_ms=generation_time,
                from_cache=False
            )
            
            return embedding
            
        except Exception as e:
            self.generation_stats["errors"] += 1
            logger.error(
                "Embedding generation failed",
                error=str(e),
                text_length=len(text)
            )
            raise BaseLayerError(f"Embedding generation failed: {str(e)}") from e
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        normalize: bool = True,
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            normalize: Whether to normalize embeddings
            batch_size: Batch size for processing
            
        Returns:
            List of generated embedding vectors
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            if not texts:
                return []
            
            # Determine batch size
            if not batch_size:
                model_info = self.provider.get_model_info()
                batch_size = model_info.get("batch_size", 32)
            
            # Separate cached and uncached texts
            uncached_texts = []
            uncached_indices = []
            cached_embeddings = [None] * len(texts)
            
            for i, text in enumerate(texts):
                cache_key = self._generate_cache_key(text)
                if use_cache and self._is_cache_valid(cache_key):
                    cached_embeddings[i] = self.embedding_cache[cache_key]
                    self.generation_stats["cache_hits"] += 1
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
                    self.generation_stats["cache_misses"] += 1
            
            # Generate embeddings for uncached texts
            if uncached_texts:
                new_embeddings = await self.provider.generate_embeddings_batch(uncached_texts)
                
                # Process new embeddings
                for i, (text, embedding) in enumerate(zip(uncached_texts, new_embeddings)):
                    original_index = uncached_indices[i]
                    
                    # Normalize if requested
                    if normalize:
                        embedding = self._normalize_embedding(embedding)
                    
                    # Update cache
                    if use_cache:
                        cache_key = self._generate_cache_key(text)
                        self._cache_embedding(cache_key, embedding)
                    
                    # Update result
                    cached_embeddings[original_index] = embedding
            
            # Update statistics
            generation_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            total_tokens = sum(self.provider.get_token_count(text) for text in texts)
            
            self.generation_stats.update({
                "total_embeddings": self.generation_stats["total_embeddings"] + len(texts),
                "generation_time_ms": self.generation_stats["generation_time_ms"] + generation_time,
                "tokens_processed": self.generation_stats["tokens_processed"] + total_tokens
            })
            
            logger.info(
                "Batch embeddings generated successfully",
                text_count=len(texts),
                uncached_count=len(uncached_texts),
                cached_count=len(texts) - len(uncached_texts),
                total_tokens=total_tokens,
                generation_time_ms=generation_time
            )
            
            return cached_embeddings
            
        except Exception as e:
            self.generation_stats["errors"] += 1
            logger.error(
                "Batch embedding generation failed",
                error=str(e),
                text_count=len(texts)
            )
            raise BaseLayerError(f"Batch embedding generation failed: {str(e)}") from e
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.embedding_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_embedding(self, cache_key: str, embedding: List[float]) -> None:
        """Cache embedding."""
        self.embedding_cache[cache_key] = embedding
        self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
        
        # Cleanup old cache entries
        self._cleanup_cache()
    
    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding vector."""
        if not embedding:
            return embedding
        
        # Calculate L2 norm
        norm = sum(x * x for x in embedding) ** 0.5
        
        if norm == 0:
            return embedding
        
        # Normalize
        return [x / norm for x in embedding]
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.now(timezone.utc)
        keys_to_remove = []
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age_seconds = (current_time - timestamp).total_seconds()
            if age_seconds > self.cache_ttl:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in self.embedding_cache:
                del self.embedding_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        total_requests = self.generation_stats["cache_hits"] + self.generation_stats["cache_misses"]
        cache_hit_rate = (
            self.generation_stats["cache_hits"] / total_requests
            if total_requests > 0 else 0.0
        )
        
        avg_generation_time = (
            self.generation_stats["generation_time_ms"] / self.generation_stats["total_embeddings"]
            if self.generation_stats["total_embeddings"] > 0 else 0.0
        )
        
        return {
            "total_embeddings": self.generation_stats["total_embeddings"],
            "cache_hits": self.generation_stats["cache_hits"],
            "cache_misses": self.generation_stats["cache_misses"],
            "cache_hit_rate": cache_hit_rate,
            "average_generation_time_ms": avg_generation_time,
            "total_generation_time_ms": self.generation_stats["generation_time_ms"],
            "tokens_processed": self.generation_stats["tokens_processed"],
            "errors": self.generation_stats["errors"],
            "cache_size": len(self.embedding_cache),
            "model_info": self.provider.get_model_info()
        }
    
    def reset_stats(self) -> None:
        """Reset generation statistics."""
        self.generation_stats = {
            "total_embeddings": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "generation_time_ms": 0,
            "tokens_processed": 0,
            "errors": 0
        }
    
    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self.embedding_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Embedding cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on embedding generator."""
        try:
            # Test embedding generation
            test_text = "This is a test for embedding generation."
            test_embedding = await self.generate_embedding(test_text, use_cache=False)
            
            # Test batch generation
            test_texts = ["Test text 1", "Test text 2"]
            test_embeddings = await self.generate_embeddings_batch(test_texts, use_cache=False)
            
            health_status = {
                "status": "healthy",
                "provider": self.provider.__class__.__name__,
                "model_info": self.provider.get_model_info(),
                "test_embedding_generated": len(test_embedding) > 0,
                "test_batch_generated": len(test_embeddings) == len(test_texts),
                "cache_size": len(self.embedding_cache),
                "stats": self.get_generation_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Embedding generator health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Embedding generator health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "provider": self.provider.__class__.__name__,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "provider": self.provider.__class__.__name__,
            "model_info": self.provider.get_model_info(),
            "cache_config": {
                "cache_size": len(self.embedding_cache),
                "cache_ttl": self.cache_ttl,
                "cache_enabled": True
            },
            "stats": self.get_generation_stats()
        }


def create_embedding_generator(
    provider_type: str,
    **config
) -> EmbeddingGenerator:
    """
    Create embedding generator for specified provider.
    
    Args:
        provider_type: Type of provider ("openai", "sentence_transformers")
        config: Provider configuration
        
    Returns:
        EmbeddingGenerator instance
    """
    if provider_type == "openai":
        api_key = config.get("api_key")
        model = config.get("model", "text-embedding-ada-002")
        
        if not api_key:
            raise BaseLayerError("OpenAI API key is required")
        
        provider = OpenAIEmbeddingProvider(api_key=api_key, model=model)
        return EmbeddingGenerator(provider)
    
    elif provider_type == "sentence_transformers":
        model_name = config.get("model_name", "all-MiniLM-L6-v2")
        provider = SentenceTransformersProvider(model_name=model_name)
        return EmbeddingGenerator(provider)
    
    else:
        raise BaseLayerError(f"Unsupported embedding provider: {provider_type}")


def calculate_similarity(
    embedding1: List[float],
    embedding2: List[float]
) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score
    """
    if len(embedding1) != len(embedding2):
        raise BaseLayerError("Embedding dimensions must match")
    
    if not embedding1 or not embedding2:
        return 0.0
    
    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    
    # Calculate magnitudes
    magnitude1 = sum(a * a for a in embedding1) ** 0.5
    magnitude2 = sum(b * b for b in embedding2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    # Calculate cosine similarity
    return dot_product / (magnitude1 * magnitude2)


def calculate_euclidean_distance(
    embedding1: List[float],
    embedding2: List[float]
) -> float:
    """
    Calculate Euclidean distance between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Euclidean distance
    """
    if len(embedding1) != len(embedding2):
        raise BaseLayerError("Embedding dimensions must match")
    
    return sum((a - b) ** 2 for a, b in zip(embedding1, embedding2)) ** 0.5


def calculate_manhattan_distance(
    embedding1: List[float],
    embedding2: List[float]
) -> float:
    """
    Calculate Manhattan distance between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Manhattan distance
    """
    if len(embedding1) != len(embedding2):
        raise BaseLayerError("Embedding dimensions must match")
    
    return sum(abs(a - b) for a, b in zip(embedding1, embedding2))
