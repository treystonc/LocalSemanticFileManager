"""Semantic search and Janitor module for finding and organizing files."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.indexer.semantic_indexer import Indexer

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Search for files using natural language queries."""
    
    def __init__(self, indexer: Optional[Indexer] = None) -> None:
        """Initialize the search engine.
        
        Args:
            indexer: Indexer instance to use for searching
        """
        self._indexer = indexer or Indexer()
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        file_filter: Optional[dict] = None,
    ) -> list[dict]:
        """Search for files matching the query.
        
        Args:
            query: Natural language search query
            n_results: Maximum number of results to return
            file_filter: Optional metadata filter
            
        Returns:
            List of search results with file info and relevance
        """
        results = self._indexer.search(
            query=query,
            n_results=n_results * 3,
            where=file_filter,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        unique_files: dict[str, dict] = {}
        
        for i, (doc_id, document, metadata, distance) in enumerate(zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            file_path = metadata.get("file_path", "")
            
            if file_path not in unique_files:
                similarity = 1 - distance
                unique_files[file_path] = {
                    "file_path": file_path,
                    "filename": Path(file_path).name,
                    "relevance_score": round(similarity, 4),
                    "snippet": document[:200] + "..." if len(document) > 200 else document,
                    "metadata": metadata,
                }
        
        sorted_results = sorted(
            unique_files.values(),
            key=lambda x: x["relevance_score"],
            reverse=True,
        )
        
        return sorted_results[:n_results]
    
    def search_by_keyword(
        self,
        keywords: list[str],
        operator: str = "OR",
        n_results: int = 5,
    ) -> list[dict]:
        """Search using keywords with AND/OR logic.
        
        Args:
            keywords: List of keywords to search
            operator: "AND" or "OR" logic
            n_results: Maximum results per keyword
            
        Returns:
            List of search results
        """
        all_results = []
        
        for keyword in keywords:
            results = self.search(keyword, n_results=n_results)
            all_results.extend(results)
        
        if operator.upper() == "AND":
            file_counts: dict[str, int] = {}
            file_data: dict[str, dict] = {}
            
            for result in all_results:
                fp = result["file_path"]
                file_counts[fp] = file_counts.get(fp, 0) + 1
                if fp not in file_data:
                    file_data[fp] = result
            
            required_count = len(keywords)
            and_results = [
                file_data[fp]
                for fp, count in file_counts.items()
                if count >= required_count
            ]
            return sorted(and_results, key=lambda x: x["relevance_score"], reverse=True)
        
        seen = set()
        unique_results = []
        for result in all_results:
            if result["file_path"] not in seen:
                seen.add(result["file_path"])
                unique_results.append(result)
        
        return sorted(unique_results, key=lambda x: x["relevance_score"], reverse=True)[:n_results]


class RuleEvaluator:
    """Evaluates files against janitor rules."""
    
    def __init__(self, indexer: Optional[Indexer] = None) -> None:
        """Initialize the rule evaluator.
        
        Args:
            indexer: Indexer instance for semantic matching
        """
        self._indexer = indexer or Indexer()
        self._search = SemanticSearch(self._indexer)
        self._rules = get_config().rules
    
    def get_rules(self) -> list[dict]:
        """Get all janitor rules."""
        return self._rules
    
    def evaluate_file(self, file_path: str) -> list[dict]:
        """Evaluate a file against all rules.
        
        Args:
            file_path: Path to the file to evaluate
            
        Returns:
            List of matching rules with confidence scores
        """
        matches = []
        
        for rule in self._rules:
            match_result = self._evaluate_rule(file_path, rule)
            if match_result:
                matches.append(match_result)
        
        return sorted(matches, key=lambda x: x["confidence"], reverse=True)
    
    def _evaluate_rule(self, file_path: str, rule: dict) -> Optional[dict]:
        """Evaluate a single rule against a file.
        
        Args:
            file_path: Path to the file
            rule: Rule configuration
            
        Returns:
            Match result or None if no match
        """
        conditions = rule.get("conditions", {})
        keywords = conditions.get("keywords", [])
        operator = conditions.get("operator", "OR").upper()
        threshold = rule.get("similarity_threshold", 0.75)
        
        results = self._search.search_by_keyword(
            keywords=keywords,
            operator=operator,
            n_results=10,
        )
        
        for result in results:
            if result["file_path"] == file_path:
                confidence = result["relevance_score"]
                
                if confidence >= threshold:
                    return {
                        "rule_name": rule.get("name", "Unnamed"),
                        "file_path": file_path,
                        "target_folder": rule.get("target_folder", ""),
                        "confidence": confidence,
                        "matched_keywords": keywords,
                    }
        
        return None


class Janitor:
    """Automatically organizes files based on semantic rules."""
    
    def __init__(self, indexer: Optional[Indexer] = None) -> None:
        """Initialize the janitor.
        
        Args:
            indexer: Indexer instance
        """
        config = get_config()
        self._indexer = indexer or Indexer()
        self._evaluator = RuleEvaluator(self._indexer)
        self._auto_move = config.is_auto_move_enabled()
        self._require_confirmation = config.requires_confirmation()
    
    def suggest_organization(self, file_path: str) -> Optional[dict]:
        """Suggest where a file should be organized.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Suggestion dict or None
        """
        matches = self._evaluator.evaluate_file(file_path)
        
        if matches:
            best_match = matches[0]
            return {
                "file_path": file_path,
                "suggested_folder": best_match["target_folder"],
                "rule_name": best_match["rule_name"],
                "confidence": best_match["confidence"],
                "new_path": str(Path(best_match["target_folder"]).expanduser() / Path(file_path).name),
            }
        
        return None
    
    def get_all_suggestions(self) -> list[dict]:
        """Get organization suggestions for all indexed files.
        
        Returns:
            List of suggestions
        """
        suggestions = []
        
        stats = self._indexer.get_stats()
        
        results = self._indexer.collection.get(include=["metadatas"])
        
        seen_files = set()
        for metadata in results.get("metadatas", []):
            file_path = metadata.get("file_path", "")
            
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                suggestion = self.suggest_organization(file_path)
                if suggestion:
                    suggestions.append(suggestion)
        
        return suggestions
    
    def organize_file(
        self,
        file_path: str,
        target_folder: str,
        dry_run: bool = True,
    ) -> dict:
        """Move a file to a target folder.
        
        Args:
            file_path: Path to the file
            target_folder: Destination folder
            dry_run: If True, only simulate the move
            
        Returns:
            Result dict with status and details
        """
        source = Path(file_path).expanduser()
        dest_folder = Path(target_folder).expanduser()
        dest_path = dest_folder / source.name
        
        result = {
            "source": str(source),
            "destination": str(dest_path),
            "success": False,
            "dry_run": dry_run,
            "error": None,
        }
        
        if not source.exists():
            result["error"] = "Source file does not exist"
            return result
        
        if dry_run:
            result["success"] = True
            result["message"] = "Dry run - file would be moved"
            return result
        
        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest_path))
            
            self._indexer.remove_document(str(source))
            result["success"] = True
            result["message"] = "File moved successfully"
            
            logger.info(f"Moved file: {source} -> {dest_path}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error moving file {source}: {e}")
        
        return result
    
    def batch_organize(
        self,
        suggestions: Optional[list[dict]] = None,
        dry_run: bool = True,
        min_confidence: float = 0.75,
    ) -> list[dict]:
        """Organize multiple files based on suggestions.
        
        Args:
            suggestions: List of suggestions (if None, get all)
            dry_run: If True, only simulate
            min_confidence: Minimum confidence to act on
            
        Returns:
            List of results
        """
        if suggestions is None:
            suggestions = self.get_all_suggestions()
        
        results = []
        
        for suggestion in suggestions:
            if suggestion["confidence"] >= min_confidence:
                result = self.organize_file(
                    file_path=suggestion["file_path"],
                    target_folder=suggestion["suggested_folder"],
                    dry_run=dry_run,
                )
                result["suggestion"] = suggestion
                results.append(result)
        
        return results
