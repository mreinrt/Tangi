"""
RAG (Retrieval Augmented Generation) commands for code indexing and search
"""

import os
import logging
import json
import shutil
import subprocess
import sys
from pathlib import Path
from Tangi.commands.base import Command
from Tangi.rag.iterative_rag import IterativeRAG

logger = logging.getLogger(__name__)


class IndexCommand(Command):
    """Index a codebase for analysis"""
    
    def __init__(self, parent):
        super().__init__("index", "Index a codebase for analysis", parent)
        self.indexer = None
        self.retriever = None
            
    def check_rag_model(self):
        """Check if the embedding model exists locally"""
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        
        # Check if model exists in Hugging Face cache
        model_exists = False
        model_pattern = "models--sentence-transformers--all-MiniLM-L6-v2"
        
        if cache_dir.exists():
            for item in cache_dir.glob(f"{model_pattern}"):
                if item.is_dir():
                    snapshots_dir = item / "snapshots"
                    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                        model_exists = True
                        break
        
        return model_exists, model_name
    
    def execute(self, args):        
        # Expand user path
        expanded = os.path.expanduser(args.strip())
        path = expanded
        
        if not os.path.exists(path):
            self.parent.append_message("system", f"Path not found: {path}")
            return
        
        # Check if RAG model is available
        model_exists, model_name = self.check_rag_model()
        
        if not model_exists:
            self.parent.append_message("system", 
                f"RAG embedding model not found.\n\n"
                f"To enable code indexing, download the model using HF CLI:\n"
                f"  /hf download sentence-transformers/all-MiniLM-L6-v2\n\n"
                f"Example:\n"
                f"  /hf download sentence-transformers/all-MiniLM-L6-v2\n\n"
                f"This will download the model to ~/.cache/huggingface/hub/\n\n"
                f"After downloading, run /index again.")
            return
        
        # Import here (lazy loading) only after model exists
        from Tangi.rag.indexer import CodeIndexer
        from Tangi.rag.retriever import CodeRetriever
        
        self.parent.append_message("system", f"Indexing {path}...")
        
        self.indexer = CodeIndexer()
        self.retriever = CodeRetriever()
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._do_index(path))
    
    def _do_index(self, path):
        try:
            chunk_count = self.indexer.index_directory(path)
            
            # Save the indexed path for backward compatibility
            saved_path_file = os.path.expanduser("~/.Tangi/last_indexed.txt")
            with open(saved_path_file, 'w') as f:
                f.write(path)
            
            self.parent.append_message("system", 
                f"Index complete! {chunk_count} code chunks indexed.\n"
                f"Now you can ask questions about this codebase.")
                
        except Exception as e:
            logger.error(f"Indexing failed: {e}", exc_info=True)
            self.parent.append_message("system", f"Indexing failed: {e}")


class SearchCommand(Command):
    """Search indexed code and answer questions"""
    
    def __init__(self, parent):
        super().__init__("search", "Search indexed code and answer", parent)
        self.retriever = None
    
    def execute(self, args):
        if not args:
            self.parent.append_message("system", "Usage: /search your question")
            return
        
        # Check if there's an active codebase selected
        if not hasattr(self.parent, 'current_codebase_metadata') or not self.parent.current_codebase_metadata:
            self.parent.append_message("system", "No active codebase selected. Use Manage Index to select one.")
            return
        
        # Set flag that the next LLM call should include code context
        self.parent._last_command = 'search'
        
        self.parent.append_message("system", "Searching codebase...")
        
        # Import here (lazy loading)
        from Tangi.rag.retriever import CodeRetriever
        self.retriever = CodeRetriever()
        
        # Get the active codebase info
        collection_name = self.parent.current_codebase_metadata.get('collection')
        indexed_path = self.parent.current_codebase_metadata.get('path')
        
        if not collection_name or not indexed_path:
            self.parent.append_message("system", "Invalid codebase metadata. Please reselect using Manage Index.")
            return
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._do_search(collection_name, indexed_path, args))
    
    def _do_search(self, collection_name, indexed_dir, query):
        try:
            logger.info(f"Searching codebase '{indexed_dir}' with query: '{query}'")
            results = self.retriever.retrieve(indexed_dir, query, n_results=5)
            
            if not results:
                self.parent.append_message("system", "No relevant code found.")
                return
            
            # Store results for the LLM to use
            self.parent.current_code_context = results
            logger.info(f"Stored {len(results)} chunks in context")
            
            # Format and display the results
            output = "Relevant indexed chunks:\n\n"
            for r in results:
                output += f"`{r['file']}` (lines {r['start_line']}-{r['end_line']})\n"
                # Show first few lines as preview
                preview_lines = r['text'].split('\n')[:3]
                preview = '\n'.join(preview_lines)
                if len(preview_lines) < len(r['text'].split('\n')):
                    preview += "\n..."
                output += f"```python\n{preview}\n```\n\n"
            
            self.parent.append_command_output(output)
            
            # Found results message
            self.parent.append_message("system", f"Found {len(results)} relevant sections. Generating answer...")
            
            # Set the last command so prepare_and_send_to_llm knows this is a search query
            self.parent._last_command = 'search'
            
            # Let prepare_and_send_to_llm handle the routing (online API or local LLM)
            # This method already has the logic to redirect to online API when in online mode
            self.parent.prepare_and_send_to_llm(query)
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            self.parent.append_message("system", f"Search failed: {e}")

