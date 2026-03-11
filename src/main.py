"""Main entry point for Socrates."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.ingestion.file_parser import FileParser
from src.indexer.semantic_indexer import Indexer
from src.watcher.file_watcher import FileWatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for Socrates CLI."""
    parser = argparse.ArgumentParser(
        description="Socrates - Local Semantic File Manager",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    index_parser = subparsers.add_parser("index", help="Index files")
    index_parser.add_argument("path", help="File or directory to index")
    index_parser.add_argument("-r", "--recursive", action="store_true", help="Recursive indexing")
    
    watch_parser = subparsers.add_parser("watch", help="Watch directories for changes")
    watch_parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    
    search_parser = subparsers.add_parser("search", help="Search indexed files")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("-n", "--num-results", type=int, default=5, help="Number of results")
    
    ui_parser = subparsers.add_parser("ui", help="Launch the web UI")
    
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    
    clear_parser = subparsers.add_parser("clear", help="Clear the index")
    
    args = parser.parse_args()
    
    if args.command == "index":
        index_files(args.path, args.recursive)
    elif args.command == "watch":
        start_watcher()
    elif args.command == "search":
        search_files(args.query, args.num_results)
    elif args.command == "ui":
        launch_ui()
    elif args.command == "stats":
        show_stats()
    elif args.command == "clear":
        clear_index()
    else:
        parser.print_help()


def index_files(path: str, recursive: bool) -> None:
    """Index files from a path."""
    config = get_config()
    parser = FileParser(config.get_supported_extensions())
    indexer = Indexer()
    
    target = Path(path).expanduser()
    
    if not target.exists():
        logger.error(f"Path does not exist: {target}")
        return
    
    if target.is_file():
        result = parser.parse(target)
        if result["success"]:
            chunks = indexer.index_file(target, result)
            logger.info(f"Indexed {chunks} chunks from {target}")
        else:
            logger.error(f"Failed to parse {target}: {result.get('error')}")
    else:
        results = parser.parse_directory(target, recursive=recursive)
        
        total_chunks = 0
        for result in results:
            if result["success"]:
                chunks = indexer.index_file(
                    Path(result["metadata"]["path"]),
                    result,
                )
                total_chunks += chunks
        
        logger.info(f"Indexed {total_chunks} chunks from {len(results)} files")


def start_watcher() -> None:
    """Start the file watcher."""
    config = get_config()
    parser = FileParser(config.get_supported_extensions())
    indexer = Indexer()
    
    def on_file_created(file_path: Path) -> None:
        logger.info(f"New file detected: {file_path}")
        result = parser.parse(file_path)
        if result["success"]:
            chunks = indexer.index_file(file_path, result)
            logger.info(f"Indexed {chunks} chunks from {file_path}")
    
    watcher = FileWatcher(on_file_created=on_file_created)
    watcher.start()
    
    logger.info("File watcher started. Press Ctrl+C to stop.")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
        watcher.stop()


def search_files(query: str, num_results: int) -> None:
    """Search indexed files."""
    from src.search.semantic_search import SemanticSearch
    
    indexer = Indexer()
    search = SemanticSearch(indexer)
    
    results = search.search(query, n_results=num_results)
    
    if not results:
        print("No results found.")
        return
    
    print(f"\nFound {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['filename']}")
        print(f"   Relevance: {result['relevance_score']:.2%}")
        print(f"   Path: {result['file_path']}")
        print(f"   Snippet: {result['snippet'][:100]}...")
        print()


def launch_ui() -> None:
    """Launch the Streamlit UI."""
    import subprocess
    
    ui_path = Path(__file__).parent / "ui" / "app.py"
    subprocess.run(["streamlit", "run", str(ui_path)])


def show_stats() -> None:
    """Show database statistics."""
    indexer = Indexer()
    stats = indexer.get_stats()
    
    print("\nDatabase Statistics:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Database path: {stats['database_path']}")
    print(f"  Model: {stats['model_name']}")
    print()


def clear_index() -> None:
    """Clear the index."""
    confirm = input("Are you sure you want to clear the index? [y/N]: ")
    if confirm.lower() == "y":
        indexer = Indexer()
        indexer.clear_all()
        print("Index cleared.")
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
