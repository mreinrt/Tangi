# Changelog

## [1.1.0] - 2026-04-03

### Major New Features

#### Online Mode with NVIDIA NIM API
- **Added universal API client** (`OpenAIClient`) supporting NVIDIA NIM, OpenAI, Together AI, DeepSeek
- **Online/Offline toggle button** in status bar - one click to switch between local LLM and cloud API
- **API Base URL configuration** in Preferences - supports any OpenAI-compatible endpoint
- **Test Connection button** to verify API key and endpoint before switching

#### Local LLM Resource Management
- **Auto-unload local model** when switching to online mode (frees 4-6GB RAM)
- **Unload Model option** in File menu - manually free RAM without closing Tangi
- **Persistent model unloading** - cleared from settings so it doesn't auto-load on next startup

#### UI Improvements
- **Window transparency persistence** - slider value saved across sessions
- **Centered response settings buttons** - better layout in Preferences dialog
- **Show/Hide API key toggle** 

#### RAG Enhancements
- **RAG search now uses online API** when in online mode (faster, more stable)
- **Automatic context clearing** to prevent memory buildup

### Bug Fixes
- Fixed missing `live_transparency_change` method causing crash
- Fixed model auto-loading after explicit unload

### New Files
- `utils/openai_api.py` - Universal OpenAI-compatible API client

### 🔄 Modified Files
- `ui/dialogs.py` - Added NVIDIA NIM section, transparency persistence
- `ui/main_window.py` - Online mode toggle, API routing, auto-unload
- `commands/rag_commands.py` - RAG uses online API when available
- `utils/__init__.py` - Export OpenAIClient
- `requirements.txt` - Updated dependencies

---

## [1.0.0] - Before Online Mode (Previous Version)

### Core Features (Pre-Online Mode)
- Local LLM inference with GGUF model support
- RAG (Retrieval Augmented Generation) for codebase indexing
- `/search` command for semantic code search
- `/ds` command for iterative deep search
- SQLite database for chat sessions and history
- Hugging Face CLI integration for model downloads
- Dark/Light theme support
- KV cache management for session performance
- OpenBLAS optimization for CPU inference

### Limitations (Resolved in v1.1.0)
- Local model only - no cloud API option
- Transparency reset on each launch


---

## Upgrade Summary

| Feature | v1.0.0 | v1.1.0 |
|---------|--------|--------|
| **Local LLM** | Yes | Yes |
| **Online API** | No | NVIDIA NIM, OpenAI, etc. |
| **Online/Offline Toggle** | No | Status bar button |
| **Manual Unload** | No | File menu option |
| **Transparency Persistence** | No | Saved across sessions |
| **API Key Storage** | No | Persistent |
| **RAG Search Speed** | Slow (local CPU) | Fast (cloud API option) |

---


### New Settings Added
- `api_base_url` - API endpoint (default: NVIDIA NIM)
- `api_key` - Universal API key storage
- `window_opacity` - Transparency persistence


