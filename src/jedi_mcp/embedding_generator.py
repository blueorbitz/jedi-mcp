"""Embedding generation for vector search capabilities."""

import os
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from .models import EmbeddingConfig


logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates vector embeddings for text content using sentence-transformers."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize the embedding generator.
        
        Args:
            config: Embedding configuration. If None, loads from environment.
        """
        self.config = config or EmbeddingConfig.from_env()
        self._model: Optional[SentenceTransformer] = None
        
        # Validate model support
        supported_models = {'all-MiniLM-L6-v2', 'Qwen/Qwen3-Embedding-0.6B'}
        if self.config.model not in supported_models:
            raise ValueError(f"Unsupported model: {self.config.model}. Supported models: {supported_models}")
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.config.model}")
            self._model = SentenceTransformer(self.config.model)
            
            # Verify the model dimension matches configuration
            actual_dimension = self._model.get_sentence_embedding_dimension()
            if actual_dimension != self.config.dimension:
                logger.warning(
                    f"Model dimension mismatch: expected {self.config.dimension}, "
                    f"got {actual_dimension}. Updating configuration."
                )
                self.config.dimension = actual_dimension
        
        return self._model
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of float values representing the embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.config.dimension
        
        # Truncate text if it exceeds max length
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
            logger.debug(f"Truncated text to {self.config.max_text_length} characters")
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_tensor=False)
        
        # Ensure it's a list of floats
        if hasattr(embedding, 'tolist'):
            return embedding.tolist()
        return list(embedding)
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors, one for each input text
        """
        if not texts:
            return []
        
        # Process texts in batches
        all_embeddings = []
        batch_size = self.config.batch_size
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Prepare batch (handle empty texts and truncation)
            processed_batch = []
            for text in batch:
                if not text or not text.strip():
                    processed_batch.append("")
                elif len(text) > self.config.max_text_length:
                    processed_batch.append(text[:self.config.max_text_length])
                else:
                    processed_batch.append(text)
            
            # Generate embeddings for batch
            logger.debug(f"Processing batch of {len(processed_batch)} texts")
            batch_embeddings = self.model.encode(processed_batch, convert_to_tensor=False)
            
            # Convert to list format
            for embedding in batch_embeddings:
                if hasattr(embedding, 'tolist'):
                    all_embeddings.append(embedding.tolist())
                else:
                    all_embeddings.append(list(embedding))
        
        # Handle empty texts by replacing with zero vectors
        for i, text in enumerate(texts):
            if not text or not text.strip():
                all_embeddings[i] = [0.0] * self.config.dimension
        
        return all_embeddings
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this generator.
        
        Returns:
            Embedding dimension
        """
        return self.config.dimension
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks for processing long documents.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks with overlap
        """
        if len(text) <= self.config.max_text_length:
            return [text]
        
        chunks = []
        chunk_size = self.config.max_text_length - self.config.chunk_overlap
        
        for i in range(0, len(text), chunk_size):
            chunk_end = min(i + self.config.max_text_length, len(text))
            chunk = text[i:chunk_end]
            
            # Avoid very small chunks at the end
            if len(chunk) < self.config.chunk_overlap and chunks:
                # Merge with previous chunk
                chunks[-1] += " " + chunk
            else:
                chunks.append(chunk)
        
        return chunks
    
    def generate_chunked_embeddings(self, text: str) -> List[List[float]]:
        """
        Generate embeddings for a long text by chunking it first.
        
        Args:
            text: Input text to embed (can be longer than max_text_length)
            
        Returns:
            List of embedding vectors for each chunk
        """
        chunks = self.chunk_text(text)
        return self.generate_batch_embeddings(chunks)