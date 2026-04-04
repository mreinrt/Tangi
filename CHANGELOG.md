# Changelog

## [1.2.0] - 2026-04-05

### Major New Features

#### Online Mode Improvements
- **Response repetition detection disabled** while online mode is active - prevents false truncation of valid responses
- **Online mode session persistence** - database now stores online provider and model for each session
- **Session string search** - find in chat bar in status bar with Enter-to-search and X-to-clear

#### UI Improvements
- **Online/Offline toggle button repositioned** - moved from status bar to top-right corner of menu bar
- **Session management enhancements** - Load Session and Manage Sessions dialogs now display online/offline mode with provider details

### Bug Fixes
- **Transparency event handling bug** - fixed issue where transparency would decrease by 1% every time Preferences dialog was opened
- **Online mode session creation** - sessions now correctly save online mode status when toggled
- **Session deletion column index mismatch** - fixed after adding Mode column to session tables
- **Load Session dialog unpacking error** - now properly handles new session format with online mode columns
- **Old session backward compatibility** - gracefully handles sessions created before online mode columns were added

### Database Schema Updates
- Added `online_mode`, `online_provider`, `online_model` columns to sessions table
- Backward compatible with existing sessions

---

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


