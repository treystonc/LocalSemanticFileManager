"""Main Streamlit UI for Socrates."""

import logging
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.ingestion.file_parser import FileParser
from src.indexer.semantic_indexer import Indexer
from src.search.semantic_search import Janitor, SemanticSearch
from src.watcher.file_watcher import FileWatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Socrates - Local Semantic File Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    if "is_indexing" not in st.session_state:
        st.session_state["is_indexing"] = False
    if "index_progress" not in st.session_state:
        st.session_state["index_progress"] = {"files": 0, "chunks": 0, "total_files": 0}
    if "index_log" not in st.session_state:
        st.session_state["index_log"] = []
    if "index_complete" not in st.session_state:
        st.session_state["index_complete"] = False
    if "progress_queue" not in st.session_state:
        st.session_state["progress_queue"] = queue.Queue()


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


def background_reindex(progress_queue: queue.Queue):
    config = get_config()
    parser = get_parser()
    indexer = get_indexer()
    
    total_chunks = 0
    total_files = 0
    all_files = []
    
    for folder_path, recursive in config.get_monitored_folders():
        if folder_path.exists():
            results = parser.parse_directory(folder_path, recursive=recursive)
            all_files.extend(results)
    
    progress_queue.put(("total", len(all_files)))
    
    for i, result in enumerate(all_files):
        file_path = Path(result["metadata"]["path"])
        
        if result["success"]:
            chunks = indexer.index_file(file_path, result)
            total_chunks += chunks
            total_files += 1
            progress_queue.put(("file", str(file_path.name), chunks, i + 1))
        else:
            progress_queue.put(("skip", str(file_path.name), result.get("error", "Unknown error"), i + 1))
    
    progress_queue.put(("done", total_files, total_chunks))


def start_background_reindex():
    init_session_state()
    
    st.session_state["is_indexing"] = True
    st.session_state["index_progress"] = {"files": 0, "chunks": 0, "total_files": 0}
    st.session_state["index_log"] = []
    st.session_state["index_complete"] = False
    st.session_state["progress_queue"] = queue.Queue()
    
    thread = threading.Thread(
        target=background_reindex,
        args=(st.session_state["progress_queue"],),
        daemon=True,
    )
    thread.start()
    st.session_state["index_thread"] = thread


def check_index_progress():
    init_session_state()
    
    if not st.session_state["is_indexing"]:
        return
    
    progress_queue = st.session_state.get("progress_queue")
    if not progress_queue:
        return
    
    try:
        while True:
            msg = progress_queue.get_nowait()
            
            if msg[0] == "total":
                st.session_state["index_progress"]["total_files"] = msg[1]
            elif msg[0] == "file":
                _, filename, chunks, count = msg
                st.session_state["index_progress"]["files"] = count
                st.session_state["index_progress"]["chunks"] += chunks
                st.session_state["index_log"].append(f"✓ {filename} ({chunks} chunks)")
            elif msg[0] == "skip":
                _, filename, error, count = msg
                st.session_state["index_progress"]["files"] = count
                st.session_state["index_log"].append(f"✗ {filename}: {error}")
            elif msg[0] == "done":
                st.session_state["is_indexing"] = False
                st.session_state["index_complete"] = True
                st.session_state["final_files"] = msg[1]
                st.session_state["final_chunks"] = msg[2]
    except queue.Empty:
        pass
    
    if len(st.session_state["index_log"]) > 50:
        st.session_state["index_log"] = st.session_state["index_log"][-50:]


