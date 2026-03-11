# Socrates - Local Semantic File Manager

A privacy-first, 100% offline semantic file manager that monitors your folders, indexes documents for natural language search, and helps organize files automatically.

## Features

- **Semantic Search**: Find files by meaning, not just keywords
- **Real-Time Monitoring**: Automatically indexes new files in monitored folders
- **Auto-Janitor**: Suggests or performs file organization based on content
- **100% Offline**: No internet required after initial model download
- **Multi-Format Support**: PDF, Word, Excel, Text, Markdown

## Requirements

- Python 3.10+
- ~500MB disk space (for model + database)
- 4GB+ RAM recommended

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd LocalSemanticFileManager

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Launch the Web UI

```bash
streamlit run ui/app.py
```

Or using the CLI:

```bash
python -m src.main ui
```

### Index Files

```bash
# Index a single file
python -m src.main index ~/Documents/report.pdf

# Index a directory recursively
python -m src.main index ~/Documents -r
```

### Search Files

```bash
python -m src.main search "quarterly financial report"
```

### Start File Watcher

```bash
python -m src.main watch
```

## Configuration

### Monitored Folders (`config/settings.yaml`)

```yaml
watcher:
  monitored_folders:
    - path: ~/Downloads
      recursive: false
    - path: ~/Documents
      recursive: true
```

### Janitor Rules (`config/rules.json`)

```json
{
  "rules": [
    {
      "name": "Finance Documents",
      "conditions": {
        "operator": "OR",
        "keywords": ["invoice", "receipt", "financial"]
      },
      "similarity_threshold": 0.80,
      "target_folder": "~/Documents/Finance"
    }
  ]
}
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `index <path>` | Index a file or directory |
| `watch` | Start real-time file monitoring |
| `search <query>` | Search indexed files |
| `ui` | Launch the Streamlit web UI |
| `stats` | Show database statistics |
| `clear` | Clear the index |

## Project Structure

```
socrates/
├── src/
│   ├── config.py           # Configuration loader
│   ├── main.py             # CLI entry point
│   ├── ingestion/          # File parsing (Module A)
│   ├── indexer/            # Vector indexing (Module B)
│   ├── watcher/            # File monitoring (Module C)
│   ├── search/             # Search & Janitor (Module D)
│   └── utils/              # Utilities
├── ui/
│   └── app.py              # Streamlit UI
├── config/
│   ├── settings.yaml       # Main configuration
│   └── rules.json          # Janitor rules
└── tests/                  # Test suite
```

## Supported File Types

| Extension | Library |
|-----------|---------|
| `.pdf` | PyMuPDF |
| `.docx` | python-docx |
| `.xlsx` | pandas + openpyxl |
| `.txt` | Built-in |
| `.md` | Built-in |

## Privacy

- All processing happens locally on your machine
- No data is sent to external servers
- Embeddings are generated using a local model
- Database is stored in `.socrates/db/`

## License

MIT
