"""Semantic indexer module for vectorizing and storing document embeddings."""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src.config import get_config
from src.utils.text_chunker import TextChunker

logger = logging.getLogger(__name__)


def normalize_filename_for_search(filename: str) -> str:
    """Normalize filename for fuzzy matching.
    
    - Lowercase
    - Replace hyphens, underscores, dots with spaces
    - Collapse multiple spaces
    
    Args:
        filename: Original filename
        
    Returns:
        Normalized filename string
    """
    normalized = filename.lower()
    normalized = re.sub(r'[-_\.]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


class Indexer:
    """Indexes documents into ChromaDB with semantic embeddings."""
    
    COLLECTION_NAME = "documents"
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        db_path: Optional[Path] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        """Initialize the indexer.
        
        Args:
            model_name: Name of the sentence-transformers model
            db_path: Path to ChromaDB storage
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        config = get_config()
        
        self.model_name = model_name or config.get_model_name()
        self.db_path = db_path or config.get_database_path()
        self.chunk_size = chunk_size or config.get_chunk_size()
        self.chunk_overlap = chunk_overlap or config.get_chunk_overlap()
        
        self._model: Optional[SentenceTransformer] = None
        self._client: Optional[chromadb.Client] = None
        self._collection = None
        self._chunker = TextChunker(self.chunk_size, self.chunk_overlap)
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    @property
    def client(self) -> chromadb.Client:
        """Get ChromaDB client."""
        if self._client is None:
            self.db_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client
    
    @property
    def collection(self):
        """Get or create the documents collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection
    
    def _generate_id(self, file_path: str, chunk_index: int) -> str:
        """Generate a unique ID for a document chunk."""
        unique_string = f"{file_path}:{chunk_index}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def index_document(
        self,
        text: str,
        file_path: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Index a document by chunking and storing embeddings.
        
        Args:
            text: The document text
            file_path: Path to the source file
            metadata: Additional metadata
            
        Returns:
            Number of chunks indexed
        """
        if not text or not text.strip():
            logger.warning(f"Empty text for file: {file_path}")
            return 0
        
        base_metadata = {
            "file_path": str(file_path),
            "indexed_at": datetime.now().isoformat(),
            "normalized_filename": normalize_filename_for_search(Path(file_path).name),
        }
        
        if metadata:
            base_metadata.update(metadata)
        
        chunks_with_meta = self._chunker.chunk_with_metadata(text, base_metadata)
        
        if not chunks_with_meta:
            return 0
        
        ids = []
        documents = []
        metadatas = []
        
        for chunk_text, chunk_meta in chunks_with_meta:
            chunk_id = self._generate_id(
                str(file_path), 
                chunk_meta["chunk_index"]
            )
            ids.append(chunk_id)
            documents.append(chunk_text)
            metadatas.append(chunk_meta)
        
        embeddings = self.model.encode(documents, show_progress_bar=False).tolist()
        
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        
        logger.info(f"Indexed {len(ids)} chunks from {file_path}")
        return len(ids)
    
    def index_file(self, file_path: Path, parsed_result: dict) -> int:
        """Index a parsed file result.
        
        Args:
            file_path: Path to the file
            parsed_result: Result from FileParser.parse()
            
        Returns:
            Number of chunks indexed
        """
        if not parsed_result.get("success", False):
            logger.warning(
                f"Skipping file due to parse error: {parsed_result.get('error')}"
            )
            return 0
        
        metadata = parsed_result.get("metadata", {})
        return self.index_document(
            text=parsed_result["text"],
            file_path=str(file_path),
            metadata=metadata,
        )
    
    def remove_document(self, file_path: str) -> int:
        """Remove all chunks for a document.
        
        Args:
            file_path: Path to the file to remove
            
        Returns:
            Number of chunks removed
        """
        results = self.collection.get(
            where={"file_path": str(file_path)},
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Removed {len(results['ids'])} chunks for {file_path}")
            return len(results["ids"])
        
        return 0
    
    def update_document(
        self,
        text: str,
        file_path: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Update a document by removing old chunks and adding new ones.
        
        Args:
            text: The document text
            file_path: Path to the source file
            metadata: Additional metadata
            
        Returns:
            Number of chunks indexed
        """
        self.remove_document(file_path)
        return self.index_document(text, file_path, metadata)
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        """Search for documents matching the query.
        
        Args:
            query: Search query
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            Search results with ids, documents, metadatas, and distances
        """
        query_embedding = self.model.encode([query], show_progress_bar=False).tolist()
        
        return self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    
    def search_by_text(
        self,
        keyword: str,
        n_results: int = 100,
    ) -> dict:
        """Search for documents containing exact keyword in content.
        
        Args:
            keyword: Keyword to search for
            n_results: Maximum results to return
            
        Returns:
            Search results with ids, documents, metadatas, and distances
        """
        return self.collection.query(
            query_texts=[keyword],
            n_results=n_results,
            where_document={"$contains": keyword},
            include=["documents", "metadatas", "distances"],
        )
    
    def search_by_filename(
        self,
        filename: str,
        n_results: int = 100,
    ) -> dict:
        """Search for documents by filename.
        
        Args:
            filename: Filename or part of filename to search
            n_results: Maximum results to return
            
        Returns:
            Search results with ids, documents, metadatas, and distances
        """
        return self.collection.get(
            where={"filename": {"$contains": filename}},
            include=["documents", "metadatas"],
        )
    
    def get_all_file_paths(self) -> list[str]:
        """Get all unique file paths in the collection.
        
        Returns:
            List of unique file paths
        """
        results = self.collection.get(include=["metadatas"])
        seen = set()
        paths = []
        for meta in results.get("metadatas", []):
            fp = meta.get("file_path", "")
            if fp and fp not in seen:
                seen.add(fp)
                paths.append(fp)
        return paths
    
    def get_all_files_with_metadata(self) -> list[dict]:
        """Get all unique files with their metadata.
        
        Returns:
            List of dicts with file_path and metadata
        """
        results = self.collection.get(include=["documents", "metadatas"])
        seen = set()
        files = []
        for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
            fp = meta.get("file_path", "")
            if fp and fp not in seen:
                seen.add(fp)
                files.append({
                    "file_path": fp,
                    "document": doc,
                    "metadata": meta,
                })
        return files
    
    def reindex_all(self, parser) -> dict:
        """Re-index all documents with updated metadata.
        
        Args:
            parser: FileParser instance to re-parse files
            
        Returns:
            Statistics about the reindexing
        """
        files = self.get_all_file_paths()
        
        stats = {
            "total": len(files),
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        for file_path in files:
            try:
                path = Path(file_path)
                if not path.exists():
                    stats["skipped"] += 1
                    continue
                    
                parsed = parser.parse(path)
                if parsed.get("success"):
                    self.index_file(path, parsed)
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"Error re-indexing {file_path}: {e}")
                stats["failed"] += 1
        
        return stats
    
    def get_stats(self) -> dict:
        """Get statistics about the indexed documents."""
        count = self.collection.count()
        return {
            "total_chunks": count,
            "database_path": str(self.db_path),
            "model_name": self.model_name,
        }
    
    def clear_all(self) -> None:
        """Clear all indexed documents."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self._collection = None
        logger.info("Cleared all indexed documents")
