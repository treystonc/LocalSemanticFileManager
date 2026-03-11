"""Tests for Indexer module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestTextChunker:
    """Tests for the TextChunker class."""
    
    def test_chunk_small_text(self):
        """Test chunking text smaller than chunk size."""
        from src.utils.text_chunker import TextChunker
        
        chunker = TextChunker(chunk_size=100, overlap=10)
        text = "This is a short text."
        
        chunks = chunker.chunk(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_large_text(self):
        """Test chunking text larger than chunk size."""
        from src.utils.text_chunker import TextChunker
        
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "This is a longer text that should be split into multiple chunks."
        
        chunks = chunker.chunk(text)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 60
    
    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        from src.utils.text_chunker import TextChunker
        
        chunker = TextChunker()
        chunks = chunker.chunk("")
        
        assert chunks == []
    
    def test_chunk_with_metadata(self):
        """Test chunking with metadata."""
        from src.utils.text_chunker import TextChunker
        
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "This is a test text that will be chunked with metadata attached."
        metadata = {"filename": "test.txt"}
        
        results = chunker.chunk_with_metadata(text, metadata)
        
        assert len(results) >= 1
        for chunk_text, chunk_meta in results:
            assert "filename" in chunk_meta
            assert "chunk_index" in chunk_meta
            assert "total_chunks" in chunk_meta


class TestIndexer:
    """Tests for the Indexer class."""
    
    @patch("src.indexer.semantic_indexer.SentenceTransformer")
    @patch("src.indexer.semantic_indexer.chromadb")
    def test_index_document(self, mock_chromadb, mock_transformer):
        """Test indexing a document."""
        from src.indexer.semantic_indexer import Indexer
        
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_transformer.return_value = mock_model
        
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(db_path=Path(tmpdir) / "db")
            
            count = indexer.index_document(
                text="This is a test document.",
                file_path="/test/file.txt",
            )
            
            assert count > 0
            mock_collection.add.assert_called_once()
    
    @patch("src.indexer.semantic_indexer.SentenceTransformer")
    @patch("src.indexer.semantic_indexer.chromadb")
    def test_index_empty_text(self, mock_chromadb, mock_transformer):
        """Test indexing empty text."""
        from src.indexer.semantic_indexer import Indexer
        
        indexer = Indexer.__new__(Indexer)
        indexer._model = MagicMock()
        indexer._client = MagicMock()
        indexer._collection = MagicMock()
        indexer._chunker = MagicMock()
        indexer._chunker.chunk_with_metadata.return_value = []
        
        count = indexer.index_document(
            text="",
            file_path="/test/file.txt",
        )
        
        assert count == 0
    
    @patch("src.indexer.semantic_indexer.SentenceTransformer")
    @patch("src.indexer.semantic_indexer.chromadb")
    def test_search(self, mock_chromadb, mock_transformer):
        """Test searching for documents."""
        from src.indexer.semantic_indexer import Indexer
        
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_transformer.return_value = mock_model
        
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[{"file_path": "/test/file.txt"}]],
            "distances": [[0.1]],
        }
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(db_path=Path(tmpdir) / "db")
            
            results = indexer.search("test query")
            
            assert results["ids"] == [["id1"]]
            mock_collection.query.assert_called_once()
    
    @patch("src.indexer.semantic_indexer.SentenceTransformer")
    @patch("src.indexer.semantic_indexer.chromadb")
    def test_remove_document(self, mock_chromadb, mock_transformer):
        """Test removing a document."""
        from src.indexer.semantic_indexer import Indexer
        
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["id1", "id2"]}
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(db_path=Path(tmpdir) / "db")
            
            count = indexer.remove_document("/test/file.txt")
            
            assert count == 2
            mock_collection.delete.assert_called_once_with(ids=["id1", "id2"])
    
    @patch("src.indexer.semantic_indexer.SentenceTransformer")
    @patch("src.indexer.semantic_indexer.chromadb")
    def test_get_stats(self, mock_chromadb, mock_transformer):
        """Test getting database statistics."""
        from src.indexer.semantic_indexer import Indexer
        
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(db_path=Path(tmpdir) / "db")
            indexer._model = None
            indexer.model_name = "test-model"
            
            stats = indexer.get_stats()
            
            assert stats["total_chunks"] == 100
            assert "database_path" in stats
            assert stats["model_name"] == "test-model"
