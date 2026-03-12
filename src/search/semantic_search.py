"""Semantic search and Janitor module for finding and organizing files."""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.indexer.semantic_indexer import Indexer

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Search for files using natural language queries with hybrid search."""
    
    KEYWORD_BONUS = 0.3
    FILENAME_BONUS = 0.5
    MIN_TOKEN_LENGTH = 2
    
    def __init__(self, indexer: Optional[Indexer] = None) -> None:
        """Initialize the search engine.
        
        Args:
            indexer: Indexer instance to use for searching
        """
        self._indexer = indexer or Indexer()
    
    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for fuzzy matching.
        
        - Lowercase
        - Replace hyphens, underscores with spaces
        - Collapse multiple spaces
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        normalized = text.lower()
        normalized = re.sub(r'[-_\.]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def _tokenize(self, text: str) -> list[str]:
        """Split text into tokens.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens (lowercase, filtered by min length)
        """
        normalized = self._normalize_for_matching(text)
        tokens = normalized.split()
        return [t for t in tokens if len(t) >= self.MIN_TOKEN_LENGTH]
    
    def _matches_any_token(self, text: str, query_tokens: list[str]) -> bool:
        """Check if any query token appears in normalized text.
        
        Args:
            text: Text to search in
            query_tokens: Tokenized query
            
        Returns:
            True if any token matches
        """
        if not query_tokens:
            return False
            
        normalized_text = self._normalize_for_matching(text)
        
        for token in query_tokens:
            if token in normalized_text:
                return True
        return False
    
    def _matches_all_tokens(self, text: str, query_tokens: list[str]) -> bool:
        """Check if all query tokens appear in normalized text.
        
        Args:
            text: Text to search in
            query_tokens: Tokenized query
            
        Returns:
            True if all tokens match
        """
        if not query_tokens:
            return True
            
        normalized_text = self._normalize_for_matching(text)
        
        for token in query_tokens:
            if token not in normalized_text:
                return False
        return True
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        file_filter: Optional[dict] = None,
        mode: str = "hybrid",
    ) -> list[dict]:
        """Search for files matching the query.
        
        Args:
            query: Natural language search query
            n_results: Maximum number of results to return
            file_filter: Optional metadata filter
            mode: Search mode - "semantic", "keyword", or "hybrid"
            
        Returns:
            List of search results with file info and relevance
        """
        if mode == "semantic":
            return self._semantic_search(query, n_results, file_filter)
        elif mode == "keyword":
            return self._keyword_search(query, n_results, file_filter)
        else:
            return self._hybrid_search(query, n_results, file_filter)
    
    def _semantic_search(
        self,
        query: str,
        n_results: int,
        file_filter: Optional[dict],
    ) -> list[dict]:
        """Pure semantic search using embeddings."""
        search_multiplier = max(10, n_results * 5)
        
        results = self._indexer.search(
            query=query,
            n_results=search_multiplier,
            where=file_filter,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        return self._process_results(results, bonus_keyword=None, bonus_filename=None)
    
    def _keyword_search(
        self,
        query: str,
        n_results: int,
        file_filter: Optional[dict],
    ) -> list[dict]:
        """Pure keyword search using text containment."""
        search_multiplier = max(20, n_results * 5)
        
        results = self._indexer.search_by_text(
            keyword=query,
            n_results=search_multiplier,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        return self._process_results(
            results, 
            bonus_keyword=True, 
            bonus_filename=None,
            keyword_query=query,
        )
    
    def _hybrid_search(
        self,
        query: str,
        n_results: int,
        file_filter: Optional[dict],
    ) -> list[dict]:
        """Hybrid search combining semantic, keyword, and filename matching."""
        search_multiplier = max(20, n_results * 5)
        query_tokens = self._tokenize(query)
        
        file_scores: dict[str, dict] = {}
        
        semantic_results = self._indexer.search(
            query=query,
            n_results=search_multiplier,
            where=file_filter,
        )
        
        if semantic_results["ids"] and semantic_results["ids"][0]:
            for doc_id, document, metadata, distance in zip(
                semantic_results["ids"][0],
                semantic_results["documents"][0],
                semantic_results["metadatas"][0],
                semantic_results["distances"][0],
            ):
                file_path = metadata.get("file_path", "")
                if file_path:
                    if file_path not in file_scores:
                        file_scores[file_path] = {
                            "file_path": file_path,
                            "filename": Path(file_path).name,
                            "semantic_score": 1 - distance,
                            "keyword_match": False,
                            "filename_match": False,
                            "best_chunk": document,
                            "metadata": metadata,
                        }
                    else:
                        existing = file_scores[file_path]["semantic_score"]
                        file_scores[file_path]["semantic_score"] = max(existing, 1 - distance)
        
        keyword_results = self._indexer.search_by_text(
            keyword=query,
            n_results=search_multiplier,
        )
        
        if keyword_results["ids"] and keyword_results["ids"][0]:
            for doc_id, document, metadata in zip(
                keyword_results["ids"][0],
                keyword_results["documents"][0],
                keyword_results["metadatas"][0],
            ):
                file_path = metadata.get("file_path", "")
                if file_path:
                    if file_path not in file_scores:
                        file_scores[file_path] = {
                            "file_path": file_path,
                            "filename": Path(file_path).name,
                            "semantic_score": 0.0,
                            "keyword_match": True,
                            "filename_match": False,
                            "best_chunk": document,
                            "metadata": metadata,
                        }
                    else:
                        file_scores[file_path]["keyword_match"] = True
        
        for token in query_tokens:
            token_results = self._indexer.search_by_text(
                keyword=token,
                n_results=search_multiplier,
            )
            
            if token_results["ids"] and token_results["ids"][0]:
                for doc_id, document, metadata in zip(
                    token_results["ids"][0],
                    token_results["documents"][0],
                    token_results["metadatas"][0],
                ):
                    file_path = metadata.get("file_path", "")
                    if file_path:
                        if file_path not in file_scores:
                            file_scores[file_path] = {
                                "file_path": file_path,
                                "filename": Path(file_path).name,
                                "semantic_score": 0.0,
                                "keyword_match": True,
                                "filename_match": False,
                                "best_chunk": document,
                                "metadata": metadata,
                            }
                        else:
                            file_scores[file_path]["keyword_match"] = True
        
        for file_path, data in file_scores.items():
            normalized_filename = data["metadata"].get(
                "normalized_filename",
                self._normalize_for_matching(data["filename"])
            )
            if self._matches_any_token(normalized_filename, query_tokens):
                data["filename_match"] = True
        
        final_results = []
        for file_path, data in file_scores.items():
            final_score = data["semantic_score"]
            if data["keyword_match"]:
                final_score += self.KEYWORD_BONUS
            if data["filename_match"]:
                final_score += self.FILENAME_BONUS
            
            snippet = data["best_chunk"]
            if snippet:
                snippet = snippet[:200] + "..." if len(snippet) > 200 else snippet
            
            final_results.append({
                "file_path": data["file_path"],
                "filename": data["filename"],
                "relevance_score": round(final_score, 4),
                "snippet": snippet,
                "metadata": data["metadata"],
                "semantic_score": data["semantic_score"],
                "keyword_match": data["keyword_match"],
                "filename_match": data["filename_match"],
            })
        
        final_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return final_results[:n_results]
    
    def _process_results(
        self,
        results: dict,
        bonus_keyword: Optional[bool],
        bonus_filename: Optional[bool],
        keyword_query: Optional[str] = None,
    ) -> list[dict]:
        """Process raw ChromaDB results into formatted output."""
        if not results["ids"] or not results["ids"][0]:
            return []
        
        unique_files: dict[str, dict] = {}
        
        for i, (doc_id, document, metadata, distance) in enumerate(zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0] if "distances" in results else [0.0] * len(results["ids"][0]),
        )):
            file_path = metadata.get("file_path", "")
            
            if file_path not in unique_files:
                similarity = 1 - distance
                final_score = similarity
                
                if bonus_keyword:
                    final_score += self.KEYWORD_BONUS
                if bonus_filename:
                    final_score += self.FILENAME_BONUS
                
                if keyword_query:
                    filename = Path(file_path).name.lower()
                    if keyword_query.lower() in filename:
                        final_score += self.FILENAME_BONUS
                
                unique_files[file_path] = {
                    "file_path": file_path,
                    "filename": Path(file_path).name,
                    "relevance_score": round(final_score, 4),
                    "semantic_score": round(similarity, 4),
                    "snippet": document[:200] + "..." if len(document) > 200 else document,
                    "metadata": metadata,
                    "keyword_match": bool(bonus_keyword),
                    "filename_match": bool(bonus_filename),
                }
        
        sorted_results = sorted(
            unique_files.values(),
            key=lambda x: x["relevance_score"],
            reverse=True,
        )
        
        return sorted_results
    
    def search_by_filename(self, query: str, n_results: int = 20) -> list[dict]:
        """Search files by filename only using token matching.
        
        Args:
            query: Filename search query
            n_results: Maximum results
            
        Returns:
            List of matching files sorted by number of token matches
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        results = []
        seen = set()
        batch_size = 500
        offset = 0
        
        while True:
            batch = self._indexer.collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            
            if not batch["ids"]:
                break
            
            for meta in batch["metadatas"]:
                fp = meta.get("file_path", "")
                if fp and fp not in seen:
                    seen.add(fp)
                    filename = Path(fp).name
                    normalized = meta.get(
                        "normalized_filename",
                        self._normalize_for_matching(filename)
                    )
                    
                    matched_tokens = sum(
                        1 for token in query_tokens 
                        if token in normalized
                    )
                    
                    if matched_tokens > 0:
                        results.append({
                            "file_path": fp,
                            "filename": filename,
                            "relevance_score": matched_tokens / len(query_tokens),
                            "snippet": "",
                            "metadata": meta,
                            "semantic_score": 0.0,
                            "keyword_match": False,
                            "filename_match": True,
                            "matched_tokens": matched_tokens,
                        })
            
            offset += batch_size
            
            if len(results) >= n_results * 3:
                break
        
        results.sort(key=lambda x: x["matched_tokens"], reverse=True)
        return results[:n_results]
    
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
    
    def evaluate_file(self, file_path: str) -> list[dict]:
        """Evaluate a file against all rules.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of matching rules with confidence scores
        """
        return self._evaluator.evaluate_file(file_path)
    
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
        
        seen_files = set()
        batch_size = 500
        offset = 0
        
        while True:
            batch = self._indexer.collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            
            if not batch["ids"]:
                break
            
            for metadata in batch.get("metadatas", []):
                file_path = metadata.get("file_path", "")
                
                if file_path and file_path not in seen_files:
                    seen_files.add(file_path)
                    suggestion = self.suggest_organization(file_path)
                    if suggestion:
                        suggestions.append(suggestion)
            
            offset += batch_size
        
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