class DownloadRAGCommand(Command):
    """Download the RAG embedding model"""
    
    def __init__(self, parent):
        super().__init__("get-rag", "Download the RAG embedding model", parent)
    
    def execute(self, args):
        self.parent.append_message("system", "Downloading Retrieval Augmented Generation embedding model (all-MiniLM-L6-v2)...")
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._do_download)
    
    def _do_download(self):
        try:
            self.parent.append_message("system", "Downloading, please wait...")
            
            cmd = [sys.executable, "-m", "huggingface_hub.commands.huggingface_cli", 
                  "download", "sentence-transformers/all-MiniLM-L6-v2"]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Log to terminal only, not to chat
            for line in process.stdout:
                logger.info(f"HF CLI: {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                self.parent.append_message("system", 
                    "RAG model downloaded successfully!\n"
                    "You can now use /index /Path/To/Directory to index your codebase.")
            else:
                self.parent.append_message("system", 
                    "Download failed. Check terminal for details.\n"
                    "Try: /hf download sentence-transformers/all-MiniLM-L6-v2")
                
        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            self.parent.append_message("system", f"Download failed: {e}")


class RAGStatusCommand(Command):
    """Show current RAG context status (including iterative/deep search)"""
    
    def __init__(self, parent):
        super().__init__("rag-status", "Show current RAG context status", parent)
    
    def execute(self, args):
        output = []
        output.append("RAG Context Status")
        output.append("")
        
        # ===== STANDARD RAG STATUS =====
        # Check if there's an active codebase selected
        if hasattr(self.parent, 'current_codebase_metadata') and self.parent.current_codebase_metadata:
            meta = self.parent.current_codebase_metadata
            output.append("Active Codebase:")
            output.append(f"  - Path: {meta.get('path', 'Unknown')}")
            output.append(f"  - Collection: {meta.get('collection', 'Unknown')}")
            output.append(f"  - Total chunks: {meta.get('chunks', 0)}")
        else:
            output.append("Active Codebase: None")
        
        output.append("")
        
        # Check if there are loaded code chunks in context
        if hasattr(self.parent, 'current_code_context') and self.parent.current_code_context:
            chunks = self.parent.current_code_context
            output.append(f"Loaded in Context: {len(chunks)} chunks")
            
            # Show preview of what's loaded
            if len(chunks) > 0:
                output.append("")
                output.append("Chunks in current context:")
                for i, chunk in enumerate(chunks[:5]):  # Show first 5
                    file = chunk.get('file', 'Unknown')
                    start = chunk.get('start_line', '?')
                    end = chunk.get('end_line', '?')
                    output.append(f"  {i+1}. {file} (lines {start}-{end})")
                
                if len(chunks) > 5:
                    output.append(f"  ... and {len(chunks) - 5} more")
        else:
            output.append("Loaded in Context: No chunks currently loaded")
        
        output.append("")
        
        # ===== ITERATIVE RAG STATUS =====
        # Check if there's an active iterative search
        if hasattr(self.parent, 'iterative_rag_state') and self.parent.iterative_rag_state:
            state = self.parent.iterative_rag_state
            output.append("Iterative/Deep Search Status:")
            output.append(f"  - Active: Yes")
            output.append(f"  - Iterations completed: {state.get('iterations_done', 0)}")
            output.append(f"  - Max iterations: {state.get('max_iterations', 3)}")
            
            # Show query evolution
            if state.get('query_evolution'):
                output.append("")
                output.append("  Query Evolution:")
                for i, q in enumerate(state['query_evolution']):
                    if len(q) > 50:
                        q = q[:47] + "..."
                    output.append(f"    {i}. \"{q}\"")
            
            # Show last analysis if available
            if state.get('last_analysis'):
                output.append("")
                output.append("  Last Analysis:")
                analysis = state['last_analysis']
                if analysis.get('is_satisfied'):
                    output.append(f"    - Satisfied with results")
                else:
                    output.append(f"    - Not satisfied")
                    if analysis.get('missing_aspects'):
                        missing = ', '.join(analysis['missing_aspects'][:3])
                        output.append(f"    - Missing: {missing}")
        else:
            output.append("Iterative/Deep Search Status: No active search")
        
        output.append("")
        
        # ===== MODE =====
        last_cmd = getattr(self.parent, '_last_command', None)
        if last_cmd == 'search':
            output.append("Mode: Next response will include code context")
        elif last_cmd == 'ds':
            output.append("Mode: Next response will use iterative RAG")
        else:
            output.append("Mode: Normal conversation (no code context)")
        
        # ===== RAG MODEL STATUS =====
        output.append("")
        output.append("RAG Model:")
        if hasattr(self.parent, 'rag_model') and self.parent.rag_model:
            output.append(f"  - Current: {self.parent.rag_model}")
        else:
            output.append(f"  - Current: sentence-transformers/all-MiniLM-L6-v2 (default)")
        
        # Check if model is available
        from pathlib import Path
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_pattern = "models--sentence-transformers--all-MiniLM-L6-v2"
        model_exists = False
        
        if cache_dir.exists():
            for item in cache_dir.glob(f"{model_pattern}"):
                if item.is_dir():
                    snapshots_dir = item / "snapshots"
                    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                        model_exists = True
                        break
        
        if model_exists:
            output.append("  - Status: Available in cache")
        else:
            output.append("  - Status: Not downloaded (use `/get-rag` to download)")
        
        # Join and display
        self.parent.append_command_output("\n".join(output))


