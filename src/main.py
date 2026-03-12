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
    search_parser.add_argument(
        "-m", "--mode",
        choices=["hybrid", "semantic", "keyword", "filename"],
        default="hybrid",
        help="Search mode (default: hybrid)"
    )
    
    ui_parser = subparsers.add_parser("ui", help="Launch the web UI")
    
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    
    clear_parser = subparsers.add_parser("clear", help="Clear the index")
    
    reindex_parser = subparsers.add_parser("reindex", help="Re-index all files with updated metadata")
    
    debug_parser = subparsers.add_parser("debug-move", help="Debug auto-move evaluation for a file")
    debug_parser.add_argument("path", help="File path to evaluate")
    
    args = parser.parse_args()
    
    if args.command == "index":
        index_files(args.path, args.recursive)
    elif args.command == "watch":
        start_watcher()
    elif args.command == "search":
        search_files(args.query, args.num_results, args.mode)
    elif args.command == "ui":
        launch_ui()
    elif args.command == "stats":
        show_stats()
    elif args.command == "clear":
        clear_index()
    elif args.command == "reindex":
        reindex_files()
    elif args.command == "debug-move":
        debug_auto_move(args.path)
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
    
    from src.janitor import AutoMoveManager
    from src.search.semantic_search import Janitor
    
    janitor = Janitor(indexer)
    auto_move_manager = AutoMoveManager(indexer, janitor)
    
    def on_file_created(file_path: Path) -> None:
        logger.info(f"New file detected: {file_path}")
        result = parser.parse(file_path)
        if result["success"]:
            chunks = indexer.index_file(file_path, result)
            logger.info(f"Indexed {chunks} chunks from {file_path}")
    
    watcher = FileWatcher(
        on_file_created=on_file_created,
        auto_move_manager=auto_move_manager,
    )
    watcher.start()
    
    logger.info("File watcher started (auto-move enabled). Press Ctrl+C to stop.")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
        watcher.stop()


def search_files(query: str, num_results: int, mode: str) -> None:
    """Search indexed files."""
    from src.search.semantic_search import SemanticSearch
    
    indexer = Indexer()
    search = SemanticSearch(indexer)
    
    if mode == "filename":
        results = search.search_by_filename(query, n_results=num_results)
    else:
        results = search.search(query, n_results=num_results, mode=mode)
    
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


def reindex_files() -> None:
    """Re-index all files with updated metadata."""
    config = get_config()
    parser = FileParser(config.get_supported_extensions())
    indexer = Indexer()
    
    print("Starting re-indexing...")
    stats = indexer.reindex_all(parser)
    
    print(f"\nRe-indexing complete:")
    print(f"  Total files: {stats['total']}")
    print(f"  Successfully re-indexed: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped (not found): {stats['skipped']}")
    print()


def debug_auto_move(file_path: str) -> None:
    """Debug auto-move evaluation for a file."""
    from src.janitor import AutoMoveManager
    from src.search.semantic_search import Janitor
    
    path = Path(file_path).expanduser()
    
    if not path.exists():
        print(f"Error: File not found: {path}")
        return
    
    print(f"\n{'='*60}")
    print(f"DEBUG: Auto-Move Evaluation")
    print(f"{'='*60}")
    print(f"File: {path.name}")
    print(f"Path: {path}")
    print(f"{'='*60}\n")
    
    indexer = Indexer()
    janitor = Janitor(indexer)
    auto_manager = AutoMoveManager(indexer, janitor)
    config = get_config()
    
    parser = FileParser(config.get_supported_extensions())
    result = parser.parse(path)
    
    if not result["success"]:
        print(f"Parse Error: {result.get('error')}")
        return
    
    print(f"Parse Success: {len(result['text'])} characters extracted\n")
    
    matches = janitor.evaluate_file(str(path))
    
    if not matches:
        print("No rules matched this file.")
        print("\nTo add a rule, edit config/rules.json")
        return
    
    print(f"Rules Matched: {len(matches)}\n")
    
    defaults = config.rules_defaults
    global_auto = defaults.get("auto_move", False)
    global_threshold = defaults.get("auto_move_threshold", 0.85)
    
    for i, match in enumerate(matches, 1):
        rule_name = match["rule_name"]
        confidence = match["confidence"]
        
        rule = None
        for r in config.rules:
            if r.get("name") == rule_name:
                rule = r
                break
        
        if rule:
            auto_move = rule.get("auto_move", global_auto)
            threshold = rule.get("auto_move_threshold", global_threshold)
            target = rule.get("target_folder", "N/A")
            sim_threshold = rule.get("similarity_threshold", 0.75)
        else:
            auto_move = global_auto
            threshold = global_threshold
            target = "N/A"
            sim_threshold = 0.75
        
        print(f"--- Rule {i}: {rule_name} ---")
        print(f"  Confidence:        {confidence:.2f}")
        print(f"  Similarity Thresh: {sim_threshold}")
        print(f"  Auto-Move:         {'Yes' if auto_move else 'No'}")
        print(f"  Auto-Move Thresh:  {threshold}")
        print(f"  Target Folder:     {target}")
        print(f"  Will Move:         {'YES' if auto_move and confidence >= threshold else 'NO'}")
        
        if auto_move and confidence < threshold:
            print(f"  Reason:            Confidence {confidence:.2f} < threshold {threshold}")
        elif not auto_move:
            print(f"  Reason:            Auto-move disabled for this rule")
        elif confidence >= threshold:
            print(f"  Reason:            All conditions met!")
        print()
    
    print(f"{'='*60}")
    print("To enable auto-move for a rule, set 'auto_move: true' in config/rules.json")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
