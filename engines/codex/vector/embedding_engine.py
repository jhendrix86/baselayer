"""
CODEX Embedding Engine

Ollama-based embedding generation with Redis caching
for semantic search capabilities.
"""

import asyncio
import hashlib
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ...llm.ollama_client import OllamaClient, get_ollama_client

logger = get_logger(__name__)


class EmbeddingEngine:
    """
    Embedding generation engine using Ollama with Redis caching.
    
    Generates vector embeddings for semantic search using
    nomic-embed-text or mxbai-embed-large models.
    """
    
    def __init__(
        self, 
        redis_client=None,
        model: str = "nomic-embed-text",
        cache_ttl: int = 86400  # 24 hours
    ):
        """Initialize embedding engine."""
        self.redis_client = redis_client
        self.model = model
        self.cache_ttl = cache_ttl
        self.ollama_client = get_ollama_client()
        
        # Model dimensions
        self.dimensions = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024
        }
        
        self.current_dimension = self.dimensions.get(model, 768)
        
        logger.info("EmbeddingEngine initialized", 
                   model=model,
                   dimensions=self.current_dimension,
                   cache_ttl=cache_ttl)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding vector
        """
        if not text or not text.strip():
            raise BaseLayerError("Text cannot be empty")
        
        # Check cache first
        cached_embedding = await self._get_cached_embedding(text)
        if cached_embedding:
            logger.debug("Embedding cache hit", text_length=len(text))
            return cached_embedding
        
        # Generate new embedding
        embedding = await self._generate_embedding_from_ollama(text)
        
        # Cache the result
        await self._cache_embedding(text, embedding)
        
        logger.debug("Generated new embedding", 
                   text_length=len(text),
                   model=self.model)
        
        return embedding
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            return []
        
        # Check cache for each text
        cache_results = await self._get_cached_batch_embeddings(valid_texts)
        
        # Separate cached and uncached texts
        uncached_texts = []
        uncached_indices = []
        cached_embeddings = [None] * len(valid_texts)
        
        for i, text in enumerate(valid_texts):
            cached_result = cache_results.get(text)
            if cached_result:
                cached_embeddings[i] = cached_result
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            uncached_embeddings = await self._generate_batch_from_ollama(uncached_texts)
            
            # Cache the new embeddings
            await self._cache_batch_embeddings(uncached_texts, uncached_embeddings)
            
            # Insert uncached embeddings into results
            for i, embedding in zip(uncached_indices, uncached_embeddings):
                cached_embeddings[i] = embedding
        
        # Filter out None values (shouldn't happen but safety check)
        final_embeddings = [emb for emb in cached_embeddings if emb is not None]
        
        logger.info("Batch embedding generation completed", 
                   total_texts=len(texts),
                   valid_texts=len(valid_texts),
                   cached=len(valid_texts) - len(uncached_texts),
                   generated=len(uncached_texts))
        
        return final_embeddings
    
    async def normalize_embedding(self, embedding: List[float]) -> List[float]:
        """
        Normalize embedding vector for cosine similarity.
        
        Args:
            embedding: Raw embedding vector
            
        Returns:
            Normalized embedding vector
        """
        if not embedding:
            return []
        
        # Calculate magnitude
        magnitude = sum(x * x for x in embedding) ** 0.5
        
        if magnitude == 0:
            return embedding
        
        # Normalize
        normalized = [x / magnitude for x in embedding]
        
        return normalized
    
    async def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (-1.0 to 1.0)
        """
        if len(embedding1) != len(embedding2):
            raise BaseLayerError("Embeddings must have same dimensions")
        
        if not embedding1 or not embedding2:
            return 0.0
        
        # Normalize both embeddings
        norm1 = await self.normalize_embedding(embedding1)
        norm2 = await self.normalize_embedding(embedding2)
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(norm1, norm2))
        
        return dot_product
    
    def get_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self.current_dimension
    
    async def clear_cache(self, pattern: str = "*") -> int:
        """
        Clear embedding cache.
        
        Args:
            pattern: Cache key pattern to clear (default: all)
            
        Returns:
            Number of cache keys cleared
        """
        if not self.redis_client:
            return 0
        
        try:
            # Get all cache keys
            cache_keys = await self.redis_client.keys(f"codex:embed:{pattern}")
            
            if not cache_keys:
                return 0
            
            # Delete all keys
            deleted_count = 0
            for key in cache_keys:
                await self.redis_client.delete(key)
                deleted_count += 1
            
            logger.info("Embedding cache cleared", 
                       pattern=pattern,
                       deleted_count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            logger.error("Failed to clear embedding cache", error=str(e))
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.redis_client:
            return {"cache_enabled": False}
        
        try:
            # Get cache keys count
            cache_keys = await self.redis_client.keys("codex:embed:*")
            
            # Sample a few keys to check TTL
            sample_keys = cache_keys[:10] if len(cache_keys) > 10 else cache_keys
            ttl_info = []
            
            for key in sample_keys:
                ttl = await self.redis_client.ttl(key)
                ttl_info.append(ttl)
            
            avg_ttl = sum(ttl_info) / len(ttl_info) if ttl_info else 0
            
            return {
                "cache_enabled": True,
                "total_keys": len(cache_keys),
                "sample_ttls": ttl_info,
                "avg_ttl_seconds": avg_ttl,
                "cache_ttl": self.cache_ttl,
                "model": self.model,
                "dimensions": self.current_dimension
            }
            
        except Exception as e:
            logger.error("Failed to get cache stats", error=str(e))
            return {"cache_enabled": True, "error": str(e)}
    
    async def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache."""
        if not self.redis_client:
            return None
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(text)
            
            # Get from cache
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                embedding_data = json.loads(cached_data)
                return embedding_data["embedding"]
            
            return None
            
        except Exception as e:
            logger.error("Failed to get cached embedding", error=str(e))
            return None
    
    async def _get_cached_batch_embeddings(self, texts: List[str]) -> Dict[str, List[float]]:
        """Get multiple embeddings from cache."""
        if not self.redis_client:
            return {}
        
        try:
            # Generate cache keys
            cache_keys = [self._generate_cache_key(text) for text in texts]
            
            # Get from cache (pipeline for efficiency)
            pipeline = self.redis_client.pipeline()
            for key in cache_keys:
                pipeline.get(key)
            
            cached_data = await pipeline.execute()
            
            # Parse results
            results = {}
            for i, (text, key, data) in enumerate(zip(texts, cache_keys, cached_data)):
                if data:
                    embedding_data = json.loads(data)
                    results[text] = embedding_data["embedding"]
            
            return results
            
        except Exception as e:
            logger.error("Failed to get cached batch embeddings", error=str(e))
            return {}
    
    async def _cache_embedding(self, text: str, embedding: List[float]) -> None:
        """Cache embedding for text."""
        if not self.redis_client:
            return
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(text)
            
            # Prepare cache data
            cache_data = {
                "embedding": embedding,
                "model": self.model,
                "dimensions": self.current_dimension,
                "cached_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in cache
            await self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                json.dumps(cache_data)
            )
            
        except Exception as e:
            logger.error("Failed to cache embedding", error=str(e))
    
    async def _cache_batch_embeddings(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """Cache multiple embeddings."""
        if not self.redis_client:
            return
        
        try:
            # Prepare pipeline for batch caching
            pipeline = self.redis_client.pipeline()
            
            for text, embedding in zip(texts, embeddings):
                cache_key = self._generate_cache_key(text)
                cache_data = {
                    "embedding": embedding,
                    "model": self.model,
                    "dimensions": self.current_dimension,
                    "cached_at": datetime.now(timezone.utc).isoformat()
                }
                pipeline.setex(cache_key, self.cache_ttl, json.dumps(cache_data))
            
            # Execute pipeline
            await pipeline.execute()
            
        except Exception as e:
            logger.error("Failed to cache batch embeddings", error=str(e))
    
    async def _generate_embedding_from_ollama(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        try:
            # Call Ollama embedding API
            response = await self.ollama_client.embed(
                model=self.model,
                prompt=text
            )
            
            # Extract embedding from response
            if hasattr(response, 'embedding'):
                embedding = response.embedding
            else:
                # Handle different response format
                embedding = response.get('embedding', [])
            
            if not embedding:
                raise BaseLayerError("No embedding returned from Ollama")
            
            # Validate embedding dimensions
            if len(embedding) != self.current_dimension:
                logger.warning("Embedding dimension mismatch", 
                           expected=self.current_dimension,
                           actual=len(embedding))
            
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding from Ollama", error=str(e))
            raise BaseLayerError(f"Failed to generate embedding: {e}")
    
    async def _generate_batch_from_ollama(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using Ollama."""
        try:
            # Ollama doesn't have a batch embedding API, so we'll generate them in parallel
            tasks = []
            for text in texts:
                task = self._generate_embedding_from_ollama(text)
                tasks.append(task)
            
            # Run all tasks concurrently
            embeddings = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            valid_embeddings = []
            for i, result in enumerate(embeddings):
                if isinstance(result, Exception):
                    logger.error(f"Failed to embed text {i}: {result}")
                    # Add empty embedding to maintain order
                    valid_embeddings.append([0.0] * self.current_dimension)
                else:
                    valid_embeddings.append(result)
            
            return valid_embeddings
            
        except Exception as e:
            logger.error("Failed to generate batch embeddings", error=str(e))
            raise BaseLayerError(f"Failed to generate batch embeddings: {e}")
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Use SHA-256 hash for consistent cache keys
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return f"codex:embed:{self.model}:{text_hash}"
    
    async def validate_embedding(self, embedding: List[float]) -> bool:
        """Validate embedding format and dimensions."""
        if not isinstance(embedding, list):
            return False
        
        if len(embedding) != self.current_dimension:
            return False
        
        # Check if all values are numbers
        for value in embedding:
            if not isinstance(value, (int, float)):
                return False
            if not (-1.0 <= value <= 1.0):  # Reasonable range for normalized embeddings
                return False
        
        return True
    
    async def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for embedding generation.
        
        Args:
            text: Raw text
            
        Returns:
            Preprocessed text
        """
        if not text:
            return text
        
        # Basic preprocessing
        processed = text.strip()
        
        # Remove excessive whitespace
        processed = ' '.join(processed.split())
        
        # Truncate if too long (Ollama has context limits)
        max_length = 8192  # Adjust based on model
        if len(processed) > max_length:
            processed = processed[:max_length]
        
        return processed
    
    async def calculate_embedding_similarity_threshold(self, sample_embeddings: List[List[float]]) -> float:
        """
        Calculate similarity threshold for duplicate detection.
        
        Args:
            sample_embeddings: Sample of embeddings to analyze
            
        Returns:
            Recommended similarity threshold
        """
        if len(sample_embeddings) < 2:
            return 0.95  # Default high threshold
        
        # Calculate pairwise similarities
        similarities = []
        for i in range(len(sample_embeddings)):
            for j in range(i + 1, len(sample_embeddings)):
                similarity = await self.cosine_similarity(
                    sample_embeddings[i], 
                    sample_embeddings[j]
                )
                similarities.append(similarity)
        
        if not similarities:
            return 0.95
        
        # Use 95th percentile as threshold
        similarities.sort(reverse=True)
        threshold_index = int(len(similarities) * 0.05)
        threshold = similarities[threshold_index] if threshold_index < len(similarities) else similarities[-1]
        
        return max(0.9, threshold)  # Minimum 0.9 threshold
