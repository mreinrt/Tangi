import os
import logging
import hashlib
import shutil
from pathlib import Path
import chromadb
from chromadb.config import Settings
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)

class CodeIndexer:
    def __init__(self, persist_dir="~/.Tangi/code_index"):
        self.persist_dir = os.path.expanduser(persist_dir)
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Load embedding model from local cache only
        try:
            logger.info("Loading embedding model from cache...")
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            cache_path = os.path.expanduser("~/.cache/huggingface/hub")
            
            # Check if model exists in HF cache
            model_exists = False
            for item in os.listdir(cache_path):
                if item.startswith("models--sentence-transformers--all-MiniLM-L6-v2"):
                    model_exists = True
                    break
            
            if not model_exists:
                raise FileNotFoundError("Model not in cache")
            
            # Load with local_files_only=True
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                local_files_only=True,
                cache_dir=cache_path
            )
            self.model = AutoModel.from_pretrained(
                model_name,
                local_files_only=True,
                cache_dir=cache_path
            )
            logger.info("Embedding model loaded successfully from cache")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(
                "\n❌ Embedding model not found in cache.\n\n"
                "Run one of these commands to download it:\n"
                "  /get-rag\n"
                "  /hf download sentence-transformers/all-MiniLM-L6-v2\n\n"
                "After downloading, try /index again."
            )
        
        # Simple ChromaDB initialization with minimal settings
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_dir
            )
            logger.info(f"Connected to ChromaDB at {self.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            # If connection fails, try to recreate the directory
            shutil.rmtree(self.persist_dir, ignore_errors=True)
            os.makedirs(self.persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_dir
            )
            logger.info(f"Recreated and connected to ChromaDB at {self.persist_dir}")
    
    def encode(self, texts):
        """Convert texts to embeddings"""
        if isinstance(texts, str):
            texts = [texts]
            
        # Tokenize
        inputs = self.tokenizer(
            texts, 
            padding=True, 
            truncation=True, 
            return_tensors="pt", 
            max_length=512
        )
        
        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use mean pooling for sentence embeddings
            embeddings = outputs.last_hidden_state.mean(dim=1).numpy()
        
        return embeddings
    
    def chunk_code(self, file_path, max_lines=50):
        """Split code files into manageable chunks"""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return chunks
        
        current_chunk = []
        current_lines = []
        
        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_lines.append(i+1)
            
            stripped = line.strip()
            if stripped.startswith(('def ', 'class ', 'async def ')) and len(current_chunk) > 5:
                if current_chunk:
                    chunks.append({
                        'text': ''.join(current_chunk[:-1]),
                        'start_line': current_lines[0],
                        'end_line': current_lines[-2],
                    })
                current_chunk = [line]
                current_lines = [i+1]
            
            elif len(current_chunk) >= max_lines:
                chunks.append({
                    'text': ''.join(current_chunk),
                    'start_line': current_lines[0],
                    'end_line': current_lines[-1],
                })
                current_chunk = []
                current_lines = []
        
        if current_chunk:
            chunks.append({
                'text': ''.join(current_chunk),
                'start_line': current_lines[0] if current_lines else 1,
                'end_line': current_lines[-1] if current_lines else len(lines),
            })
        
        return chunks
    
    def index_directory(self, directory, extensions=None):
        """Index all code files in a directory"""
        if extensions is None:
            extensions = [
                '.py', '.js', '.ts', '.jsx', '.tsx',        # Python & JavaScript/TypeScript
                '.c', '.h', '.cpp', '.cxx', '.cc', '.hpp',  # C/C++
                '.java', '.kt', '.kts',                      # Java & Kotlin
                '.go', '.rs', '.rlib',                       # Go & Rust
                '.php', '.rb', '.erb',                        # PHP & Ruby
                '.swift', '.m', '.mm',                        # Swift & Objective-C
                '.cs', '.fs', '.vb',                          # C# & F# & VB.NET
                '.html', '.htm', '.css', '.scss', '.sass',   # Web
                '.xml', '.json', '.yaml', '.yml', '.toml',   # Config files
                '.sh', '.bash', '.zsh', '.fish',              # Shell scripts
                '.lua', '.pl', '.pm', '.t',                   # Lua & Perl
                '.r', '.R',                                   # R
                '.sql',                                       # SQL
                '.dart',                                      # Dart
                '.scala',                                     # Scala
                '.groovy',                                    # Groovy
                '.jl',                                        # Julia
                '.ex', '.exs',                                # Elixir
                '.erl', '.hrl',                               # Erlang
                '.clj', '.cljs', '.cljc',                     # Clojure
                '.elm',                                       # Elm
                '.hs', '.lhs',                                # Haskell
            ]
        
        directory = os.path.expanduser(directory)
        
        if not os.path.exists(directory):
            logger.error(f"Directory does not exist: {directory}")
            return 0
        
        # Directories to ignore completely
        IGNORE_DIRS = {
            # Virtual environments
            '.venv', 'venv', 'env', '.env', 'virtualenv', 'venv-old',
            'venv.bak', '.venv.bak', 'venv_backup',
            
            # Python cache and builds
            '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
            '.tox', '.nox', '.eggs', 'pip-wheel-metadata', 'pip_cache',
            '*.egg-info', '*.egg', 'EGG-INFO', 'dist', 'build', 'develop-eggs',
            
            # JS garbage
            'node_modules', 'bower_components', 'jspm_packages',
            
            # Version control
            '.git', '.svn', '.hg', '.gitlab', '.github',
            
            # IDE
            '.idea', '.vscode', '.vscode-server', '.vs',
            
            # Compiled/build directories
            'target', 'bin', 'obj', 'out', 'cmake-build-debug', 'cmake-build-release',
            'Debug', 'Release', 'x64', 'x86', 'build-*', 'dist-newstyle',
            
            # Python site-packages and libs
            'site-packages', 'dist-packages', 'lib', 'lib64', 'include', 'local/lib',
            
            # Cache directories
            '.cache', '.cargo', '.gradle', '.m2', '.stack-work',
            '.dart_tool', '.pub-cache', '.terraform',
            
            # Documentation and generated
            'docs', 'doc', 'htmlcov', '.coverage', 'lcov',
        }
        
        # File extensions to ignore
        IGNORE_EXTENSIONS = {
            # Compiled objects
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib',
            '.o', '.obj', '.a', '.lib', '.la', '.lo',
            '.exe', '.msi', '.deb', '.rpm', '.dmg', '.pkg',
            '.class', '.jar', '.war', '.ear',
            '.bin', '.out', '.app',
            
            # Archives
            '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.xz',
            '.tgz', '.tbz2', '.whl', '.egg',
            
            # Images
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg',
            '.ico', '.icns', '.webp',
            
            # Media
            '.mp3', '.mp4', '.wav', '.ogg', '.avi', '.mov', '.mkv',
            '.flv', '.webm', '.m4a', '.aac',
            
            # Documents
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.odt', '.ods', '.odp', '.epub', '.mobi',
            
            # Logs and temp
            '.log', '.cache', '.pid', '.lock', '.bak', '.swp', '.swo',
            '.tmp', '.temp', '.old', '.orig',
            
            # Database
            '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
            
            # Translation files
            '.mo', '.po', '.pot', '.gmo',
        }
        
        # File patterns to ignore (full filename)
        IGNORE_FILES = {
            '*.pyc', '*.pyo', '*.pyd',
            '*.so', '*.dll', '*.dylib',
            '*.o', '*.obj', '*.a', '*.lib',
            '*.exe', '*.msi', '*.deb',
            '*.log', '*.cache', '*.pid', '*.lock',
            '*.bak', '*.swp', '*.swo',
            '*.db', '*.sqlite',
            '*.mo', '*.po', '*.pot',
            'pip-log.txt', 'pip-delete-this-directory.txt',
            'PKG-INFO', 'MANIFEST.in', 'setup.cfg',
            'pyvenv.cfg', 'pip-selfcheck.json', 'easy-install.pth',
        }
        
        # Check if path should be ignored
        def should_ignore(path):
            path_str = str(path)
            
            # List of directory names to ignore (exact matches)
            IGNORE_DIRS = {
                'venv', '.venv', 'env', '.env', 'virtualenv',
                '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                'node_modules', 'bower_components',
                '.git', '.svn', '.hg',
                '.idea', '.vscode',
                'site-packages', 'dist-packages',
                'build', 'dist', 'target', 'bin', 'obj',
                '.cache', '.cargo', '.gradle', '.m2',
                '.tox', '.nox', '.eggs',
                '__pycache__',
            }
            
            # Split path and check each part
            path_parts = path_str.split(os.sep)
            for part in path_parts:
                if part in IGNORE_DIRS:
                    return True
            
            # Check file extensions
            IGNORE_EXTS = {
                '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib',
                '.o', '.obj', '.a', '.lib', '.exe', '.msi', '.deb',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
                '.mp3', '.mp4', '.wav', '.ogg', '.avi', '.mov',
                '.pdf', '.doc', '.docx', '.xls', '.ppt',
                '.zip', '.tar', '.gz', '.7z', '.rar',
                '.log', '.cache', '.lock', '.bak', '.swp',
                '.db', '.sqlite', '.sqlite3',
                '.mo', '.po', '.pot',
            }
            
            if path.suffix in IGNORE_EXTS:
                return True
            
            # Check for common patterns
            if 'site-packages' in path_parts or 'dist-packages' in path_parts:
                return True
            
            if any('python' in part and part.replace('python', '').replace('.', '').isdigit() for part in path_parts):
                return True
            
            return False
        
        # Generate a UNIQUE collection name based on the directory path
        normalized_path = os.path.abspath(directory)
        collection_name = hashlib.md5(normalized_path.encode()).hexdigest()[:10]
        
        logger.info(f"INDEXER - Path: {directory}")
        logger.info(f"INDEXER - Normalized: {normalized_path}")
        logger.info(f"INDEXER - Collection name: {collection_name}")
        
        try:
            # Try to delete existing collection for this specific directory
            try:
                self.client.delete_collection(collection_name)
                logger.info(f"Deleted existing collection for {directory}")
            except:
                pass
            # Create new collection with unique name
            collection = self.client.create_collection(collection_name)
            logger.info(f"Created new collection '{collection_name}' for {directory}")
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return 0
        
        all_chunks = []
        file_count = 0
        
        for ext in extensions:
            for file_path in Path(directory).rglob(f'*{ext}'):
                if should_ignore(file_path):
                    continue
                    
                try:
                    chunks = self.chunk_code(file_path)
                    if not chunks:
                        continue
                        
                    rel_path = str(file_path.relative_to(directory))
                    file_count += 1
                    
                    for i, chunk in enumerate(chunks):
                        chunk_id = hashlib.md5(f"{rel_path}_{chunk['start_line']}_{chunk['end_line']}".encode()).hexdigest()
                        
                        all_chunks.append({
                            'id': chunk_id,
                            'text': chunk['text'],
                            'metadata': {
                                'file': rel_path,
                                'start_line': chunk['start_line'],
                                'end_line': chunk['end_line'],
                            }
                        })
                    
                    if file_count % 10 == 0:
                        logger.info(f"Processed {file_count} files...")
                    
                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
        
        # Add to ChromaDB in batches
        if all_chunks:
            batch_size = 100
            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i:i+batch_size]
                
                texts = [chunk['text'] for chunk in batch]
                embeddings = self.encode(texts).tolist()
                
                collection.upsert(
                    ids=[chunk['id'] for chunk in batch],
                    documents=texts,
                    metadatas=[chunk['metadata'] for chunk in batch],
                    embeddings=embeddings
                )
                
                logger.info(f"Indexed batch {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}")
        
        # Save the mapping between directory and collection name
        mapping_file = os.path.expanduser("~/.Tangi/collection_mapping.json")
        try:
            import json
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r') as f:
                    mapping = json.load(f)
            else:
                mapping = {}
            
            # Store both the original and normalized paths
            mapping[directory] = collection_name
            mapping[normalized_path] = collection_name
            
            with open(mapping_file, 'w') as f:
                json.dump(mapping, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save collection mapping: {e}")
        
        logger.info(f"Indexing complete: {file_count} files, {len(all_chunks)} chunks")
        return len(all_chunks)