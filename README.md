# Tangi

**Hardware-agnostic, auto-optimizing AI assistant with RAG for codebases and optional cloud API acceleration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Optimized: OpenBLAS](https://img.shields.io/badge/Optimized-OpenBLAS-green.svg)](https://www.openblas.net/)
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)](https://github.com/mreinrt/Tangi/releases)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)](https://github.com/mreinrt/Tangi)
[![RAG](https://img.shields.io/badge/RAG-Supported-brightgreen.svg)](https://github.com/mreinrt/Tangi)

---

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Security & Privacy](#security--privacy)
- [Features](#features)
  - [Dual-Mode Operation](#dual-mode-operation)
  - [Hardware-Aware Optimization](#hardware-aware-optimization)
  - [RAG System (Code Intelligence)](#rag-system-code-intelligence)
  - [Code Indexing](#code-indexing)
  - [Interface](#interface)
  - [Session Management](#session-management)
  - [Performance](#performance)
  - [Cloud API Support](#cloud-api-support)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Local Mode (Offline)](#local-mode-offline)
  - [Online Mode (Cloud API)](#online-mode-cloud-api)
- [RAG Workflow](#rag-workflow-when-to-use-which-command)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Commands](#commands)
  - [General](#general)
  - [Hugging Face](#hugging-face)
  - [RAG](#rag)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Performance Guidelines](#performance-guidelines)
- [Version History](#version-history)
- [Recent Updates](#recent-updates)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Support](#support)
- [Donations](#donations)

---

## Overview

Tangi is an AI assistant designed for developers who want **fast, hardware-aware inference** and **code-aware answers**. It automatically detects system capabilities (CPU, threads, memory, BLAS backend) and tunes itself for optimal performance.

It includes a built-in **Retrieval-Augmented Generation (RAG)** system that indexes your codebase, enabling accurate, context-grounded responses.

**Latest:** v1.3.0 adds Session Prompts list (jump to any user message with hover over preview), full database session search with exact word matching, Load Session integrated into Load/Manage Sessions, and UI layout improvements (search bar moved to top menu, online toggle returned to status bar). Still supports NVIDIA NIM API (40 requests/min free tier).

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 8 GB | 16 GB |
| **Storage** | 10 GB | 20 GB (for multiple models) |
| **Python** | 3.12+ | 3.12+ |
| **OS** | Linux, Windows, macOS | Linux (Gentoo/Debian optimized) |
| **Internet** | Optional (offline mode) | Required for online mode |

---

## Security & Privacy

- **Local Mode**: All processing happens on your machine. No data leaves your system.
- **Online Mode**: Your prompts are sent to your configured API provider. Choose providers with privacy policies you trust.
- **API Keys**: Stored locally in Qt's secure settings. Never transmitted except to your chosen API endpoint.
- **Chat History**: Stored unencrypted locally in `~/.Tangi/chatlogs.db`. Encrypted storage planned for future release.

---

## Features

![Main Window](media/Tangi.png)

*Main widget LLM Inference Demo*

### Dual-Mode Operation

| Mode | Description | Best For |
|------|-------------|----------|
| **Offline (Local)** | Run GGUF models on your hardware using llama-cpp-python | Privacy, air-gapped environments, no internet |
| **Online (Cloud)** | NVIDIA NIM API with OpenAI-compatible endpoints | Speed, complex reasoning, reduced local resource usage |

### Hardware-Aware Optimization
- Automatic detection of physical vs logical CPU cores
- NUMA-aware scheduling (multi-socket systems)
- OpenBLAS auto-configuration
- Dynamic batch sizing based on RAM
- Optional memory locking to prevent swapping
- **Auto-unload local model when switching to online mode** (frees 4-6GB RAM)

### RAG System (Code Intelligence)

| Feature | Command | Use Case |
|--------|---------|----------|
| **Code Indexing** | `/index /path` | Index a codebase for semantic search |
| **Standard RAG** | `/search "question"` | Fast, single-pass retrieval for direct questions |
| **Deep Search** | `/ds "question"` | Multi-step iterative search for complex, cross-file analysis |

### Code Indexing
- Semantic search across codebases
- Multi-project support
- Automatic ignore rules (venv, node_modules, build artifacts)
- Chunk preview before querying

### Interface
- Markdown and plain chat modes
- Session persistence
- Theme support (dark/light)
- KV cache for faster repeated queries
- **Window transparency persistence**
- **Session Prompts list** - Jump to any user message in current session
- **Session Search** - Full database search across all session names and message content with exact word matching
- **Load Session integrated into Manage Sessions** - Load any session directly from the management dialog

### Session Management
- **Session Prompts** - List all user prompts in current session with jump-to functionality
- **Session Search** - Search across your entire chat history database by session name or message content
- **Load Session** - Load any saved session from the Manage Sessions dialog
- **Session persistence** - Automatically saves conversation history with local/online mode tracking

### Performance
- OpenBLAS acceleration
- Thread coordination (avoids BLAS/LLM contention)
- Automatic token budgeting
- Context window management

### Cloud API Support
- **NVIDIA NIM** (free tier: 40 requests/minute, no credit card)
- OpenAI (GPT-4o, GPT-4o-mini)
- Together AI
- DeepSeek
- Any OpenAI-compatible endpoint

---

## Installation

### Requirements
- Python 3.12+
- 8 GB RAM minimum (16 GB recommended)
- OpenBLAS (recommended)
- ~10 GB disk space for models
- **Optional:** NVIDIA API key for online mode

### Setup

```
git clone https://github.com/mreinrt/Tangi.git
cd Tangi

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

Install dependencies:

```
# OpenBLAS
sudo apt install libopenblas-dev        # Debian/Ubuntu
# or
sudo emerge -av sci-libs/openblas       # Gentoo

pip install -r requirements.txt

# Rebuild llama-cpp-python with OpenBLAS
pip uninstall llama-cpp-python -y
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" \
  pip install llama-cpp-python==0.3.16 --no-cache-dir
```

---

## Quick Start

```
python -m Tangi
```

### Local Mode (Offline)

1. **Load a model** (File → Load Model or select a .gguf file)
2. **Download the embedding model** (one-time setup): `/get-rag`
3. **Index your codebase**: `/index /path/to/your/project`
4. **Select the indexed codebase** (Manage Index → Select CodeBase)
5. **Ask questions!**

### Online Mode (Cloud API)

1. **Get a free NVIDIA API key** from [build.nvidia.com](https://build.nvidia.com/models)
2. **Go to Preferences** → NVIDIA NIM Online Mode
3. **Enter your API key** and Base URL (default: `https://integrate.api.nvidia.com/v1`)
4. **Select a model** (recommended: `mistralai/mistral-nemotron`)
5. **Click Test Connection** to verify
6. **Toggle Online Mode** in the status bar (bottom right)
7. **The local model auto-unloads** to free RAM
8. **Chat with cloud acceleration!**

---

## RAG Workflow: When to Use Which Command

### Step 1: Make sure to download a local RAG model by using /get-rag or store one inside of ~/.cache/huggingface/hub/. You can also select from a local RAG model by clicking File > Manage Index and clicking "Manage RAG Models".

### Step 2: Index Your Codebase

```
/index /home/user/projects/codebase
```

### Step 3: Select Your Active Codebase
- Open **Manage Index** (File → Manage Index)
- Select your indexed project
- Click **Select CodeBase**

### Step 4: Choose the Right Search Command

#### Use /search for:
- Direct, factual questions
- Single file lookups
- Finding specific functions or classes
- Simple queries
- **Now supports online API for faster responses**

#### Use /ds for:
- Complex, multi-file questions
- System architecture understanding
- Cross-module dependencies
- Troubleshooting complex issues

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus find in chat bar |
| `F3` | Find next match (when find bar is active) |
| `Shift+F3` | Find previous match |
| `Esc` | Close find bar |
| `Ctrl+U` | Unload current model |
| `Enter` | Send message (main input) |
| `Shift+Enter` | New line in message input |

---

## Commands

### General
| Command | Description |
|--------|-------------|
| /about | Application information |
| /help or /commands | Show all commands |

### Hugging Face
| Command | Description |
|--------|-------------|
| /hf login | Authenticate |
| /hf download MODEL | Download model |
| /hf search QUERY | Search models |
| /hf info MODEL | Model details |
| /hf cache | Cache info |

### RAG
| Command | Description |
|--------|-------------|
| /index PATH | Index codebase |
| /search QUERY | Fast retrieval (uses online API if available) |
| /ds QUERY | Deep search |
| /get-rag | Download embeddings |
| /remove-index PATH | Remove index |
| /clear | Clear context |
| /rag-status | Status |
| /cache-info | Cache stats |

---

## Architecture

### Standard RAG (Offline)
Query → Retrieve → Context → Local LLM → Answer

### Online RAG
Query → Retrieve → Context → Cloud API (NVIDIA NIM) → Answer

### Deep Search
Query → Retrieve → Analyze → Refine → Retrieve → ... → Answer

---

## Configuration

### Memory Usage
Default: 85% RAM (adjustable in Preferences)

### Online Mode Settings

| Setting | Default | Description |
|---------|---------|-------------|
| API Base URL | `https://integrate.api.nvidia.com/v1` | Endpoint for cloud API |
| Model | `mistralai/mistral-nemotron` | Best for coding (92.68% HumanEval) |
| API Key | User-provided | Get from build.nvidia.com |

### Model Settings

```
optimal_settings = {
    'n_threads': auto-detected,
    'n_batch': auto-optimized,
    'use_mlock': based on system RAM,
}
```

---

## Troubleshooting

### Common Issues

#### Model won't load
- Ensure you have enough free RAM (8GB minimum, 16GB recommended)
- Check that the file is a valid GGUF format
- Verify file permissions

#### Online mode connection fails
- Check your API key in Preferences
- Verify internet connection
- Ensure the API base URL is correct

#### RAG search returns no results
- Make sure you've indexed your codebase: `/index /path/to/code`
- Verify an embedding model is installed: `/get-rag`
- Check that you've selected an active codebase in Manage Index

#### High memory usage
- Unload the local model when using online mode (File → Unload Model)
- Reduce context size in Preferences
- Clear chat history periodically

---

## Performance Guidelines

| System | Threads | Batch | Context |
|-------|--------|------|--------|
| 2–4 cores | = cores | 64–128 | 8K–16K |
| 4–8 cores | cores +25% | 128–256 | 16K–32K |
| 8+ cores | 80–100% | 256–512 | 32K–128K |

### Online Mode Performance

| Provider | Free Tier | Speed | Best For |
|----------|-----------|-------|----------|
| **NVIDIA NIM** | 40 requests/min | 1-3 seconds | Coding, general use |
| **OpenAI** | Requires payment method | 1-3 seconds | General purpose |
| **Together AI** | Free credits | 1-3 seconds | Various open models |

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

| Version | Release Date | Highlights |
|---------|--------------|------------|
| v1.3.0 | 2026-04-06 | Session Prompts list, full database session search, Load Session in Manage Sessions, UI layout improvements |
| v1.2.0 | 2025-04-05 | Session persistence, find in chat, transparency fix |
| v1.1.0 | 2026-04-03 | NVIDIA NIM API, online mode |
| v1.0.0 | 2026-03-20 | Initial release |

---

## Recent Updates

### v1.3.0 (Current Stable)

#### Added
- **Session Prompts list** - Button next to search bar showing all user prompts in current session with jump-to functionality (double-click or button)
- **Full database session search** - Search across all session names and message content with exact word matching
- **Search results dialog** - Displays matching sessions with details, model info, message count, and message preview tooltips
- **Auto-highlight on load** - Search term automatically highlighted in chat when loading a session from search results

#### Changed
- **Swapped Online/Offline toggle with Search Input** - Search bar moved to top-right menu bar, Online toggle returned to status bar
- **Load Session integrated into Load/Manage Sessions** - Removed standalone Load Session from File menu; now accessible via "Load Selected" button in Manage Sessions dialog
- **Session management dialog** - Added Search Sessions button and Load Selected button for unified session management

---

### v1.2.0

#### Added
- **Session string search** - Find in chat bar in status bar (Ctrl+F, Enter to search, X to clear)
- **Online mode session persistence** - Database now stores online provider and model for each session
- **Model unload option** - File menu option to unload local model and free RAM
- **Auto-unload local model** - Automatically unloads when switching to online mode (with optional "Don't ask again")

#### Changed
- **Online/Offline toggle button** - Repositioned from status bar to top-right corner of menu bar
- **Session management** - Load Session and Manage Sessions dialogs now show online/offline mode with provider details
- **Response repetition detection** - Disabled while online mode is active to prevent false truncation

#### Fixed
- **Transparency event handling bug** - Fixed issue where transparency would decrease by 1% every time Preferences dialog was opened
- **Online mode session creation** - Sessions now correctly save online mode status when toggled
- **Session deletion column index mismatch** - Fixed after adding Mode column to session tables
- **Load Session dialog unpacking error** - Now properly handles new session format

---

### v1.1.0

#### Added
- NVIDIA NIM API integration with online/offline toggle
- Auto-unload local model when switching to online mode
- Window transparency persistence across sessions
- API Base URL configuration in preferences
- Universal OnlineAPIClient (supports any OpenAI-compatible endpoint)

#### Changed
- RAG search now uses online API when available (faster)
- Centered response settings buttons in preferences

#### Fixed
- Missing `live_transparency_change` method

---

### v1.0.0 (Initial Release)

- Local LLM inference with GGUF model support
- RAG (Retrieval Augmented Generation) for codebase indexing
- `/search` and `/ds` commands for code intelligence
- SQLite database for chat sessions
- Hugging Face CLI integration
- Dark/Light theme support
- OpenBLAS optimization

---


## License

MIT License.

---

## Acknowledgments

- llama-cpp-python  
- sentence-transformers  
- OpenBLAS  
- NVIDIA NIM for free API access

---

## Support

GitHub Issues for bugs and requests.

---

## Donations

BTC: 3GtCgHhMP7NTxsdNjcDs7TUNSBK6EXoAzz  
ETH: 0x5f1ed610a96c648478a775644c9244bf4e78631e  

---

Built by Michael Reinert
