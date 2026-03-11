"""Tests for Semantic Search and Janitor modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSemanticSearch:
    """Tests for the SemanticSearch class."""
    
    @patch("src.search.semantic_search.Indexer")
    def test_search_returns_results(self, mock_indexer_class):
        """Test search returns formatted results."""
        from src.search.semantic_search import SemanticSearch
        
        mock_indexer = MagicMock()
        mock_indexer.search.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["Document 1 content", "Document 2 content"]],
            "metadatas": [
                [
                    {"file_path": "/path/to/file1.txt"},
                    {"file_path": "/path/to/file2.txt"},
                ]
            ],
            "distances": [[0.1, 0.3]],
        }
        
        search = SemanticSearch(indexer=mock_indexer)
        results = search.search("test query", n_results=5)
        
        assert len(results) == 2
        assert results[0]["file_path"] == "/path/to/file1.txt"
        assert results[0]["relevance_score"] > results[1]["relevance_score"]
    
    @patch("src.search.semantic_search.Indexer")
    def test_search_empty_results(self, mock_indexer_class):
        """Test search with no results."""
        from src.search.semantic_search import SemanticSearch
        
        mock_indexer = MagicMock()
        mock_indexer.search.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        
        search = SemanticSearch(indexer=mock_indexer)
        results = search.search("test query")
        
        assert results == []
    
    @patch("src.search.semantic_search.Indexer")
    def test_search_by_keyword_or(self, mock_indexer_class):
        """Test keyword search with OR logic."""
        from src.search.semantic_search import SemanticSearch
        
        mock_indexer = MagicMock()
        mock_indexer.search.return_value = {
            "ids": [["id1"]],
            "documents": [["Content"]],
            "metadatas": [[{"file_path": "/path/file.txt"}]],
            "distances": [[0.1]],
        }
        
        search = SemanticSearch(indexer=mock_indexer)
        results = search.search_by_keyword(
            keywords=["python", "code"],
            operator="OR",
            n_results=5,
        )
        
        assert mock_indexer.search.call_count == 2
    
    @patch("src.search.semantic_search.Indexer")
    def test_search_by_keyword_and(self, mock_indexer_class):
        """Test keyword search with AND logic."""
        from src.search.semantic_search import SemanticSearch
        
        mock_indexer = MagicMock()
        mock_indexer.search.side_effect = [
            {
                "ids": [["id1"]],
                "documents": [["Python content"]],
                "metadatas": [[{"file_path": "/path/file1.txt"}]],
                "distances": [[0.1]],
            },
            {
                "ids": [["id1", "id2"]],
                "documents": [["Python code content", "Other code"]],
                "metadatas": [
                    [
                        {"file_path": "/path/file1.txt"},
                        {"file_path": "/path/file2.txt"},
                    ]
                ],
                "distances": [[0.1, 0.2]],
            },
        ]
        
        search = SemanticSearch(indexer=mock_indexer)
        results = search.search_by_keyword(
            keywords=["python", "code"],
            operator="AND",
            n_results=5,
        )
        
        assert len(results) == 1
        assert results[0]["file_path"] == "/path/file1.txt"


class TestRuleEvaluator:
    """Tests for the RuleEvaluator class."""
    
    @patch("src.search.semantic_search.Indexer")
    @patch("src.search.semantic_search.get_config")
    def test_evaluate_file_matches_rule(self, mock_config, mock_indexer_class):
        """Test evaluating a file that matches a rule."""
        from src.search.semantic_search import RuleEvaluator
        
        mock_config.return_value.rules = [
            {
                "name": "Finance",
                "conditions": {"operator": "OR", "keywords": ["invoice", "receipt"]},
                "similarity_threshold": 0.75,
                "target_folder": "~/Documents/Finance",
            }
        ]
        
        mock_indexer = MagicMock()
        mock_indexer.search.return_value = {
            "ids": [["id1"]],
            "documents": [["Invoice document"]],
            "metadatas": [[{"file_path": "/path/invoice.pdf"}]],
            "distances": [[0.1]],
        }
        
        evaluator = RuleEvaluator(indexer=mock_indexer)
        matches = evaluator.evaluate_file("/path/invoice.pdf")
        
        assert len(matches) == 1
        assert matches[0]["rule_name"] == "Finance"
        assert matches[0]["confidence"] > 0.75
    
    @patch("src.search.semantic_search.Indexer")
    @patch("src.search.semantic_search.get_config")
    def test_evaluate_file_no_match(self, mock_config, mock_indexer_class):
        """Test evaluating a file that doesn't match any rule."""
        from src.search.semantic_search import RuleEvaluator
        
        mock_config.return_value.rules = [
            {
                "name": "Finance",
                "conditions": {"operator": "OR", "keywords": ["invoice"]},
                "similarity_threshold": 0.90,
                "target_folder": "~/Documents/Finance",
            }
        ]
        
        mock_indexer = MagicMock()
        mock_indexer.search.return_value = {
            "ids": [["id1"]],
            "documents": [["Some other document"]],
            "metadatas": [[{"file_path": "/path/other.pdf"}]],
            "distances": [[0.5]],
        }
        
        evaluator = RuleEvaluator(indexer=mock_indexer)
        matches = evaluator.evaluate_file("/path/unrelated.pdf")
        
        assert len(matches) == 0


class TestJanitor:
    """Tests for the Janitor class."""
    
    @patch("src.search.semantic_search.RuleEvaluator")
    @patch("src.search.semantic_search.Indexer")
    @patch("src.search.semantic_search.get_config")
    def test_suggest_organization(self, mock_config, mock_indexer_class, mock_evaluator_class):
        """Test getting organization suggestions."""
        from src.search.semantic_search import Janitor
        
        mock_config.return_value.is_auto_move_enabled.return_value = False
        mock_config.return_value.requires_confirmation.return_value = True
        
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_file.return_value = [
            {
                "rule_name": "Finance",
                "file_path": "/path/invoice.pdf",
                "target_folder": "~/Documents/Finance",
                "confidence": 0.85,
                "matched_keywords": ["invoice"],
            }
        ]
        mock_evaluator_class.return_value = mock_evaluator
        
        janitor = Janitor()
        suggestion = janitor.suggest_organization("/path/invoice.pdf")
        
        assert suggestion is not None
        assert suggestion["rule_name"] == "Finance"
        assert suggestion["confidence"] == 0.85
    
    @patch("src.search.semantic_search.RuleEvaluator")
    @patch("src.search.semantic_search.Indexer")
    @patch("src.search.semantic_search.get_config")
    def test_organize_file_dry_run(self, mock_config, mock_indexer_class, mock_evaluator_class):
        """Test organizing a file in dry run mode."""
        from src.search.semantic_search import Janitor
        
        mock_config.return_value.is_auto_move_enabled.return_value = False
        mock_config.return_value.requires_confirmation.return_value = True
        
        mock_evaluator = MagicMock()
        mock_evaluator_class.return_value = mock_evaluator
        
        mock_indexer = MagicMock()
        mock_indexer_class.return_value = mock_indexer
        
        janitor = Janitor(indexer=mock_indexer)
        
        with patch.object(Path, "exists", return_value=True):
            result = janitor.organize_file(
                "/path/source.txt",
                "/path/target",
                dry_run=True,
            )
        
        assert result["success"] is True
        assert result["dry_run"] is True
