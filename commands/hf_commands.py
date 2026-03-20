"""
Hugging Face CLI integration commands
"""

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from PyQt6.QtCore import QTimer

from Tangi.commands.base import Command

logger = logging.getLogger(__name__)

# Check if huggingface_hub is available
try:
    from huggingface_hub import HfApi, login, whoami, hf_hub_download, snapshot_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logger.warning("huggingface_hub not installed. /hf command will be limited.")


class HFCommand(Command):
    """/hf - Hugging Face CLI integration"""
    
    def __init__(self, parent):
        super().__init__("hf", "Hugging Face CLI integration (login, download, search, etc.)", parent)
        self.subcommands = {
            "login": self.hf_login,
            "whoami": self.hf_whoami,
            "logout": self.hf_logout,
            "download": self.hf_download,
            "list": self.hf_list,
            "ls": self.hf_list,  # Alias
            "info": self.hf_info,
            "search": self.hf_search,
            "cache": self.hf_cache_info,
            "env": self.hf_env,
            "help": self.show_help,
        }
    
    def execute(self, args):
        """Execute HF command with arguments"""
        if not HF_AVAILABLE:
            self.parent.append_command_output(
                "⚠️ Hugging Face Hub not installed.\n\n"
                "Install it with:\n"
                "```bash\npip install huggingface_hub\n```"
            )
            return
        
        args = args.strip()
        
        # Show help if no arguments
        if not args or args == "help":
            self.show_help()
            return
        
        # Parse command
        parts = args.split()
        cmd = parts[0].lower()
        sub_args = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        if cmd in self.subcommands:
            try:
                self.subcommands[cmd](sub_args)
            except Exception as e:
                self.parent.append_command_output(f"Error: {str(e)}")
                logger.error(f"HF command error: {e}")
        else:
            self.parent.append_command_output(f"Unknown HF command: {cmd}\nType /hf help for available commands")
    
    def show_help(self, args=""):
        """Show HF command help"""
        help_text = """
Hugging Face CLI Integration

Available Commands:
  /hf login                 - Log in to Hugging Face Hub
  /hf whoami                - Show current user
  /hf logout                - Log out
  /hf download MODEL_ID [file] - Download a model or specific file
  /hf list [models|datasets|spaces] - List popular items
  /hf info MODEL_ID         - Show model information
  /hf search QUERY          - Search for models
  /hf cache                 - Show cache information
  /hf env                   - Show environment info

Examples:
  /hf download gpt2
  /hf download meta-llama/Llama-2-7b config.json
  /hf search text generation
  /hf info mistralai/Mistral-7B-v0.1

Note: Downloaded models are stored in ~/.cache/huggingface/
"""
        self.parent.append_command_output(help_text)
    
    def hf_login(self, args):
        """Handle HF login"""
        # Create a simple input dialog for token
        token, ok = QInputDialog.getText(
            self.parent, "Hugging Face Login", 
            "Enter your Hugging Face token (from https://huggingface.co/settings/tokens):",
            QLineEdit.EchoMode.Password
        )
        
        if ok and token:
            try:
                login(token=token, add_to_git_credential=True)
                self.parent.append_message("system", "✅ Successfully logged in to Hugging Face Hub!")
            except Exception as e:
                self.parent.append_message("system", f"❌ Login failed: {str(e)[:100]}")
        else:
            self.parent.append_message("system", "Login cancelled.")
    
    def hf_whoami(self, args):
        """Show current user info"""
        try:
            user_info = whoami()
            
            name = user_info.get('name', 'Unknown')
            email = user_info.get('email', 'Not provided')
            orgs = user_info.get('orgs', [])
            
            org_list = "\n".join([f"  • {org}" for org in orgs[:10]]) if orgs else "  None"
            
            info = f"""
**Logged in as:** {name}
**Email:** {email}

**Organizations:**
{org_list}
"""
            self.parent.append_message("assistant", info)
        except Exception as e:
            self.parent.append_message("system", f"Not logged in or error: {str(e)[:100]}")
    
    def hf_logout(self, args):
        """Log out from HF"""
        token_file = Path.home() / '.cache' / 'huggingface' / 'token'
        stored_tokens = Path.home() / '.cache' / 'huggingface' / 'stored_tokens'
        
        reply = QMessageBox.question(
            self.parent,
            "Confirm Logout",
            "Are you sure you want to log out from Hugging Face Hub?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if token_file.exists():
                    token_file.unlink()
                if stored_tokens.exists():
                    stored_tokens.unlink()
                self.parent.append_message("system", "✅ Logged out successfully.")
            except Exception as e:
                self.parent.append_message("system", f"❌ Error during logout: {str(e)[:100]}")
    
    def hf_download(self, args):
        """Download a model or file"""
        parts = args.split()
        if len(parts) < 1:
            self.parent.append_command_output("Usage: /hf download MODEL_ID [filename]")
            return
        
        model_id = parts[0]
        filename = parts[1] if len(parts) > 1 else None
        
        self.parent.append_message("system", f"⏳ Downloading {model_id}...")
        QTimer.singleShot(10, lambda: self._do_download(model_id, filename))
    
    def _do_download(self, model_id, filename=None):
        """Actual download operation (called after UI updates)"""
        try:
            if filename:
                # Download single file
                path = hf_hub_download(
                    repo_id=model_id,
                    filename=filename,
                    local_dir_use_symlinks=False
                )
                self.parent.append_message("system", 
                    f"✅ Downloaded to:\n`{path}`")
            else:
                # Download entire model
                path = snapshot_download(
                    repo_id=model_id,
                    local_dir_use_symlinks=False
                )
                self.parent.append_message("system", 
                    f"✅ Model downloaded to:\n`{path}`")
        except Exception as e:
            self.parent.append_message("system", f"❌ Download failed: {str(e)[:200]}")
    
    def hf_list(self, args):
        """List popular items"""
        resource_type = args.strip() or "models"
        
        self.parent.append_message("system", f"⏳ Fetching popular {resource_type}...")
        QTimer.singleShot(10, lambda: self._do_list(resource_type))
    
    def _do_list(self, resource_type):
        """Actual list operation"""
        try:
            api = HfApi()
            
            if resource_type == "models":
                items = api.list_models(sort="downloads", direction=-1, limit=10)
                title = "Top 10 Most Downloaded Models:\n"
            elif resource_type == "datasets":
                items = api.list_datasets(sort="downloads", direction=-1, limit=10)
                title = "Top 10 Most Downloaded Datasets:\n"
            elif resource_type == "spaces":
                items = api.list_spaces(sort="likes", direction=-1, limit=10)
                title = "Top 10 Spaces:\n"
            else:
                self.parent.append_message("system", "Invalid type. Use: models, datasets, or spaces")
                return
            
            # Build plain text output
            output = title
            for i, item in enumerate(items, 1):
                downloads = getattr(item, 'downloads', 0)
                likes = getattr(item, 'likes', 0)
                output += f"{i}. {item.modelId}\n"
                if downloads:
                    output += f"   📥 {downloads:,} downloads\n"
                if likes:
                    output += f"   ❤️ {likes} likes\n"
                output += "\n"
            
            self.parent.append_command_output(output)
            
        except Exception as e:
            self.parent.append_message("system", f"Error: {str(e)[:200]}")
    
    def hf_info(self, args):
        """Show model information"""
        if not args:
            self.parent.append_command_output("Usage: /hf info MODEL_ID")
            return
        
        model_id = args.strip()
        
        self.parent.append_message("system", f"⏳ Fetching info for {model_id}...")
        QTimer.singleShot(10, lambda: self._do_info(model_id))
    
    def _do_info(self, model_id):
        """Actual info operation"""
        try:
            api = HfApi()
            info = api.model_info(model_id)
            
            # Safely get description with fallback
            description = "No description available"
            try:
                if info.cardData and 'model-index' in info.cardData:
                    model_index = info.cardData['model-index']
                    if model_index and len(model_index) > 0:
                        description = model_index[0].get('name', 'No description')
            except:
                pass
            
            details = f"""
**Model:** {info.modelId}

**Downloads:** {info.downloads:,}
**Likes:** {info.likes or 0}
**Tags:** {', '.join(info.tags[:10]) if info.tags else 'None'}

**Pipeline Tag:** {info.pipeline_tag or 'Unknown'}
**Author:** {info.author or 'Unknown'}

**Last Modified:** {info.lastModified}

**Description:**  
{description}
"""
            if len(details) > 4000:
                details = details[:4000] + "\n\n[Description truncated...]"
            
            self.parent.append_message("assistant", details)
        except Exception as e:
            self.parent.append_message("system", f"Error: {str(e)[:200]}")
    
    def hf_search(self, args):
        """Search for models"""
        if not args:
            self.parent.append_command_output("Usage: /hf search QUERY")
            return
        
        query = args.strip()
        
        self.parent.append_message("system", f"⏳ Searching for '{query}'...")
        QTimer.singleShot(10, lambda: self._do_search(query))
    
    def _do_search(self, query):
        """Actual search operation"""
        try:
            api = HfApi()
            results = api.list_models(search=query, limit=10)
            
            if not results:
                self.parent.append_message("system", "No results found.")
                return
            
            # Plain text output
            output = f"Search results for '{query}':\n"
            for i, model in enumerate(results, 1):
                downloads = getattr(model, 'downloads', 0)
                output += f"{i}. {model.modelId}"
                if downloads:
                    output += f" (📥 {downloads:,})"
                output += "\n"
            
            self.parent.append_command_output(output)
            
        except Exception as e:
            self.parent.append_message("system", f"Search error: {str(e)[:200]}")
    
    def hf_cache_info(self, args):
        """Show cache information"""
        cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
        
        if not cache_dir.exists():
            self.parent.append_message("system", "No Hugging Face cache directory found.")
            return
        
        try:
            # Calculate cache size
            total_size = 0
            model_count = 0
            
            for item in cache_dir.glob('models--*'):
                if item.is_dir():
                    model_count += 1
                    for file in item.rglob('*'):
                        if file.is_file():
                            total_size += file.stat().st_size
            
            size_gb = total_size / (1024**3)
            
            info = f"""
Hugging Face Cache Information:

Cache Directory: {cache_dir}
Models Cached: {model_count}
Total Size: {size_gb:.2f} GB

To clear cache: /hf cache clear
"""
            self.parent.append_command_output(info)
            
        except Exception as e:
            self.parent.append_message("system", f"Error reading cache: {str(e)[:100]}")
    
    def hf_env(self, args):
        """Show environment information"""
        import platform
        import sys
        
        try:
            from huggingface_hub import __version__ as hf_version
        except:
            hf_version = "Not installed"
        
        info = f"""
**Hugging Face Environment:**

**huggingface_hub version:** {hf_version}
**Python version:** {sys.version.split()[0]}
**Platform:** {platform.system()} {platform.release()}

**Cache location:** `{Path.home() / '.cache' / 'huggingface' / 'hub'}`

**Token status:** {'Logged in' if (Path.home() / '.cache' / 'huggingface' / 'token').exists() else 'Not logged in'}
"""
        self.parent.append_message("assistant", info)


def register_hf_command(registry):
    """Register HF command with the registry"""
    registry.register(HFCommand(registry.parent))


__all__ = ['register_hf_command']