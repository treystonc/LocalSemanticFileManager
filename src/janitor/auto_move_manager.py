"""Auto-move manager for automatic file organization."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config import get_config
from src.indexer.semantic_indexer import Indexer
from src.search.semantic_search import Janitor

logger = logging.getLogger(__name__)


class AutoMoveManager:
    """Manages automatic file organization based on rules."""
    
    def __init__(self, indexer: Optional[Indexer] = None, janitor: Optional[Janitor] = None):
        """Initialize the auto-move manager.
        
        Args:
            indexer: Indexer instance
            janitor: Janitor instance
        """
        self._config = get_config()
        self._indexer = indexer or Indexer()
        self._janitor = janitor or Janitor(self._indexer)
        self._pending_moves: list[dict] = []
        self._load_pending_moves()
    
    def _get_pending_moves_path(self) -> Path:
        """Get path to pending moves file."""
        default_path = self._config.get_database_path().parent / "pending_moves.json"
        custom_path = self._config.janitor.get("pending_moves_file")
        if custom_path:
            return Path(custom_path).expanduser()
        return default_path
    
    def _load_pending_moves(self) -> None:
        """Load pending moves from file."""
        path = self._get_pending_moves_path()
        
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._pending_moves = data.get("moves", [])
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load pending moves: {e}")
                self._pending_moves = []
        else:
            self._pending_moves = []
    
    def _save_pending_moves(self) -> None:
        """Save pending moves to file."""
        path = self._get_pending_moves_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"moves": self._pending_moves}, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save pending moves: {e}")
    
    def _get_rule(self, rule_name: str) -> Optional[dict]:
        """Get rule by name."""
        for rule in self._config.rules:
            if rule.get("name") == rule_name:
                return rule
        return None
    
    def _get_default(self, key: str, default: Any = None) -> Any:
        """Get default value from rules.json defaults section."""
        defaults = self._config.rules_defaults or {}
        return defaults.get(key, default)
    
    def evaluate_and_move(self, file_path: str) -> Optional[dict]:
        """Evaluate file against rules and auto-move if configured.
        
        Args:
            file_path: Path to the file to evaluate
            
        Returns:
            Move result dict if moved, None if not moved
        """
        path = Path(file_path)
        
        logger.info(f"[AutoMove] Evaluating: {file_path}")
        
        if not path.exists():
            logger.warning(f"[AutoMove] File not found: {file_path}")
            return None
        
        matches = self._janitor.evaluate_file(file_path)
        
        if not matches:
            logger.info(f"[AutoMove] No rules matched for: {path.name}")
            return None
        
        logger.info(f"[AutoMove] {len(matches)} rule(s) matched for: {path.name}")
        
        for match in matches:
            rule_name = match.get("rule_name")
            confidence = match.get("confidence", 0)
            
            logger.info(f"[AutoMove] Rule '{rule_name}': confidence={confidence:.2f}")
            
            rule = self._rule_by_name(rule_name)
            
            if not rule:
                logger.warning(f"[AutoMove] Rule not found: {rule_name}")
                continue
            
            auto_move = rule.get("auto_move", self._get_default("auto_move", False))
            
            if not auto_move:
                logger.info(f"[AutoMove] Rule '{rule_name}': auto_move disabled, skipping")
                continue
            
            threshold = rule.get(
                "auto_move_threshold",
                self._get_default("auto_move_threshold", 0.85)
            )
            
            if confidence < threshold:
                logger.info(
                    f"[AutoMove] Rule '{rule_name}': confidence {confidence:.2f} < threshold {threshold}, skipping"
                )
                continue
            
            target_folder = Path(rule.get("target_folder", "")).expanduser()
            target_path = target_folder / path.name
            
            if target_path.exists():
                logger.info(
                    f"[AutoMove] Rule '{rule_name}': target already exists at {target_path}, skipping"
                )
                continue
            
            logger.info(
                f"[AutoMove] Rule '{rule_name}': moving {path.name} to {target_folder}"
            )
            
            result = self._janitor.organize_file(
                file_path,
                str(target_folder),
                dry_run=False,
            )
            
            if result["success"]:
                move_record = {
                    "id": str(uuid.uuid4()),
                    "filename": path.name,
                    "original_path": str(path),
                    "target_folder": str(target_folder),
                    "rule_name": rule_name,
                    "confidence": confidence,
                    "moved_at": datetime.now().isoformat(),
                    "acknowledged": False,
                }
                
                self._pending_moves.append(move_record)
                self._save_pending_moves()
                
                logger.info(
                    f"[AutoMove] SUCCESS: {path.name} moved to {target_folder} "
                    f"(rule: {rule_name}, confidence: {confidence:.2f})"
                )
                
                return move_record
            else:
                logger.error(
                    f"[AutoMove] FAILED: {path.name} - {result.get('error')}"
                )
        
        logger.info(f"[AutoMove] No auto-move triggered for: {path.name}")
        return None
    
    def _rule_by_name(self, rule_name: str) -> Optional[dict]:
        """Get rule by name."""
        for rule in self._config.rules:
            if rule.get("name") == rule_name:
                return rule
        return None
    
    def get_pending_moves(self) -> list[dict]:
        """Get moves awaiting acknowledgement."""
        return [m for m in self._pending_moves if not m.get("acknowledged", False)]
    
    def get_acknowledged_moves(self) -> list[dict]:
        """Get acknowledged moves (history)."""
        return [m for m in self._pending_moves if m.get("acknowledged", False)]
    
    def acknowledge_move(self, move_id: str) -> bool:
        """Mark a single move as acknowledged.
        
        Args:
            move_id: ID of the move to acknowledge
            
        Returns:
            True if acknowledged, False if not found
        """
        for move in self._pending_moves:
            if move.get("id") == move_id:
                move["acknowledged"] = True
                self._save_pending_moves()
                return True
        return False
    
    def acknowledge_all(self) -> int:
        """Mark all pending moves as acknowledged.
        
        Returns:
            Number of moves acknowledged
        """
        count = 0
        for move in self._pending_moves:
            if not move.get("acknowledged", False):
                move["acknowledged"] = True
                count += 1
        
        if count > 0:
            self._save_pending_moves()
        
        return count
    
    def clear_acknowledged(self) -> int:
        """Remove acknowledged moves from storage.
        
        Returns:
            Number of moves removed
        """
        original_count = len(self._pending_moves)
        self._pending_moves = [m for m in self._pending_moves if not m.get("acknowledged", False)]
        removed = original_count - len(self._pending_moves)
        
        if removed > 0:
            self._save_pending_moves()
        
        return removed
    
    def get_move_count(self) -> dict:
        """Get counts of pending and acknowledged moves.
        
        Returns:
            Dict with 'pending' and 'acknowledged' counts
        """
        pending = len(self.get_pending_moves())
        acknowledged = len(self.get_acknowledged_moves())
        return {"pending": pending, "acknowledged": acknowledged}
