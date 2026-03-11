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
│   └── models/                   # Downloaded embedding model cache
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
│   │   └── semantic_search.py    # SemanticSearch, Janitor (Module D)
│   └── utils/
│       ├── __init__.py
│       └── text_chunker.py       # TextChunker utility
├── ui/
│   └── app.py                    # Streamlit UI
├── config/
│   ├── settings.yaml             # Main configuration
│   └── rules.json                # Janitor rules (AND/OR logic)
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_indexer.py
│   └── test_search.py
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
  - `remove_document(file_path)` - Remove from index
  - `get_stats()` - Database statistics
- **Chunking:** 500-char chunks with 50-char overlap
- **Storage:** `.socrates/db/`

### Module C: Real-Time Watcher (`src/watcher/file_watcher.py`)

- **Class:** `FileWatcher`, `DebouncedEventHandler`
- **Purpose:** Monitor directories for file changes
- **Debounce:** 2 seconds (configurable)
- **Key methods:**
  - `start()` - Begin watching
  - `stop()` - Stop watching
  - `add_directory(path, recursive)` - Add watch target

### Module D: Semantic Search & Janitor (`src/search/semantic_search.py`)

- **Classes:** `SemanticSearch`, `RuleEvaluator`, `Janitor`
- **Purpose:** Search files by meaning + auto-organization
- **Key methods:**
  - `SemanticSearch.search(query, n_results)` - Natural language search
  - `SemanticSearch.search_by_keyword(keywords, operator)` - AND/OR keyword search
  - `Janitor.suggest_organization(file_path)` - Get move suggestion
  - `Janitor.organize_file(file_path, target, dry_run)` - Move file

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
  auto_move_enabled: false      # false = suggest only
  require_confirmation: true

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
      "name": "Rule Name",
      "conditions": {
        "operator": "OR",          // "AND" or "OR"
        "keywords": ["keyword1", "keyword2"]
      },
      "similarity_threshold": 0.80,
      "target_folder": "~/Documents/Category"
    }
  ]
}
```

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
python -m src.main --help
python -m src.main index ~/Documents -r
python -m src.main search "quarterly report"
python -m src.main stats
python -m src.main ui

# Run Streamlit UI directly
streamlit run ui/app.py

# Run tests
pytest tests/
```

## Development Guidelines

1. **No comments in code** unless explicitly requested
2. **Offline-first:** Never add external API calls
3. **Config-driven:** All paths, thresholds, and settings should be configurable
4. **Error handling:** Gracefully handle corrupted/encrypted files
5. **Logging:** Use Python logging module with appropriate levels

## Known Limitations

- Large files (>10MB by default) are skipped
- Binary files (.exe, .dll, etc.) are not indexed
- Model download requires internet connection on first run (then cached)
- Windows-only path handling currently (can be extended)

## When Adding New Features

1. Update `config/settings.yaml` if adding new configuration
2. Update `AGENTS.md` if adding new modules or changing architecture
3. Add tests in `tests/` directory
4. Follow existing code patterns and naming conventions
5. Run `pytest` before committing