def render_indexing_status():
    init_session_state()
    check_index_progress()
    
    if st.session_state["is_indexing"]:
        progress = st.session_state["index_progress"]
        total = progress.get("total_files", 1)
        current = progress.get("files", 0)
        chunks = progress.get("chunks", 0)
        
        if total > 0:
            pct = min(current / total, 1.0)
            st.progress(pct, text=f"Indexing: {current}/{total} files ({chunks} chunks)")
        else:
            st.progress(0, text="Scanning files...")
        
        with st.expander("📋 Live Log", expanded=False):
            log_text = "\n".join(st.session_state["index_log"][-20:])
            st.code(log_text, language=None)
        
        st.caption("Indexing runs in background. You can navigate to other tabs.")
        time.sleep(0.5)
        st.rerun()
    
    elif st.session_state.get("index_complete"):
        st.success(
            f"✅ Indexing complete! "
            f"{st.session_state.get('final_files', 0)} files, "
            f"{st.session_state.get('final_chunks', 0)} chunks."
        )
        st.session_state["index_complete"] = False


def main():
    init_session_state()
    
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
        
        st.subheader("Reindex")
        
        if st.session_state["is_indexing"]:
            st.button("🔄 Reindex All", disabled=True, help="Indexing in progress...")
        else:
            if st.button("🔄 Reindex All"):
                start_background_reindex()
                st.rerun()
        
        render_indexing_status()
    
    tab1, tab2, tab3 = st.tabs(["🔍 Search", "🧹 Janitor", "📊 Index"])
    
    with tab1:
        render_search_tab()
    
    with tab2:
        render_janitor_tab()
    
    with tab3:
        render_index_tab()


def render_search_tab():
    st.header("🔍 Search")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "Search your files:",
            placeholder="e.g., 'La Trobe' or 'quarterly report'",
            label_visibility="collapsed",
        )
    
    with col2:
        search_mode = st.radio(
            "Mode",
            ["Smart", "Semantic", "Keyword"],
            horizontal=True,
            label_visibility="collapsed",
            captions=["Hybrid", "Meaning only", "Exact match"],
        )
    
    mode_map = {"Smart": "hybrid", "Semantic": "semantic", "Keyword": "keyword"}
    selected_mode = mode_map[search_mode]
    
    n_results = st.slider("Results", 1, 20, 5, key="search_results")
    
    if query:
        with st.spinner("Searching..."):
            search = get_search()
            results = search.search(query, n_results=n_results, mode=selected_mode)
        
        if results:
            st.subheader(f"Found {len(results)} results")
            
            for i, result in enumerate(results, 1):
                match_icons = ""
                if result.get("filename_match"):
                    match_icons += "📁 "
                elif result.get("keyword_match"):
                    match_icons += "📄 "
                
                with st.expander(
                    f"{i}. {match_icons}{result['filename']} "
                    f"(Score: {result['relevance_score']:.2f})",
                    expanded=(i == 1),
                ):
                    col_a, col_b = st.columns([3, 1])
                    
                    with col_a:
                        st.markdown("**Snippet:**")
                        st.text(result["snippet"])
                        
                        st.markdown("**Path:**")
                        st.code(result["file_path"])
                        
                        match_info = []
                        if result.get("filename_match"):
                            match_info.append("Filename match (+0.5)")
                        if result.get("keyword_match"):
                            match_info.append("Content match (+0.3)")
                        if match_info:
                            st.caption(" | ".join(match_info))
                    
                    with col_b:
                        if st.button("📂 Open", key=f"open_{i}"):
                            open_folder(Path(result["file_path"]).parent)
                        
                        st.metric("Score", f"{result['relevance_score']:.2f}")
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
        
        if st.session_state["is_indexing"]:
            st.button("📁 Index Folder", disabled=True, help="Indexing in progress...")
        else:
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
        
        if st.session_state["is_indexing"]:
            st.button("📄 Index File", disabled=True, help="Indexing in progress...")
        else:
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
        if st.session_state["is_indexing"]:
            st.button("🗑️ Clear Index", type="secondary", disabled=True, help="Indexing in progress...")
        else:
            if st.button("🗑️ Clear Index", type="secondary"):
                indexer.clear_all()
                st.success("Index cleared")
                st.rerun()
    
    with col_b:
        st.caption("This will remove all indexed documents. This cannot be undone.")


def open_folder(path: Path):
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
