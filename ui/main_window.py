"""
Main window for Tangi application
"""

import os
import sys
import time
import re
import html
import markdown
import logging
import random
from collections import Counter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QTextEdit,
    QStatusBar, QLabel, QMenuBar, QSplitter, QInputDialog, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QDialog, QPushButton,
    QDialogButtonBox, QApplication, QGroupBox, QListWidget, QListWidgetItem,
    QRadioButton, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QMutex, QMutexLocker, QUrl, QSettings
from PyQt6.QtGui import QFont, QTextCursor

from llama_cpp import Llama

# Tangi imports
from Tangi.utils.constants import (
    UNIVERSAL_STOP_SEQUENCES, MAX_TURNS, MAX_QUEUE_SIZE, DEFAULT_RAM_PERCENTAGE
)
from Tangi.utils.system import (
    ThreadOptimizer, OpenBLASDetector, SYSTEM_RAM_MB, AVAILABLE_RAM_MB, optimal_threads
)
from Tangi.utils.helpers import (
    clean_response, validate_response, get_appropriate_system_prompt,
    format_timestamp, is_code_request, estimate_token_count
)
from Tangi.models.loader import ModelLoaderThread
from Tangi.workers.llm_worker import LLMWorker
from Tangi.databases.manager import DatabaseManager
from Tangi.commands.base import CommandRegistry
from Tangi.commands.info_commands import register_all_info_commands
from Tangi.commands.hf_commands import register_hf_command
from Tangi.utils.kv_cache import KVCacheManager
from Tangi.ui.theme import apply_theme, set_theme, CURRENT_THEME, apply_theme_to_application
from Tangi.ui.dialogs import (
    DisplayOptionsDialog, PreferencesDialog, AboutDialog, themed_file_dialog
)

logger = logging.getLogger(__name__)


class RawChat(QWidget):
    """Main chat window for Tangi"""

    def __init__(self):
        super().__init__()

        self.llm = None
        self.session_id = None
        self.model_path = None
        self.db_manager = None
        self.llm_worker = None
        self.model_loader = None
        self.is_processing = False
        self.message_queue = []
        self.processing_mutex = QMutex()
        self.queue_mutex = QMutex()

        # RAG context storage
        self.current_code_context = None
        self.current_codebase_metadata = None
        self.iterative_rag_state = None

        # RAM allocation setting
        self.ram_percentage = DEFAULT_RAM_PERCENTAGE

        # Model info storage
        self.model_type = None
        self.model_size_category = None
        self.estimated_params = 0

        # Settings for saving UI state
        self.settings = QSettings("Tangi", "Tangi")

        # Load last model from settings
        self.last_model_path = self.settings.value("last_model", "")

        # Use default storage in user's home directory
        self.default_storage_dir = os.path.expanduser("~/.Tangi")
        self.db_path = os.path.join(self.default_storage_dir, "chatlogs.db")
        os.makedirs(self.default_storage_dir, exist_ok=True)

        # Track the last command executed (for RAG context handling)
        self._last_command = None
        
