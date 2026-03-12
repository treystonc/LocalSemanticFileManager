# AGENTS.md

> Context file for AI coding agents working on the Socrates project.

## Project Overview

**Name:** Socrates - Local Semantic File Manager

**Goal:** A background utility that monitors specific folders (Downloads, Documents), extracts text from files, indexes them into a local vector database for semantic search, and provides an "Auto-Janitor" feature to suggest/perform file organization.

**Key Constraint:** 100% Offline. No external LLM APIs. All embeddings must be generated on the local CPU.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| File Monitoring | watchdog |
| Text Extraction | PyMuPDF (PDFs), python-docx (Word), pandas/openpyxl (Excel) |
| Embeddings | sentence-transformers (Model: all-MiniLM-L6-v2) |
| Vector Database | ChromaDB (Persistent local storage) |
| UI | Streamlit (Web-based local UI) |
| Config Format | YAML (settings), JSON (rules) |

## Project Structure

```
G:\Projects\LocalSemanticFileManager\
├── .socrates/                    # Hidden app data folder
│   ├── db/                       # ChromaDB persistent storage
│   ├── models/                   # Downloaded embedding model cache
│   └── pending_moves.json        # Auto-move pending acknowledgements
├── src/
│   ├── __init__.py
│   ├── config.py                 # Config loader (YAML/JSON)
│   ├── main.py                   # CLI entry point
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── file_parser.py        # FileParser class (Module A)
│   ├── indexer/
│   │   ├── __init__.py
│   │   └── semantic_indexer.py   # Indexer class (Module B)
│   ├── watcher/
│   │   ├── __init__.py
│   │   └── file_watcher.py       # FileWatcher class (Module C)
│   ├── search/
│   │   ├── __init__.py
│   │   └── semantic_search.py    # SemanticSearch, RuleEvaluator, Janitor (Module D)
│   ├── janitor/
│   │   ├── __init__.py
│   │   └── auto_move_manager.py  # AutoMoveManager (Module E)
│   └── utils/
│       ├── __init__.py
│       └── text_chunker.py       # TextChunker utility
├── ui/
│   └── app.py                    # Streamlit UI
├── config/
│   ├── settings.yaml             # Main configuration
│   └── rules.json                # Janitor rules
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_indexer.py
│   └── test_search.py
├── start.bat                     # Windows start script
├── start.ps1                     # PowerShell start script
├── requirements.txt
├── pyproject.toml
├── README.md
└── AGENTS.md                     # This file
```

## Core Modules

### Module A: Ingestion Engine (`src/ingestion/file_parser.py`)

- **Class:** `FileParser`
- **Purpose:** Extract text from files
- **Supported formats:** `.pdf`, `.docx`, `.xlsx`, `.txt`, `.md`
- **Key method:** `parse(file_path) -> dict` with `text`, `metadata`, `success`, `error` keys
- **Libraries:** PyMuPDF (`fit`), python-docx, pandas/openpyxl

### Module B: Semantic Indexer (`src/indexer/semantic_indexer.py`)

- **Class:** `Indexer`
- **Purpose:** Convert text to vectors and store in ChromaDB
- **Key methods:**
  - `index_document(text, file_path, metadata)` - Index a document
  - `search(query, n_results)` - Semantic search
  - `search_by_text(keyword)` - Keyword search in content
  - `search_by_filename(filename)` - Search by filename
  - `remove_document(file_path)` - Remove from index
  - `get_stats()` - Database statistics
  - `get_all_file_paths()` - Get unique file paths
  - `reindex_all(parser)` - Re-index all files
- **Chunking:** 500-char chunks with 50-char overlap
- **Storage:** `.socrates/db/`
- **Metadata:** Adds `normalized_filename` for fuzzy filename matching

### Module C: Real-Time Watcher (`src/watcher/file_watcher.py`)

- **Class:** `FileWatcher`, `DebouncedEventHandler`
- **Purpose:** Monitor directories for file changes
- **Debounce:** 2 seconds (configurable)
- **Key methods:**
  - `start()` - Begin watching
  - `stop()` - Stop watching
  - `add_directory(path, recursive)` - Add watch target
- **Integration:** Can use `auto_move_manager` for automatic file organization

### Module D: Semantic Search (`src/search/semantic_search.py`)

- **Classes:** `SemanticSearch`, `RuleEvaluator`, `Janitor`
- **Purpose:** Search files by meaning + manual organization
- **Search Modes:**
  - `hybrid` - Combines semantic, keyword, and filename matching
  - `semantic` - Pure vector similarity search
  - `keyword` - Exact substring match in content
  - `filename` - Token-based filename matching
- **Key methods:**
  - `SemanticSearch.search(query, n_results, mode)` - Search with mode selection
  - `SemanticSearch.search_by_filename(query, n_results)` - Filename-only search
  - `SemanticSearch.search_by_keyword(keywords, operator)` - AND/OR keyword search
  - `Janitor.evaluate_file(file_path)` - Evaluate file against rules
  - `Janitor.suggest_organization(file_path)` - Get move suggestion
  - `Janitor.organize_file(file_path, target, dry_run)` - Move file
  - `Janitor.get_all_suggestions()` - Get suggestions for all files

