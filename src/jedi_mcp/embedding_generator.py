"""Embedding generation for vector search capabilities."""

import os
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from .models import EmbeddingConfig


class EmbeddingGenerator:
    """Generates vector embeddings for document content using sentence-transformers."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize the embedding generator.
        
        Args:
            config: Embedding configuration. If None, loads from environment.
        """
        self.config = config or EmbeddingConfig.from_env()
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self) -> None:
        """Initialize the sentence transformer model."""
        try:
            self.model = SentenceTransformer(self.config.model)
        except Exception as e:
            print(f"Warning: Could not load embedding model '{self.config.model}': {e}")
            print("Falling back to default model 'all-MiniLM-L6-v2'")
            self.config.model = "all-MiniLM-L6-v2"
            self.config.dimension = 384
            self.model = SentenceTransformer(self.config.model)
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")
        
        # Truncate text if too long
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_tensor=False)
        
        # Convert to list of floats
        return embedding.tolist()
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")
        
        # Truncate texts if too long
        truncated_texts = []
        for text in texts:
            if len(text) > self.config.max_text_length:
                truncated_texts.append(text[:self.config.max_text_length])
            else:
                truncated_texts.append(text)
        
        # Process in batches
        all_embeddings = []
        for i in range(0, len(truncated_texts), self.config.batch_size):
            batch = truncated_texts[i:i + self.config.batch_size]
            batch_embeddings = self.model.encode(batch, convert_to_tensor=False)
            
            # Convert to list of lists
            for embedding in batch_embeddings:
                all_embeddings.append(embedding.tolist())
        
        return all_embeddings
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this generator.
        
        Returns:
            Embedding dimension
        """
        return self.config.dimension
    
    def get_model_name(self) -> str:
        """
        Get the name of the embedding model being used.
        
        Returns:
            Model name
        """
        return self.config.model