class RemoveIndexCommand(Command):
    """Remove an indexed codebase"""
    
    def __init__(self, parent):
        super().__init__("remove-index", "Remove an indexed codebase", parent)
    
    def execute(self, args):
        if not args:
            self.parent.append_message("system", "Usage: /remove-index /path/to/codebase")
            return
        
        path = os.path.expanduser(args.strip())
        
        try:
            index_dir = Path.home() / ".Tangi" / "code_index"
            mapping_file = Path.home() / ".Tangi" / "collection_mapping.json"
            
            # Load mapping
            mapping = {}
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    mapping = json.load(f)
            
            # Find collection name - try mapping first
            collection_name = None
            normalized = os.path.abspath(path)
            if path in mapping:
                collection_name = mapping[path]
            elif normalized in mapping:
                collection_name = mapping[normalized]
            
            if not collection_name:
                self.parent.append_message("system", f"Could not find index for: {path}")
                return
            
            # Delete from ChromaDB
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(index_dir))
                client.delete_collection(collection_name)
                self.parent.append_message("system", f"Deleted from ChromaDB: {collection_name}")
            except Exception as e:
                logger.warning(f"Error deleting from ChromaDB: {e}")
            
            # Delete collection directory
            collection_path = index_dir / collection_name
            if collection_path.exists():
                shutil.rmtree(collection_path)
                self.parent.append_message("system", f"Deleted directory: {collection_name}")
            
            # Remove from mapping
            mapping.pop(path, None)
            mapping.pop(normalized, None)
            
            with open(mapping_file, 'w') as f:
                json.dump(mapping, f, indent=2)
            
            self.parent.append_message("system", f"Removed index: {path}")
            
            # Clear context if this was active
            if (hasattr(self.parent, 'current_codebase_metadata') and 
                self.parent.current_codebase_metadata and
                self.parent.current_codebase_metadata.get('path') == path):
                self.parent.current_codebase_metadata = None
                self.parent.current_code_context = None
                self.parent.append_message("system", "Current code context cleared")
                
        except Exception as e:
            logger.error(f"Error removing index: {e}", exc_info=True)
            self.parent.append_message("system", f"Error removing index: {e}")