### Module E: Auto-Move Manager (`src/janitor/auto_move_manager.py`)

- **Class:** `AutoMoveManager`
- **Purpose:** Automatic file organization based on rules
- **Key methods:**
  - `evaluate_and_move(file_path)` - Evaluate and auto-move if configured
  - `get_pending_moves()` - Get moves awaiting acknowledgement
  - `get_acknowledged_moves()` - Get acknowledged moves (history)
  - `acknowledge_move(move_id)` - Acknowledge a single move
  - `acknowledge_all()` - Acknowledge all pending moves
  - `clear_acknowledged()` - Clear acknowledged moves from history
- **Persistence:** Moves saved to `.socrates/pending_moves.json`

## Configuration

### settings.yaml Structure

```yaml
watcher:
  monitored_folders:
    - path: ~/Downloads
      recursive: false
    - path: ~/Documents
      recursive: true
  debounce_seconds: 2

file_filtering:
  max_file_size_mb: 10
  skip_extensions: [.exe, .dll, .zip, ...]
  supported_extensions: [.pdf, .docx, .xlsx, .txt, .md]

janitor:
  auto_move_enabled: false      # Global default for auto-move
  auto_move_threshold: 0.85      # Global default threshold
  require_confirmation: true
  summary_on_auto_move: true
  pending_moves_file: .socrates/pending_moves.json

embedding:
  model: all-MiniLM-L6-v2
  chunk_size: 500
  chunk_overlap: 50

database:
  path: .socrates/db
```

### rules.json Structure

```json
{
  "rules": [
    {
      "name": "Finance Documents",
      "conditions": {
        "operator": "OR",
        "keywords": ["invoice", "receipt", "financial", "budget", "expense"]
      },
      "similarity_threshold": 0.80,
      "target_folder": "~/Documents/Finance",
      "auto_move": true,
      "auto_move_threshold": 0.90
    }
  ],
  "defaults": {
    "auto_move": false,
    "auto_move_threshold": 0.85
  }
}
```

**Rule Fields:**
- `name` - Rule display name
- `conditions.keywords` - Keywords to match
- `conditions.operator` - "AND" or "OR" logic
- `similarity_threshold` - Minimum confidence to suggest move
- `target_folder` - Destination folder for organized files
- `auto_move` - Enable automatic moving (requires threshold check)
- `auto_move_threshold` - Minimum confidence for auto-move (overrides global)

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
python -m src.main --help
python -m src.main index ~/Documents -r
python -m src.main search "quarterly report"
python -m src.main search "la trobe" -m filename    # Filename-only search
python -m src.main search "invoice" -m keyword     # Keyword search
python -m src.main stats
python -m src.main reindex                         # Re-index with new metadata
python -m src.main debug-move ~/Download/file.txt   # Debug auto-move
python -m src.main watch                           # Start file watcher

# Run UI (includes watcher controls)
streamlit run ui/app.py

# Or use start scripts (recommended)
start.bat           # Windows batch
start.ps1          # PowerShell
```

## UI Features

### Search Tab
- **Smart mode** - Hybrid search (semantic + keyword + filename)
- **Semantic mode** - Pure meaning-based search
- **Keyword mode** - Exact content match
- **Filename mode** - Token-based filename matching

### Janitor Tab
- View configured rules
- Get organization suggestions
- Manual file moving with dry-run option

### Index Tab
- Index individual files or folders
- Reindex all files
- Clear index

### Notifications Tab
- View pending auto-move acknowledgements
- Acknowledge completed moves
- View move history

### Sidebar
- Monitored folders list
- Database statistics
- Reindex button
- File Watcher controls (Start/Stop)

## Development Guidelines

1. **No comments in code** unless explicitly requested
2. **Offline-first:** Never add external API calls
3. **Config-driven:** All paths, thresholds, and settings should be configurable
4. **Error handling:** Gracefully handle corrupted/encrypted files
5. **Logging:** Use Python logging module with appropriate levels
6. **Batching:** When fetching large datasets from ChromaDB, use batched fetches (500 at a time) to avoid SQLite variable limits

## Known Limitations

- Large files (>10MB by default) are skipped
- Binary files (.exe, .dll, etc.) are not indexed
- Model download requires internet connection on first run (then cached)
- Windows-only path handling currently (can be extended)
- Empty files (0 bytes) cannot be indexed or evaluated for auto-move

## When Adding New Features

1. Update `config/settings.yaml` if adding new configuration
2. Update `config/rules.json` schema if adding new rule fields
3. Update `AGENTS.md` if adding new modules or changing architecture
4. Add tests in `tests/` directory
5. Follow existing code patterns and naming conventions
6. Run `pytest` before committing