# Theme refresh prevention flag
        self._refreshing_theme = False

        # Thinking animation attributes
        self.animating = False
        self.dot_count = 0
        self.thinking_message = ""

        self.setWindowTitle("Tangi")

        # Create status bar
        self.status_bar = QStatusBar()
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)

        # ==================== MAIN SPLITTER ====================
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(8)
        main_splitter.setChildrenCollapsible(False)

        # Chat display
        self.chat = QTextBrowser()
        self.chat.setAcceptRichText(True)
        self.chat.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        main_splitter.addWidget(self.chat)

        # Input area
        self.input = QTextEdit()
        self.input.setAcceptRichText(False)
        self.input.setMinimumHeight(30)
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.input.setPlaceholderText("Type prompt here... ")
        self.input.installEventFilter(self)
        main_splitter.addWidget(self.input)

        # Set stretch factors
        main_splitter.setStretchFactor(0, 8)
        main_splitter.setStretchFactor(1, 1)

        # ==================== MAIN LAYOUT ====================
        layout = QVBoxLayout(self)
        layout.addWidget(main_splitter)
        layout.addWidget(self.status_bar)

        # ==================== MENU ====================
        menubar = QMenuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New Session", self.new_session)
        file_menu.addAction("Load Model", self.load_model)
        file_menu.addSeparator()
        file_menu.addAction("Load Session", self.load_session)
        file_menu.addAction("Manage Sessions", self.manage_sessions)
        file_menu.addSeparator()
        file_menu.addAction("Manage Index", self.show_index_manager)

        preferences_menu = menubar.addMenu("Preferences")
        preferences_menu.addAction("Preferences...", self.show_preferences)

        about_menu = menubar.addMenu("About")
        about_menu.addAction("About Tangi", self.show_about)

        layout.setMenuBar(menubar)

        self.history = []
        self.response_format = "markdown"

        # Command registry
        self.command_registry = CommandRegistry(self)
        self._register_commands()

        # Apply initial theme
        apply_theme(self)

        # Markdown debugger
        self.markdown_debug = self.MarkdownDebugger()
        self.bleed_counter = 0

        # Initialize database
        self.init_database()

        # Initialize KV cache manager
        self.kv_cache_manager = KVCacheManager(max_size_gb=4)
        self.current_kv_cache = None

        # Auto-create default session
        self.auto_create_session()
        
        # Load last model after UI is ready
        QTimer.singleShot(100, self.load_last_model)

        # Message Sender Tracking
        self._last_speaker = None

        # User token limit setting
        self.max_tokens_setting = 512

        # RAG model setting
        self.rag_model = None

    # ==================== MODEL PERSISTENCE ====================  
    
    def load_last_model(self):
        """Load the previously used model if it exists"""
        if self.last_model_path and os.path.exists(self.last_model_path):
            logger.info(f"Auto-loading last model: {self.last_model_path}")
            self.model_path = self.last_model_path
            self.input.setEnabled(False)
            self.start_thinking_animation(f"Loading {os.path.basename(self.last_model_path)}")
            
            self.model_loader = ModelLoaderThread(self.last_model_path, self.ram_percentage)
            self.model_loader.model_loaded.connect(self.on_model_loaded)
            self.model_loader.load_failed.connect(self.on_model_load_failed)
            self.model_loader.progress.connect(self.on_model_load_progress)
            self.model_loader.finished.connect(self.on_model_loader_finished)
            self.model_loader.start()
        else:
            logger.info("No previous model found or file missing")

    # ==================== THINKING ANIMATION METHODS ====================

    def start_thinking_animation(self, message="Thinking"):
        """Start the thinking animation in status bar"""
        self.animating = True
        self.dot_count = 0
        self.thinking_message = message
        self.status_label.setText(message)
        self._animate_thinking_dots()

    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        self.animating = False
        self.update_model_info()

    def _animate_thinking_dots(self):
        """Animate the status dots continuously"""
        if not self.animating:
            return

        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.status_label.setText(f"{self.thinking_message}{dots}")

        if self.animating:
            QTimer.singleShot(500, self._animate_thinking_dots)

    # ==================== MARKDOWN DEBUGGER ====================

    class MarkdownDebugger:
        """Helper class for debugging markdown bleed issues"""

        def __init__(self):
            self.last_message_tags = []
            self.reset_counter = 0

        def analyze_html(self, html_text, message_type):
            """Analyze HTML for unclosed tags"""
            import re

            opening_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*)?>(?!.*?<\/\1>)', html_text)
            closing_tags = re.findall(r'<\/([a-zA-Z][a-zA-Z0-9]*)>', html_text)

            unclosed = []
            for tag in opening_tags:
                if closing_tags.count(tag) < opening_tags.count(tag):
                    unclosed.append(tag)

            return {
                'opening': opening_tags,
                'closing': closing_tags,
                'unclosed': unclosed,
                'has_content': bool(html_text.strip())
            }

    # ==================== EVENT HANDLING ====================

    def eventFilter(self, obj, event):
        """Handle key events for input widget"""
        if obj is self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                event.accept()
                self.process_enter_key()
                return True
        return super().eventFilter(obj, event)

    def process_enter_key(self):
        """Process Enter key press"""
        prompt = self.input.toPlainText().strip()
        self.input.clear()
        if prompt:
            QTimer.singleShot(0, lambda: self.process_prompt(prompt))

    # ==================== COMMAND HANDLING ====================

    def process_prompt(self, prompt):
        """Process user input"""
        prompt_lower = prompt.lower().strip()

        self.append_message("user", prompt)

        # Check for commands first
        if prompt.startswith('/'):
            self.command_registry.execute(prompt[1:])
            return

        # Check for LLM
        if not self.llm:
            self.append_message("system", "No language model detected. Load language model to begin...")
            return

        if not self.session_id:
            self.auto_create_session()

        # Queue management
        with QMutexLocker(self.queue_mutex):
            if len(self.message_queue) >= MAX_QUEUE_SIZE:
                self.append_message("system", f"Queue full ({MAX_QUEUE_SIZE} max). Please wait...")
                return

        with QMutexLocker(self.processing_mutex):
            if self.is_processing:
                with QMutexLocker(self.queue_mutex):
                    self.message_queue.append(prompt)
                self.append_message("system", f"Message queued ({len(self.message_queue)} in queue)...")
                return
            self.is_processing = True

        # Temporarily switch to markdown for code requests
        if is_code_request(prompt):
            self._original_format = self.response_format
            self.response_format = "markdown"
            logger.info("Code request detected, temporarily switching to markdown mode")

        # Add to history and save
        self.history.append(f"User: {prompt}")
        self.save("user", prompt)

        # Update UI
        self.input.setEnabled(False)
        self.start_thinking_animation("Thinking")

        self.prepare_and_send_to_llm(prompt)

    # ==================== REGISTER COMMANDS =====================

    def _register_commands(self):
        """Register all slash commands"""
        from Tangi.commands.info_commands import register_all_info_commands
        from Tangi.commands.hf_commands import register_hf_command

        register_all_info_commands(self.command_registry)
        register_hf_command(self.command_registry)

        try:
            from Tangi.commands.rag_commands import register_rag_commands
            register_rag_commands(self.command_registry)
            logger.info("RAG commands registered successfully")
        except ImportError as e:
            logger.warning(f"RAG commands not available: {e}")
        except Exception as e:
            logger.error(f"Error registering RAG commands: {e}")

        logger.info(f"Total registered commands: {len(self.command_registry.commands)}")

    # ==================== MODEL INFO METHODS ====================

    def update_model_info(self, force=False):
        """Update model information from loaded model"""
        if self.animating and not force:
            return

        if self.llm:
            if hasattr(self.llm, 'model_type'):
                self.model_type = self.llm.model_type
            if hasattr(self.llm, 'model_size_category'):
                self.model_size_category = self.llm.model_size_category
            if hasattr(self.llm, 'estimated_params'):
                self.estimated_params = self.llm.estimated_params

            # Check OpenBLAS status
            openblas_status = ""
            try:
                import ctypes
                openblas = ctypes.CDLL("libopenblas.so.0")
                if hasattr(openblas, 'openblas_get_corename'):
                    openblas.openblas_get_corename.restype = ctypes.c_char_p
                    core_name = openblas.openblas_get_corename()
                    openblas_status = f" | OpenBLAS: {core_name.decode('utf-8')}"
            except Exception:
                pass

            token_limit_info = f" | Max tokens: {self.max_tokens_setting}"

            model_ctx = self.get_model_context_size()
            ctx_display = f"{model_ctx//1000}K" if model_ctx >= 1000 else str(model_ctx)

            model_info = f"{self.model_type}" if self.model_type else "Unknown"
            size_info = f"({self.model_size_category})" if self.model_size_category else ""
            param_info = f"~{self.estimated_params}M" if self.estimated_params else ""

            status_text = (
                f"Model: {model_info} {size_info} {param_info} - "
                f"Context: {ctx_display} - "
                f"Format: {self.response_format.capitalize()}{openblas_status}{token_limit_info}"
            )

            if force or not self.animating:
                self.status_label.setText(status_text)

    def get_model_context_size(self):
        """Get the actual context size the model is using"""
        if self.llm:
            if hasattr(self.llm, 'actual_ctx'):
                return self.llm.actual_ctx
            elif hasattr(self.llm, 'n_ctx'):
                return self.llm.n_ctx
        return 2048

    # ==================== HISTORY MANAGEMENT ====================

    def calculate_optimal_history(self, context_size):
        """Calculate optimal history turns for ANY context size"""
        if context_size >= 65536:
            return MAX_TURNS * 4
        elif context_size >= 32768:
            return MAX_TURNS * 3
        elif context_size >= 16384:
            return MAX_TURNS * 2
        elif context_size >= 8192:
            return MAX_TURNS
        elif context_size >= 4096:
            return 4
        elif context_size >= 2048:
            return 3
        return 2

    def clean_history(self, history_segment):
        """Remove potential contamination from history"""
        if not history_segment:
            return []

        cleaned = []
        last_message = None

        for msg in history_segment:
            msg_stripped = msg.strip()
            if len(msg_stripped) < 3:
                continue
            if msg_stripped == last_message:
                continue
            if msg_stripped in ["Assistant:", "User:", "assistant:", "user:", "Human:"]:
                continue
            cleaned.append(msg_stripped)
            last_message = msg_stripped

        return cleaned

    # ==================== MODEL LOADING ====================

    def verify_model_file(self, filepath):
        """Check if a file appears to be a valid GGUF file"""
        try:
            if not filepath.lower().endswith('.gguf'):
                return False, "File must have .gguf extension"

            if not os.path.exists(filepath):
                return False, "File does not exist"

            if not os.access(filepath, os.R_OK):
                return False, "Cannot read file (permission denied)"

            try:
                size_bytes = os.path.getsize(filepath)
                size_mb = size_bytes / (1024 * 1024)

                if size_mb < 10:
                    return False, f"File too small ({size_mb:.1f}MB) - may be corrupted"

                if size_mb > SYSTEM_RAM_MB:
                    return False, f"File too large ({size_mb:.1f}MB) for your {SYSTEM_RAM_MB/1024:.1f}GB RAM"

            except OSError as e:
                if e.errno == 5:
                    return False, "I/O error reading file - storage device may be disconnected"
                raise

            try:
                with open(filepath, 'rb') as f:
                    magic = f.read(4)
                    if magic != b'GGUF':
                        return False, "Not a valid GGUF file (wrong format)"
            except OSError as e:
                if e.errno == 5:
                    return False, "I/O error reading file contents - file may be corrupted"
                raise

            return True, f"GGUF file verified ({size_mb:.1f}MB)"

        except OSError as e:
            if e.errno == 5:
                return False, "Input/output error - storage device may be disconnected"
            elif e.errno == 30:
                return False, "Read-only filesystem - cannot access file"
            else:
                return False, f"System error [{e.errno}]: {str(e)}"
        except Exception as e:
            return False, f"Error checking file: {str(e)}"

    def verify_model_loaded(self):
        """Verify model is actually loaded and responsive"""
        try:
            logger.info("Verifying model is responsive...")
            test_out = self.llm("test", max_tokens=1, temperature=0.1)
            logger.info("Model verification passed")
            return True
        except Exception as e:
            logger.error(f"Model verification failed: {e}")
            return False

    def load_model(self):
        """Open file dialog and load a model"""
        if self.model_loader and self.model_loader.isRunning():
            self.model_loader.stop()
            self.model_loader = None

        if self.llm:
            try:
                if hasattr(self.llm, 'close'):
                    self.llm.close()
                elif hasattr(self.llm, 'reset'):
                    self.llm.reset()
            except Exception as e:
                logger.warning(f"Error cleaning up old model: {e}")
            finally:
                self.llm = None
                self.model_type = None
                self.model_size_category = None
                self.estimated_params = 0
            import gc
            gc.collect()

        dialog = themed_file_dialog(self, "Select GGUF", "", "GGUF (*.gguf)")

        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                path = files[0]

                self.append_message("system", f"Checking file: {os.path.basename(path)}")

                try:
                    is_valid, message = self.verify_model_file(path)
                    if not is_valid:
                        self.append_message("system", f"Invalid model file: {message}")
                        return
                    self.append_message("system", message)
                except Exception as e:
                    self.append_message("system", f"Error during file check: {str(e)}")
                    return

                self.model_path = path
                self.input.setEnabled(False)
                self.start_thinking_animation(f"Loading {os.path.basename(path)}")

                self.model_loader = ModelLoaderThread(path, self.ram_percentage)
                self.model_loader.model_loaded.connect(self.on_model_loaded)
                self.model_loader.load_failed.connect(self.on_model_load_failed)
                self.model_loader.progress.connect(self.on_model_load_progress)
                self.model_loader.finished.connect(self.on_model_loader_finished)
                self.model_loader.start()

    def on_model_loaded(self, llm):
        """Handle successful model load"""
        self.stop_thinking_animation()
        self.llm = llm

        # Save the model path for next startup
        self.settings.setValue("last_model", self.model_path)

        if not self.verify_model_loaded():
            self.append_message("system", "Model loaded but not responding properly. Try reloading.")
            self.llm = None
            logger.error("Model verification failed - unloading model")
            return

        if self.session_id and self.db_manager and self.db_manager.db:
            try:
                self.db_manager.update_session_model(self.session_id, str(self.model_path))
                logger.info(f"Updated session {self.session_id} with model: {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to update session with model: {e}")

        model_ctx = self.get_model_context_size()

        # Get CPU name
        cpu_name = "Unknown CPU"
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        cpu_name = line.split(':')[1].strip()
                        break
        except Exception:
            pass

        batch_size = getattr(self.llm, 'n_batch', 'optimized')

        # Check OpenBLAS status
        openblas_core = ""
        try:
            import ctypes
            openblas = ctypes.CDLL("libopenblas.so.0")
            if hasattr(openblas, 'openblas_get_corename'):
                openblas.openblas_get_corename.restype = ctypes.c_char_p
                core_name = openblas.openblas_get_corename()
                if core_name:
                    openblas_core = core_name.decode('utf-8')
        except Exception:
            openblas_core = "Unknown"

        ctx_display = f"{model_ctx//1000}K" if model_ctx >= 1000 else str(model_ctx)

        self.append_message("system",
            f"Optimized using OpenBLAS {openblas_core}: {cpu_name} • batch {batch_size}"
        )

        self.update_model_info()

        allocated_gb = (SYSTEM_RAM_MB * self.ram_percentage / 100) / 1024
        system_gb = SYSTEM_RAM_MB / 1024

        self.append_message("system",
            f"Model loaded successfully! "
            f"(Context: {ctx_display}, "
            f"RAM: {self.ram_percentage}% of {system_gb:.1f}GB)")

        logger.info(f"Model loaded with {model_ctx} token context")

        if not self.session_id:
            self.auto_create_session()

    def on_model_load_failed(self, error_msg):
        """Handle model load failure"""
        self.append_message("system", f"Load failed: {error_msg}")
        allocated_gb = (SYSTEM_RAM_MB * self.ram_percentage / 100) / 1024
        self.status_label.setText(f"Model load failed - RAM: {self.ram_percentage}% ({allocated_gb:.1f}GB)")
        logger.error(f"Model load failed: {error_msg}")

    def on_model_load_progress(self, message):
        """Update progress during model load"""
        self.status_label.setText(f"Loading: {message}")
        QApplication.processEvents()

    def on_model_loader_finished(self):
        """Clean up after model loader finishes"""
        self.input.setEnabled(True)
        self.model_loader = None

    # ==================== LLM INTERACTION ====================

    def prepare_and_send_to_llm(self, prompt):
        """Prepare context and send to LLM worker"""
        model_ctx = self.get_model_context_size()

        is_search_query = hasattr(self, '_last_command') and self._last_command in ['search', 'ds']

        system_prompt = get_appropriate_system_prompt(self.model_path)

        max_history_turns = self.calculate_optimal_history(model_ctx)
        clean_history = self.clean_history(self.history[-max_history_turns:])

        context_parts = [system_prompt]

        for msg in clean_history:
            if msg.startswith("User:"):
                context_parts.append(f"User: {msg[5:].strip()}")
            elif msg.startswith("Assistant:"):
                context_parts.append(f"Assistant: {msg[10:].strip()}")

        context_parts.append(f"User: {prompt}")
        context_parts.append("Assistant:")

        ctx = "\n".join(context_parts)

        ctx_tokens_est = estimate_token_count(ctx)
        logger.info(f"Context: {model_ctx} tokens, Prompt: ~{ctx_tokens_est} tokens, History: {len(clean_history)} turns")

        code_context_to_use = self.current_code_context if is_search_query else None

        if is_search_query:
            logger.info(f"Including {len(self.current_code_context) if self.current_code_context else 0} code chunks in context ({self._last_command} query)")
            self._last_command = None
        else:
            logger.info("No code context included (normal query)")

        self.llm_worker = LLMWorker(
            llm=self.llm,
            context=ctx,
            model_path=self.model_path,
            prompt=prompt,
            max_tokens_setting=self.max_tokens_setting,
            code_context=code_context_to_use
        )
        self.llm_worker.response_ready.connect(self.handle_llm_response)
        self.llm_worker.error_occurred.connect(self.handle_llm_error)
        self.llm_worker.finished.connect(self.cleanup_worker)
        self.llm_worker.start()

    def handle_llm_response(self, reply):
        """Handle successful LLM response"""
        try:
            self.stop_thinking_animation()

            cleaned_reply = clean_response(reply)

            is_valid, validation_msg = validate_response(cleaned_reply, self.history[-1] if self.history else "")

            if not is_valid:
                logger.warning(f"Response validation failed: {validation_msg}")
                self.append_message("system", f"Response issue: {validation_msg}. Please try rephrasing your prompt.")
                self.cleanup_worker()
                return

            self.append_message("assistant", cleaned_reply)
            self.save("assistant", cleaned_reply)
            self.history.append(f"Assistant: {cleaned_reply}")

            if hasattr(self, '_original_format'):
                self.response_format = self._original_format
                delattr(self, '_original_format')
                logger.info(f"Restored original format: {self.response_format}")

            self.status_label.setText("Ready")

        except Exception as e:
            self.stop_thinking_animation()
            logger.error(f"Error handling LLM response: {e}")
            self.append_message("system", f"Error displaying response: {str(e)[:100]}")
            self.status_label.setText("Error occurred")
        finally:
            self.input.setEnabled(True)
            self.input.setFocus()

    def handle_llm_error(self, error_msg):
        """Handle errors from the LLM worker"""
        try:
            self.stop_thinking_animation()
            logger.error(f"LLM error: {error_msg}")
            self.append_message("system", f"Error: {error_msg[:200]}")
            self.status_label.setText("Error occurred")
            self.cleanup_worker()
        except Exception as e:
            self.stop_thinking_animation()
            logger.error(f"Error in error handler: {e}")
        finally:
            self.input.setEnabled(True)
            self.input.setFocus()

    def cleanup_worker(self):
        """Clean up LLM worker and process next queued message"""
        try:
            if self.llm_worker is not None:
                if hasattr(self.llm_worker, 'isRunning') and self.llm_worker.isRunning():
                    if hasattr(self.llm_worker, 'stop'):
                        self.llm_worker.stop()
                self.llm_worker.deleteLater()
                self.llm_worker = None

            self.input.setEnabled(True)
            self.input.setFocus()
            self.update_model_info()

            with QMutexLocker(self.queue_mutex):
                if self.message_queue:
                    QTimer.singleShot(100, self.process_next_queued_message)
                    return

            with QMutexLocker(self.processing_mutex):
                self.is_processing = False

        except Exception as e:
            logger.error(f"Error in cleanup_worker: {e}")
            self.input.setEnabled(True)
            self.input.setFocus()
            with QMutexLocker(self.processing_mutex):
                self.is_processing = False

    def process_next_queued_message(self):
        """Process the next message in queue"""
        try:
            with QMutexLocker(self.queue_mutex):
                if not self.message_queue:
                    with QMutexLocker(self.processing_mutex):
                        self.is_processing = False
                    return

                next_prompt = self.message_queue.pop(0)

                self.append_message("user", f"{next_prompt} (from queue)")
                self.history.append(f"User: {next_prompt}")
                self.save("user", next_prompt)

                self.input.setEnabled(False)
                self.start_thinking_animation("Processing queued message")

                self.prepare_and_send_to_llm(next_prompt)

        except Exception as e:
            self.stop_thinking_animation()
            logger.error(f"Error processing queued message: {e}")
            with QMutexLocker(self.processing_mutex):
                self.is_processing = False
            self.input.setEnabled(True)
            self.status_label.setText("Error processing queue")

    # ==================== UI METHODS ====================

    def set_response_format(self, format_mode):
        """Set the response format mode"""
        if format_mode in ["markdown", "conversation"]:
            self.response_format = format_mode
            logger.info(f"Response format set to: {format_mode}")
            self.update_model_info()

    def set_max_tokens(self, value):
        """Update token limit from preferences"""
        self.max_tokens_setting = value
        self.append_message("system", f"Max tokens per response set to: {value}")
        logger.info(f"Max tokens setting changed to: {value}")
        self.update_model_info()

    def set_ram_percentage(self, value):
        """Update RAM allocation percentage"""
        self.ram_percentage = value
        logger.info(f"RAM allocation set to: {value}%")

    def append_message(self, role, text):
        """Append a message to the chat display"""
        role = role.lower()

        if role == "system":
            prefix = "&lt;system&gt;"
        elif role == "user":
            prefix = "&lt;user&gt;"
        elif role == "assistant":
            prefix = "&lt;assistant&gt;"
        else:
            prefix = "&lt;unknown&gt;"

        cleaned_text = text.strip()
        has_numbered_list = bool(re.search(r'^\s*\d+\.\s+\S', cleaned_text, re.MULTILINE))

        # Add spacing between different speakers
        if role != "system" and hasattr(self, '_last_speaker') and self._last_speaker and self._last_speaker != role:
            self.chat.append('<div style="height: 8px;"></div>')

        container_style = 'style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word; max-width: 100%; width: 100%; display: block;"'

        if role == "assistant" and self.response_format == "markdown" and not has_numbered_list:
            code_blocks = []
            def save_code_block(match):
                code_blocks.append(match.group(0))
                return f"!!CODE_BLOCK_{len(code_blocks)-1}!!"

            text_with_placeholders = re.sub(r'```.*?\n(.*?)```', save_code_block, cleaned_text, flags=re.DOTALL)
            html_text = markdown.markdown(text_with_placeholders, extensions=["fenced_code", "codehilite", "tables"])

            for i, block in enumerate(code_blocks):
                code_content = re.sub(r'```.*?\n(.*?)```', r'\1', block, flags=re.DOTALL)
                code_content = html.escape(code_content)
                proper_code = f'<pre style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word; max-width: 100%;"><code style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word;">{code_content}</code></pre>'
                html_text = html_text.replace(f"!!CODE_BLOCK_{i}!!", proper_code)

            html_text = html_text.replace('<br>', '').replace('<br/>', '')
            full_message = f'<div class="message-container" {container_style}>{prefix}<br>{html_text}</div>'

        else:
            safe_text = html.escape(cleaned_text)
            safe_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe_text)
            safe_text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', safe_text)
            safe_text = re.sub(r'`([^`]+)`', r'<code>\1</code>', safe_text)
            safe_text = safe_text.replace('\n', '<br>')

            if '\n' in cleaned_text and (cleaned_text.count('\n') > 1 or '    ' in cleaned_text):
                full_message = f'<div class="message-container" {container_style}>{prefix}<br><pre style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word; max-width: 100%;"><code style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word;">{safe_text}</code></pre></div>'
            else:
                full_message = f'<div class="message-container" {container_style}>{prefix} {safe_text}</div>'

        self.chat.append(full_message)
        self._last_speaker = role
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()

    def append_command_output(self, text):
        """Display command output as plain text without affecting global formatting"""
        role = "assistant"
        prefix = '&lt;assistant&gt;'

        safe_text = html.escape(text)
        safe_text = safe_text.replace('\n', '<br>')
        safe_text = safe_text.replace('  ', ' &nbsp;')

        self.chat.append(f'{prefix} {safe_text}')
        self.chat.append('<div style="background: transparent; height: 0;"></div>')

        self._last_speaker = role
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()

    # ==================== DATABASE METHODS ====================

    def init_database(self):
        """Initialize database connection"""
        self.db_manager = DatabaseManager(self.db_path)
        success, message = self.db_manager.init_database()

        if success:
            allocated_gb = (SYSTEM_RAM_MB * self.ram_percentage / 100) / 1024
            self.status_label.setText(f"Storage: {self.default_storage_dir} - RAM: {self.ram_percentage}% ({allocated_gb:.1f}GB)")
            self.append_message("system", f"Database initialized at {self.db_path}")
        else:
            self.status_label.setText("Warning: Database error")
            self.append_message("system", "Database unavailable - running without persistence")
            self.db_manager = None

    def auto_create_session(self):
        """Auto-create a default session if none exists"""
        try:
            with QMutexLocker(self.processing_mutex):
                if not self.session_id:
                    session_name = "Auto Session"
                    if self.db_manager and self.db_manager.db:
                        self.session_id = self.db_manager.create_session(session_name, str(self.model_path) if self.model_path else "")
                        self.append_message("system", f"Auto-created session: {session_name}")
                        logger.info(f"Auto-created session {self.session_id}: {session_name}")
                    else:
                        self.session_id = 1
                        self.append_message("system", f"Started temporary session: {session_name}")
        except Exception as e:
            logger.error(f"Failed to auto-create session: {e}")
            self.session_id = 1

    def save(self, role, text):
        """Save a message to the database"""
        if not self.db_manager or not self.db_manager.db or not self.session_id:
            logger.warning(f"Could not save message: db={self.db_manager is not None}, session={self.session_id}")
            return

        try:
            self.db_manager.add_message(self.session_id, role, text)
        except Exception as e:
            logger.error(f"Database error saving message: {e}")
            if random.random() < 0.1:
                self.append_message("system", "Warning: Some messages may not be saved to database")

    def new_session(self):
        """Create a new chat session"""
        name, ok = QInputDialog.getText(self, "New Session", "Enter session name:")
        if ok and name.strip():
            try:
                if hasattr(self, 'kv_cache_manager') and self.session_id:
                    self.kv_cache_manager.clear_session_cache(self.session_id)
                    logger.info(f"Cleared KV cache for old session {self.session_id}")

                if self.db_manager and self.db_manager.db:
                    self.session_id = self.db_manager.create_session(name.strip(), str(self.model_path) if self.model_path else "")
                    self.chat.clear()
                    self.history.clear()
                    self._last_speaker = None
                    self.current_kv_cache = None
                    self.append_message("system", f" Started new session: {name.strip()} (ID: {self.session_id})")
                    self.append_message("system", "-" * 50)
                    logger.info(f"Created new session {self.session_id}: {name}")
                else:
                    self.session_id = int(time.time())
                    self.chat.clear()
                    self.history.clear()
                    self._last_speaker = None
                    self.current_kv_cache = None
                    self.append_message("system", f"Started temporary session: {name} (database unavailable)")
            except Exception as e:
                error_msg = f"Error creating session: {e}"
                self.append_message("system", error_msg)
                logger.error(error_msg)
        elif ok and not name.strip():
            self.append_message("system", "Session name cannot be empty.")

    def load_session(self):
        """Load a previous session from database"""
        if not self.db_manager or not self.db_manager.db:
            self.append_message("system", "Database not available")
            return

        try:
            sessions = self.db_manager.get_sessions(50)

            if not sessions:
                self.append_message("system", "No previous sessions found")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Load Session")
            dialog.setMinimumWidth(700)
            dialog.setMinimumHeight(400)

            layout = QVBoxLayout(dialog)
            instructions = QLabel("Select a session to load:")
            layout.addWidget(instructions)

            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["ID", "Session Name", "Model", "Created", "Messages"])
            table.horizontalHeader().setStretchLastSection(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

            table.setColumnWidth(0, 50)
            table.setColumnWidth(1, 200)
            table.setColumnWidth(2, 300)
            table.setColumnWidth(3, 150)
            table.setColumnWidth(4, 80)

            table.setRowCount(len(sessions))
            for i, session in enumerate(sessions):
                id, name, model, created, msg_count = session
                created_local = format_timestamp(created)

                if model:
                    model_display = os.path.basename(model)
                    if len(model_display) > 40:
                        model_display = "..." + model_display[-37:]
                else:
                    model_display = "Unknown"

                table.setItem(i, 0, QTableWidgetItem(str(id)))
                table.setItem(i, 1, QTableWidgetItem(name or "Unnamed"))
                table.setItem(i, 2, QTableWidgetItem(model_display))
                table.setItem(i, 3, QTableWidgetItem(created_local))
                table.setItem(i, 4, QTableWidgetItem(str(msg_count)))

            table.resizeColumnsToContents()
            table.setColumnWidth(1, 200)
            table.setColumnWidth(2, 300)
            layout.addWidget(table)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            apply_theme(dialog)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                current_row = table.currentRow()
                if current_row >= 0:
                    session_id = int(table.item(current_row, 0).text())
                    self.switch_to_session(session_id)

        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.append_message("system", f"Error loading sessions: {str(e)[:100]}")

    def switch_to_session(self, session_id):
        """Switch to a different session"""
        try:
            session_info = self.db_manager.get_session_info(session_id)
            if not session_info:
                self.append_message("system", f"Session {session_id} not found")
                return

            session_name, model_path, session_created = session_info
            messages = self.db_manager.get_session_messages(session_id)
            created_display = format_timestamp(session_created) if session_created else "Unknown"

            self.chat.clear()
            self.history.clear()
            self.session_id = session_id
            self.model_path = model_path or self.model_path

            self.append_message("system", f" Loaded session: {session_name} (ID: {session_id})")
            self.append_message("system", f" Created: {created_display}")
            self.append_message("system", f" Messages: {len(messages)}")
            self.append_message("system", "-" * 50)

            for role, text, timestamp in messages:
                if role == "user":
                    self.append_message("user", text)
                    self.history.append(f"User: {text}")
                elif role == "assistant":
                    self.append_message("assistant", text)
                    self.history.append(f"Assistant: {text}")
                elif role == "system":
                    self.append_message("system", text)

            self.append_message("system", "-" * 50)
            self.append_message("system", " Session loaded. You can continue chatting.")

            logger.info(f"Switched to session {session_id}: {session_name}")

        except Exception as e:
            logger.error(f"Error switching to session {session_id}: {e}")
            self.append_message("system", f"Error loading session: {str(e)[:100]}")

    def manage_sessions(self):
        """Open session management dialog"""
        if not self.db_manager or not self.db_manager.db:
            self.append_message("system", "Database not available")
            return

        try:
            sessions = self.db_manager.get_sessions(100)

            if not sessions:
                self.append_message("system", "No sessions found")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Manage Sessions")
            dialog.setMinimumWidth(800)
            dialog.setMinimumHeight(500)

            layout = QVBoxLayout(dialog)
            instructions = QLabel("Select sessions to manage (use Ctrl/Cmd for multiple):")
            layout.addWidget(instructions)

            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["ID", "Session Name", "Model", "Created", "Messages"])
            table.horizontalHeader().setStretchLastSection(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

            table.setColumnWidth(0, 50)
            table.setColumnWidth(1, 200)
            table.setColumnWidth(2, 300)
            table.setColumnWidth(3, 150)
            table.setColumnWidth(4, 80)

            table.setRowCount(len(sessions))
            for i, session in enumerate(sessions):
                id, name, model, created, msg_count = session
                created_local = format_timestamp(created)

                if model:
                    model_display = os.path.basename(model)
                    if len(model_display) > 40:
                        model_display = "..." + model_display[-37:]
                else:
                    model_display = "Unknown"

                id_item = QTableWidgetItem(str(id))
                name_item = QTableWidgetItem(name or "Unnamed")
                model_item = QTableWidgetItem(model_display)
                created_item = QTableWidgetItem(created_local)
                msg_item = QTableWidgetItem(str(msg_count))

                for item in [id_item, name_item, model_item, created_item, msg_item]:
                    item.setData(Qt.ItemDataRole.UserRole, id)

                table.setItem(i, 0, id_item)
                table.setItem(i, 1, name_item)
                table.setItem(i, 2, model_item)
                table.setItem(i, 3, created_item)
                table.setItem(i, 4, msg_item)

            table.resizeColumnsToContents()
            table.setColumnWidth(1, 200)
            table.setColumnWidth(2, 300)
            layout.addWidget(table)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(lambda: table.selectAll())
            button_box.addButton(select_all_btn, QDialogButtonBox.ButtonRole.ActionRole)

            rename_btn = QPushButton("Rename Selected")
            rename_btn.clicked.connect(lambda: self.rename_session_from_table(table))
            button_box.addButton(rename_btn, QDialogButtonBox.ButtonRole.ActionRole)

            delete_btn = QPushButton("Delete Selected")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff4444;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ff6666;
                }
            """)
            delete_btn.clicked.connect(lambda: self.delete_multiple_sessions(table))
            button_box.addButton(delete_btn, QDialogButtonBox.ButtonRole.ActionRole)

            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            total_sessions = len(sessions)
            total_messages = sum(s[4] for s in sessions)
            stats_label = QLabel(f"Total: {total_sessions} sessions, {total_messages} messages")
            stats_label.setStyleSheet("padding: 5px; background-color: #333333; color: #00ff00;")
            layout.addWidget(stats_label)

            apply_theme(dialog)
            dialog.exec()

        except Exception as e:
            logger.error(f"Error managing sessions: {e}")
            import traceback
            traceback.print_exc()
            self.append_message("system", f"Error managing sessions: {str(e)[:100]}")

    def rename_session_from_table(self, table):
        """Rename selected session"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a session to rename.")
            return

        if len(selected_rows) > 1:
            QMessageBox.warning(self, "Multiple Selection", "Please select only one session to rename.")
            return

        row = list(selected_rows)[0]
        session_id = int(table.item(row, 0).text())
        current_name = table.item(row, 1).text()

        new_name, ok = QInputDialog.getText(self, "Rename Session", "Enter new session name:", text=current_name)

        if ok and new_name.strip():
            try:
                self.db_manager.rename_session(session_id, new_name.strip())
                table.item(row, 1).setText(new_name.strip())

                if session_id == self.session_id:
                    self.append_message("system", f"Session renamed to: {new_name.strip()}")

                QMessageBox.information(self, "Success", "Session renamed successfully.")

            except Exception as e:
                logger.error(f"Error renaming session: {e}")
                QMessageBox.critical(self, "Error", f"Failed to rename session: {str(e)[:100]}")

    def delete_multiple_sessions(self, table):
        """Delete multiple selected sessions"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one session to delete.")
            return

        selected_rows = sorted(list(selected_rows))
        session_details = []
        session_ids = []
        current_session_included = False

        for row in selected_rows:
            session_id = int(table.item(row, 0).text())
            session_name = table.item(row, 1).text()
            msg_count = int(table.item(row, 4).text())

            session_ids.append(session_id)
            session_details.append(f"  - {session_name} (ID: {session_id}, {msg_count} messages)")

            if session_id == self.session_id:
                current_session_included = True

        if len(selected_rows) == 1:
            msg = f"Are you sure you want to delete this session?\n\n{session_details[0]}"
        else:
            msg = f"Are you sure you want to delete {len(selected_rows)} sessions?\n\n"
            msg += "\n".join(session_details[:5])
            if len(selected_rows) > 5:
                msg += f"\n  ... and {len(selected_rows) - 5} more"

        msg += "\n\nThis action cannot be undone!"

        if current_session_included:
            msg += "\n\nCurrent session is selected - you will be switched to a new session."

        reply = QMessageBox.question(self, "Confirm Delete", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if current_session_included:
                    self.new_session()

                self.db_manager.delete_sessions(session_ids)

                for row in reversed(selected_rows):
                    table.removeRow(row)

                QMessageBox.information(self, "Success", f"Successfully deleted {len(selected_rows)} session(s).")

                if table.rowCount() == 0:
                    QMessageBox.information(self, "No Sessions", "No sessions remaining. Closing manager.")
                    parent_dialog = table.window()
                    if isinstance(parent_dialog, QDialog):
                        parent_dialog.reject()

            except Exception as e:
                logger.error(f"Error deleting sessions: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete sessions: {str(e)[:100]}")

    # ==================== MENU ACTIONS ====================

    def show_preferences(self):
        """Show preferences dialog"""
        dlg = PreferencesDialog(parent=self, apply_theme_callback=self.refresh_theme, select_storage_callback=self.select_storage)
        dlg.exec()

    def refresh_theme(self):
        """Refresh theme for main window and all messages"""
        from Tangi.ui.theme import apply_theme_to_application, apply_theme
        
        # Prevent recursive theme changes
        if self._refreshing_theme:
            return
        
        self._refreshing_theme = True
        
        try:
            apply_theme_to_application()
            apply_theme(self)
            
            # Refresh any open dialogs
            for child in self.findChildren(PreferencesDialog):
                if hasattr(child, 'refresh_theme'):
                    child.refresh_theme()
            
            self.update()
            self.chat.update()
        finally:
            self._refreshing_theme = False

    def show_index_manager(self):
        """Show the index manager dialog"""
        from Tangi.ui.index_manager_dialog import IndexManagerDialog
        dialog = IndexManagerDialog(self)
        dialog.exec()

    def set_rag_model(self, model_name):
        """Set the RAG model to use"""
        self.rag_model = model_name
        self.append_message("system", f"RAG model set to: {model_name}")
        logger.info(f"RAG model changed to: {model_name}")

    def set_current_codebase(self, path, collection_name, chunk_count):
        """Set the current codebase context from the index manager"""
        self.current_codebase_metadata = {
            'path': path,
            'collection': collection_name,
            'chunks': int(chunk_count) if str(chunk_count).isdigit() else 0,
            'loaded': True
        }
        self.current_code_context = []
        self.append_message("system", f"Active codebase: {path} ({chunk_count} chunks)")
        logger.info(f"Active codebase set to: {path} ({chunk_count} chunks)")

    def show_about(self):
        """Show about dialog"""
        dlg = AboutDialog(self)
        dlg.exec()

    def select_storage(self):
        """Change storage directory"""
        try:
            dialog = themed_file_dialog(self, "Select Storage Directory", "", "")
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

            if dialog.exec():
                files = dialog.selectedFiles()
                if files:
                    path = files[0]

                    if self.db_manager:
                        self.db_manager.close()

                    self.db_path = os.path.join(path, "chatlogs.db")
                    self.init_database()
                    self.auto_create_session()

                    allocated_gb = (SYSTEM_RAM_MB * self.ram_percentage / 100) / 1024
                    self.status_label.setText(f"Storage: {path} - RAM: {self.ram_percentage}% ({allocated_gb:.1f}GB)")
                    logger.info(f"Storage changed to: {path}")

        except Exception as e:
            error_msg = f"Error changing storage: {e}"
            self.append_message("system", error_msg)
            logger.error(error_msg)

    # ==================== CLOSE EVENT ====================

    def closeEvent(self, event):
        """Handle application close"""
        logger.info("Application closing, cleaning up...")

        if hasattr(self, 'settings') and hasattr(self, 'tab_widget'):
            self.settings.setValue("last_tab", self.tab_widget.currentIndex())

        if self.model_loader and self.model_loader.isRunning():
            self.model_loader.stop()

        if self.llm_worker and self.llm_worker.isRunning():
            self.llm_worker.stop()

        if self.db_manager:
            self.db_manager.close()

        if self.llm:
            try:
                if hasattr(self.llm, 'close'):
                    self.llm.close()
                elif hasattr(self.llm, 'reset'):
                    self.llm.reset()
            except Exception:
                pass
            import gc
            gc.collect()

        event.accept()


__all__ = ['RawChat']