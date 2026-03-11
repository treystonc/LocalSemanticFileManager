"""Tests for FileParser module."""

import tempfile
from pathlib import Path

import pytest

from src.ingestion.file_parser import FileParser


class TestFileParser:
    """Tests for the FileParser class."""
    
    def test_parse_text_file(self, tmp_path: Path):
        """Test parsing a plain text file."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello, this is a test document.", encoding="utf-8")
        
        parser = FileParser()
        result = parser.parse(text_file)
        
        assert result["success"] is True
        assert "Hello" in result["text"]
        assert result["metadata"]["extension"] == ".txt"
        assert result["error"] is None
    
    def test_parse_markdown_file(self, tmp_path: Path):
        """Test parsing a markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Header\n\nThis is **markdown** content.", encoding="utf-8")
        
        parser = FileParser()
        result = parser.parse(md_file)
        
        assert result["success"] is True
        assert "Header" in result["text"]
        assert result["metadata"]["extension"] == ".md"
    
    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist."""
        parser = FileParser()
        result = parser.parse(Path("/nonexistent/file.txt"))
        
        assert result["success"] is False
        assert "does not exist" in result["error"].lower()
    
    def test_parse_unsupported_extension(self, tmp_path: Path):
        """Test parsing an unsupported file type."""
        bin_file = tmp_path / "test.exe"
        bin_file.write_bytes(b"\x00\x01\x02\x03")
        
        parser = FileParser()
        result = parser.parse(bin_file)
        
        assert result["success"] is False
        assert "unsupported" in result["error"].lower()
    
    def test_is_supported(self):
        """Test the is_supported method."""
        parser = FileParser()
        
        assert parser.is_supported(Path("test.pdf")) is True
        assert parser.is_supported(Path("test.docx")) is True
        assert parser.is_supported(Path("test.xlsx")) is True
        assert parser.is_supported(Path("test.txt")) is True
        assert parser.is_supported(Path("test.md")) is True
        assert parser.is_supported(Path("test.exe")) is False
        assert parser.is_supported(Path("test.zip")) is False
    
    def test_custom_supported_extensions(self):
        """Test parser with custom supported extensions."""
        parser = FileParser(supported_extensions=[".txt", ".md"])
        
        assert parser.is_supported(Path("test.txt")) is True
        assert parser.is_supported(Path("test.md")) is True
        assert parser.is_supported(Path("test.pdf")) is False
    
    def test_parse_directory(self, tmp_path: Path):
        """Test parsing a directory of files."""
        (tmp_path / "file1.txt").write_text("Content 1", encoding="utf-8")
        (tmp_path / "file2.txt").write_text("Content 2", encoding="utf-8")
        (tmp_path / "file3.exe").write_bytes(b"\x00\x01")
        
        parser = FileParser()
        results = parser.parse_directory(tmp_path, recursive=False)
        
        assert len(results) == 2
        successful = [r for r in results if r["success"]]
        assert len(successful) == 2
    
    def test_parse_empty_file(self, tmp_path: Path):
        """Test parsing an empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")
        
        parser = FileParser()
        result = parser.parse(empty_file)
        
        assert result["success"] is True
        assert result["text"] == ""
