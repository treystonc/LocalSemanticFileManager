"""Main Streamlit UI for Socrates."""

import subprocess
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.ingestion.file_parser import FileParser
from src.indexer.semantic_indexer import Indexer
from src.search.semantic_search import Janitor, SemanticSearch
from src.watcher.file_watcher import FileWatcher

st.set_page_config(
    page_title="Socrates - Local Semantic File Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_indexer():
    return Indexer()


@st.cache_resource
def get_search():
    return SemanticSearch(get_indexer())


@st.cache_resource
def get_janitor():
    return Janitor(get_indexer())


@st.cache_resource
def get_parser():
    return FileParser()


def main():
    st.title("📚 Socrates")
    st.subheader("Local Semantic File Manager")
    
    config = get_config()
    
    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.subheader("Monitored Folders")
        for folder, recursive in config.get_monitored_folders():
            st.text(f"📁 {folder}")
            st.caption(f"Recursive: {recursive}")
        
        st.divider()
        
        st.subheader("Database Stats")
        indexer = get_indexer()
        stats = indexer.get_stats()
        st.metric("Indexed Chunks", stats["total_chunks"])
        st.caption(f"Model: {stats['model_name']}")
        
        st.divider()
        
        if st.button("🔄 Reindex All"):
            with st.spinner("Reindexing..."):
                reindex_all()
            st.success("Reindexing complete!")
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["🔍 Search", "🧹 Janitor", "📊 Index"])
    
    with tab1:
        render_search_tab()
    
    with tab2:
        render_janitor_tab()
    
    with tab3:
        render_index_tab()


def render_search_tab():
    st.header("Semantic Search")
    
    query = st.text_input(
        "Search your files using natural language:",
        placeholder="e.g., 'quarterly financial report' or 'python tutorial'",
    )
    
    n_results = st.slider("Number of results", 1, 20, 5)
    
    if query:
        with st.spinner("Searching..."):
            search = get_search()
            results = search.search(query, n_results=n_results)
        
        if results:
            st.subheader(f"Found {len(results)} results")
            
            for i, result in enumerate(results, 1):
                with st.expander(
                    f"{i}. {result['filename']} "
                    f"(Relevance: {result['relevance_score']:.2%})",
                    expanded=(i == 1),
                ):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown("**Snippet:**")
                        st.text(result["snippet"])
                        
                        st.markdown("**Path:**")
                        st.code(result["file_path"])
                    
                    with col2:
                        if st.button("📂 Open Folder", key=f"open_{i}"):
                            open_folder(Path(result["file_path"]).parent)
                        
                        st.metric("Relevance", f"{result['relevance_score']:.2%}")
        else:
            st.info("No results found. Try a different query or index more files.")


def render_janitor_tab():
    st.header("File Organization (Janitor)")
    
    config = get_config()
    janitor = get_janitor()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Current Rules")
        rules = config.rules
        if rules:
            for rule in rules:
                with st.container():
                    st.markdown(f"**{rule['name']}**")
                    st.caption(
                        f"Keywords: {', '.join(rule['conditions']['keywords'])} "
                        f"({rule['conditions']['operator']})"
                    )
                    st.caption(f"Target: {rule['target_folder']}")
                    st.caption(f"Threshold: {rule['similarity_threshold']}")
                    st.divider()
        else:
            st.info("No rules configured. Add rules to config/rules.json")
    
    with col2:
        st.subheader("Actions")
        
        dry_run = st.checkbox(
            "Dry Run Mode",
            value=True,
            help="Preview changes without moving files",
        )
        
        min_confidence = st.slider(
            "Minimum Confidence",
            0.0,
            1.0,
            0.75,
            0.05,
            help="Only suggest moves above this confidence",
        )
        
        if st.button("🔍 Get Suggestions"):
            with st.spinner("Analyzing files..."):
                suggestions = janitor.get_all_suggestions()
            
            if suggestions:
                st.session_state["suggestions"] = [
                    s for s in suggestions
                    if s["confidence"] >= min_confidence
                ]
            else:
                st.info("No organization suggestions found.")
        
        if "suggestions" in st.session_state:
            st.subheader("Suggestions")
            
            for i, suggestion in enumerate(st.session_state["suggestions"]):
                with st.container():
                    col_a, col_b, col_c = st.columns([2, 2, 1])
                    
                    with col_a:
                        st.text(Path(suggestion["file_path"]).name)
                        st.caption(suggestion["file_path"])
                    
                    with col_b:
                        st.text(f"→ {suggestion['rule_name']}")
                        st.caption(suggestion["suggested_folder"])
                    
                    with col_c:
                        st.metric("Conf.", f"{suggestion['confidence']:.0%}")
                        
                        if st.button("✓ Move", key=f"move_{i}"):
                            result = janitor.organize_file(
                                suggestion["file_path"],
                                suggestion["suggested_folder"],
                                dry_run=dry_run,
                            )
                            if result["success"]:
                                st.success("Moved!" if not dry_run else "Would move")
                            else:
                                st.error(result.get("error", "Move failed"))