class IterativeSearchCommand(Command):
    """Iterative deep search with AI refinement"""
    
    def __init__(self, parent):
        super().__init__("ds", "Iterative deep search with AI refinement", parent)  # Changed from "deepsearch" to "ds"
        self.retriever = None
    
    def execute(self, args):
        if not args:
            self.parent.append_message("system", "Usage: /ds your question")  # Updated usage message
            return
        
        # Check if there's an active codebase selected
        if not hasattr(self.parent, 'current_codebase_metadata') or not self.parent.current_codebase_metadata:
            self.parent.append_message("system", "No active codebase selected. Use Manage Index to select one.")
            return
        
        # Get current codebase path
        current_path = self.parent.current_codebase_metadata.get('path')
        if not current_path:
            self.parent.append_message("system", "Invalid codebase metadata. Please reselect using Manage Index.")
            return
        
        # Need to pass the LLM instance
        if not hasattr(self.parent, 'llm') or not self.parent.llm:
            self.parent.append_message("system", "No LLM loaded. Please load a model first.")
            return
        
        # Set flag that the next LLM call should include code context
        self.parent._last_command = 'ds'
        
        self.parent.append_message("system", "Starting deep iterative search...")
        
        from Tangi.rag.retriever import CodeRetriever
        self.retriever = CodeRetriever()
        
        # Create iterative RAG instance
        iterative_rag = IterativeRAG(self.retriever, self.parent.llm, max_iterations=3)
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._do_deepsearch(iterative_rag, current_path, args))
    
    def _do_deepsearch(self, iterative_rag, path, query):
        try:
            results = iterative_rag.iterative_retrieve(query, path)
            
            if not results['final_context']:
                self.parent.append_message("system", "No relevant code found after iterative search.")
                return
            
            # Store iterative RAG state for status command
            self.parent.iterative_rag_state = {
                'iterations_done': len(results['iterations']),
                'max_iterations': iterative_rag.max_iterations,
                'query_evolution': results['query_evolution'],
                'last_analysis': results['iterations'][-1].get('analysis') if results['iterations'] else None
            }
            
            # Store results for LLM
            self.parent.current_code_context = results['final_context']
            
            # Show iteration summary - plain text, no markdown headers
            output_lines = []
            output_lines.append(f"Deep Search completed in {results['time_seconds']:.2f}s")
            output_lines.append(f"Iterations: {len(results['iterations'])}")
            output_lines.append("")
            output_lines.append("Query evolution:")
            for i, q in enumerate(results['query_evolution']):
                if len(q) > 60:
                    q = q[:57] + "..."
                output_lines.append(f"  {i}. {q}")
            output_lines.append("")
            
            self.parent.append_command_output("\n".join(output_lines))
            
            # Now answer using the loaded context
            self.parent.append_message("system", 
                f"Found {len(results['final_context'])} relevant code chunks. Generating answer...")
            
            # Trigger the LLM to answer using the loaded context
            # The _last_command flag is already set to 'ds'
            self.parent.prepare_and_send_to_llm(query)
            
        except Exception as e:
            logger.error(f"Deep search failed: {e}", exc_info=True)
            self.parent.append_message("system", f"Deep search failed: {e}")

class ClearContextCommand(Command):
    """Clear current code context"""
    
    def __init__(self, parent):
        super().__init__("clear", "Clear current code context", parent)
    
    def execute(self, args):
        self.parent.current_code_context = None
        self.parent.append_message("system", "Code context cleared.")
        logger.info("Code context cleared by user")


class CacheInfoCommand(Command):
    """Show KV cache statistics"""
    
    def __init__(self, parent):
        super().__init__("cache-info", "Show KV cache statistics", parent)
    
    def execute(self, args):
        if hasattr(self.parent, 'kv_cache_manager'):
            stats = self.parent.kv_cache_manager.get_cache_stats()
            output = "KV Cache Statistics:\n"
            output += f"  - Entries: {stats['total_entries']}\n"
            output += f"  - Size: {stats['total_size_gb']:.2f} GB / {stats['max_size_gb']:.1f} GB\n"
            if stats['total_entries'] > 0:
                output += f"  - Cache files: {', '.join(stats['cache_files'][:3])}"
                if len(stats['cache_files']) > 3:
                    output += f" and {len(stats['cache_files']) - 3} more"
            self.parent.append_command_output(output)
        else:
            self.parent.append_message("system", "KV cache manager not available")


def register_rag_commands(registry):    
    """Register all RAG commands with the registry"""
    registry.register(IndexCommand(registry.parent))
    registry.register(SearchCommand(registry.parent))
    registry.register(DownloadRAGCommand(registry.parent))
    registry.register(RAGStatusCommand(registry.parent)) 
    registry.register(RemoveIndexCommand(registry.parent))
    registry.register(IterativeSearchCommand(registry.parent))
    registry.register(ClearContextCommand(registry.parent))
    registry.register(CacheInfoCommand(registry.parent))