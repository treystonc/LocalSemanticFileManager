"""Text chunking utility for splitting documents into manageable segments."""

from typing import Iterator


class TextChunker:
    """Splits text into overlapping chunks for embedding."""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        """Initialize the chunker.
        
        Args:
            chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, text: str) -> list[str]:
        """Split text into overlapping chunks.
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        text = text.strip()
        
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            if end >= len(text):
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break
            
            chunk = text[start:end]
            
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")
            last_space = chunk.rfind(" ")
            
            break_point = max(last_period, last_newline, last_space)
            
            if break_point > start + self.chunk_size // 2:
                chunk = text[start:start + break_point + 1]
                end = start + break_point + 1
            
            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.overlap
            
            if start < 0:
                start = 0
        
        return chunks
    
    def chunk_with_metadata(
        self, 
        text: str, 
        metadata: dict
    ) -> list[tuple[str, dict]]:
        """Split text into chunks with metadata attached.
        
        Args:
            text: The text to chunk
            metadata: Base metadata to attach to each chunk
            
        Returns:
            List of tuples (chunk_text, chunk_metadata)
        """
        chunks = self.chunk(text)
        result = []
        
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)
            result.append((chunk, chunk_metadata))
        
        return result
    
    def __iter__(self, text: str) -> Iterator[str]:
        """Iterate over chunks of text."""
        return iter(self.chunk(text))
