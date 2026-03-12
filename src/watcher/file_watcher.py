"""File watcher module for real-time directory monitoring."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.config import get_config

logger = logging.getLogger(__name__)


class DebouncedEventHandler(FileSystemEventHandler):
    """Event handler with debouncing to handle rapid file changes."""
    
    def __init__(
        self,
        callback: Callable[[Path], None],
        debounce_seconds: float = 2.0,
        supported_extensions: Optional[set[str]] = None,
    ) -> None:
        """Initialize the handler.
        
        Args:
            callback: Function to call when a file is ready
            debounce_seconds: Seconds to wait before processing
            supported_extensions: Set of supported file extensions
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.supported_extensions = supported_extensions or set()
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer_thread: Optional[threading.Thread] = None
        self._running = True
    
    def _is_supported(self, file_path: Path) -> bool:
        """Check if the file extension is supported."""
        if not self.supported_extensions:
            return True
        return file_path.suffix.lower() in self.supported_extensions
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not self._is_supported(file_path):
            return
        
        self._schedule_callback(file_path)
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not self._is_supported(file_path):
            return
        
        self._schedule_callback(file_path)
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion event."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        with self._lock:
            if str(file_path) in self._pending:
                del self._pending[str(file_path)]
                logger.debug(f"Removed pending file: {file_path}")
    
    def _schedule_callback(self, file_path: Path) -> None:
        """Schedule a callback with debouncing."""
        with self._lock:
            self._pending[str(file_path)] = time.time()
        
        if self._timer_thread is None or not self._timer_thread.is_alive():
            self._timer_thread = threading.Thread(target=self._process_pending)
            self._timer_thread.daemon = True
            self._timer_thread.start()
    
    def _process_pending(self) -> None:
        """Process pending files after debounce period."""
        while self._running:
            time.sleep(0.5)
            
            now = time.time()
            ready_files = []
            
            with self._lock:
                for file_path_str, scheduled_time in list(self._pending.items()):
                    if now - scheduled_time >= self.debounce_seconds:
                        ready_files.append(Path(file_path_str))
                        del self._pending[file_path_str]
            
            for file_path in ready_files:
                try:
                    if file_path.exists():
                        logger.info(f"Processing file: {file_path}")
                        self.callback(file_path)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
            
            with self._lock:
                if not self._pending:
                    break
    
    def stop(self) -> None:
        """Stop the handler."""
        self._running = False


class FileWatcher:
    """Watches directories for file changes and triggers callbacks."""
    
    def __init__(
        self,
        on_file_created: Optional[Callable[[Path], None]] = None,
        on_file_modified: Optional[Callable[[Path], None]] = None,
        on_file_deleted: Optional[Callable[[Path], None]] = None,
        auto_move_manager=None,
    ) -> None:
        """Initialize the file watcher.
        
        Args:
            on_file_created: Callback for new files
            on_file_modified: Callback for modified files
            on_file_deleted: Callback for deleted files
            auto_move_manager: AutoMoveManager instance for auto-organization
        """
        config = get_config()
        
        self.debounce_seconds = config.get_debounce_seconds()
        self.supported_extensions = set(config.get_supported_extensions())
        
        self._observer: Optional[Observer] = None
        self._handler: Optional[DebouncedEventHandler] = None
        self._on_file_created = on_file_created
        self._on_file_modified = on_file_modified
        self._on_file_deleted = on_file_deleted
        self._auto_move_manager = auto_move_manager
    
    def _handle_file_event(self, file_path: Path, event_type: str) -> None:
        """Handle a file system event."""
        if event_type == "created" and self._on_file_created:
            self._on_file_created(file_path)
        elif event_type == "modified" and self._on_file_modified:
            self._on_file_modified(file_path)
        elif event_type == "deleted" and self._on_file_deleted:
            self._on_file_deleted(file_path)
        
        if event_type == "created" and self._auto_move_manager:
            logger.info(f"[Watcher] Auto-move evaluation triggered for: {file_path}")
            try:
                self._auto_move_manager.evaluate_and_move(str(file_path))
            except Exception as e:
                logger.error(f"[Watcher] Auto-move error for {file_path}: {e}")
    
    def start(self) -> None:
        """Start watching configured directories."""
        if self._observer is not None:
            logger.warning("Watcher is already running")
            return
        
        config = get_config()
        monitored_folders = config.get_monitored_folders()
        
        if not monitored_folders:
            logger.warning("No folders configured for monitoring")
            return
        
        self._observer = Observer()
        
        self._handler = DebouncedEventHandler(
            callback=lambda p: self._handle_file_event(p, "created"),
            debounce_seconds=self.debounce_seconds,
            supported_extensions=self.supported_extensions,
        )
        
        for folder_path, recursive in monitored_folders:
            if folder_path.exists():
                self._observer.schedule(
                    self._handler,
                    str(folder_path),
                    recursive=recursive,
                )
                logger.info(f"Watching: {folder_path} (recursive={recursive})")
            else:
                logger.warning(f"Folder does not exist: {folder_path}")
        
        self._observer.start()
        logger.info("File watcher started")
    
    def stop(self) -> None:
        """Stop watching directories."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("File watcher stopped")
        
        if self._handler is not None:
            self._handler.stop()
            self._handler = None
    
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._observer is not None and self._observer.is_alive()
    
    def add_directory(self, path: Path, recursive: bool = False) -> None:
        """Add a directory to watch (requires restart).
        
        Args:
            path: Directory path to watch
            recursive: Whether to watch subdirectories
        """
        if not path.exists():
            raise ValueError(f"Directory does not exist: {path}")
        
        if self._observer is not None and self._handler is not None:
            self._observer.schedule(
                self._handler,
                str(path),
                recursive=recursive,
            )
            logger.info(f"Added watch: {path} (recursive={recursive})")
