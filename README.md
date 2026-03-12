# Socrates - Local Semantic File Manager

A privacy-first, 100% offline semantic file manager that monitors your folders, indexes documents for natural language search, and helps organize files automatically.

## Features

- **Semantic Search**: Find files by meaning, not just keywords
- **Multiple Search Modes**: Smart (hybrid), Semantic, Keyword, Filename
- **Real-Time Monitoring**: Automatically indexes new files in monitored folders
- **Auto-Janitor**: Automatically organizes files based on configurable rules
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
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Using Start Scripts (Recommended)

```bash
# Windows - double-click start.bat
# Or run PowerShell:
.\start.ps1
```

This will start both the File Watcher and Streamlit UI.

### Manual Launch

```bash
# Start File Watcher (runs in background)
python -m src.main watch

# In another terminal, start Streamlit UI
streamlit run ui/app.py
```

### Index Files

```bash
# Index a single file
python -m src.main index ~/Documents/report.pdf

# Index a directory recursively
python -m src.main index ~/Documents -r

# Re-index all files (after updating rules or configuration)
python -m src.main reindex
```

### Search Files

```bash
# Smart search (hybrid - semantic + keyword + filename)
python -m src.main search "quarterly financial report"

# Filename-only search
python -m src.main search "invoice" -m filename

# Keyword search (exact content match)
python -m src.main search "invoice" -m keyword

# Semantic search (meaning-based)
python -m src.main search "la trobe" -m semantic
```

### Debug Auto-Move

```bash
# See why a file would/wouldn't be auto-moved
python -m src.main debug-move ~/Download/invoice.pdf
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

**Rule Options:**
- `auto_move`: Set to `true` to automatically move files matching this rule
- `auto_move_threshold`: Minimum confidence (0-1) required for auto-move
- `target_folder`: Where matched files should be moved

## CLI Commands

| Command | Description |
|---------|-------------|
| `index <path>` | Index a file or directory |
| `index <path> -r` | Index directory recursively |
| `watch` | Start real-time file monitoring |
| `search <query>` | Search indexed files (hybrid mode) |
| `search <query> -m <mode>` | Search with specific mode (hybrid/semantic/keyword/filename) |
| `reindex` | Re-index all files with updated metadata |
| `debug-move <path>` | Debug auto-move evaluation for a file |
| `ui` | Launch the Streamlit web UI |
| `stats` | Show database statistics |
| `clear` | Clear the index |

## UI Features

### Search Tab
- Smart (hybrid), Semantic, Keyword, and Filename search modes
- View relevance scores and match types

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
- File Watcher controls (Start/Stop)

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