def render_index_tab():
    st.header("Index Management")
    
    indexer = get_indexer()
    parser = get_parser()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Index a Folder")
        
        folder_path = st.text_input(
            "Folder Path",
            placeholder="e.g., ~/Documents",
        )
        
        recursive = st.checkbox("Recursive", value=True)
        
        if st.button("📁 Index Folder"):
            if folder_path:
                path = Path(folder_path).expanduser()
                if path.exists():
                    with st.spinner("Indexing..."):
                        results = parser.parse_directory(path, recursive=recursive)
                        
                        indexed = 0
                        for result in results:
                            if result["success"]:
                                chunks = indexer.index_file(
                                    Path(result["metadata"]["path"]),
                                    result,
                                )
                                indexed += chunks
                        
                        st.success(f"Indexed {indexed} chunks from {len(results)} files")
                else:
                    st.error("Folder does not exist")
            else:
                st.error("Please enter a folder path")
    
    with col2:
        st.subheader("Index a Single File")
        
        file_path = st.text_input(
            "File Path",
            placeholder="e.g., ~/Downloads/document.pdf",
        )
        
        if st.button("📄 Index File"):
            if file_path:
                path = Path(file_path).expanduser()
                if path.exists():
                    with st.spinner("Indexing..."):
                        result = parser.parse(path)
                        if result["success"]:
                            chunks = indexer.index_file(path, result)
                            st.success(f"Indexed {chunks} chunks")
                        else:
                            st.error(result.get("error", "Failed to parse file"))
                else:
                    st.error("File does not exist")
            else:
                st.error("Please enter a file path")
    
    st.divider()
    
    st.subheader("Danger Zone")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("🗑️ Clear Index", type="secondary"):
            indexer.clear_all()
            st.success("Index cleared")
            st.rerun()
    
    with col_b:
        st.caption("This will remove all indexed documents. This cannot be undone.")


def reindex_all():
    """Reindex all monitored folders."""
    config = get_config()
    parser = get_parser()
    indexer = get_indexer()
    
    total_chunks = 0
    total_files = 0
    
    for folder_path, recursive in config.get_monitored_folders():
        if folder_path.exists():
            results = parser.parse_directory(folder_path, recursive=recursive)
            for result in results:
                if result["success"]:
                    chunks = indexer.index_file(
                        Path(result["metadata"]["path"]),
                        result,
                    )
                    total_chunks += chunks
                    total_files += 1
    
    return total_chunks, total_files


def open_folder(path: Path):
    """Open a folder in the system file browser."""
    import platform
    
    system = platform.system()
    
    try:
        if system == "Windows":
            subprocess.run(["explorer", str(path)])
        elif system == "Darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception as e:
        st.error(f"Could not open folder: {e}")


if __name__ == "__main__":
    main()
