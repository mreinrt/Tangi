import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from Tangi.ui.theme import apply_theme

logger = logging.getLogger(__name__)

class RAGModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("RAG Model Management")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Select which embedding model to use for code indexing.\n"
            "Models are stored in ~/.cache/huggingface/hub/"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Model list group
        model_group = QGroupBox("Available RAG Models")
        model_layout = QVBoxLayout()
        
        self.model_list = QListWidget()
        self.populate_model_list()
        model_layout.addWidget(self.model_list)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Button row
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.populate_model_list)

        self.download_btn = QPushButton("📥 Download New Model")
        self.download_btn.clicked.connect(self.download_model)

        self.browse_btn = QPushButton("📂 Browse Local Models")
        self.browse_btn.clicked.connect(self.browse_local_models)

        self.use_btn = QPushButton("✅ Use Selected Model")
        self.use_btn.clicked.connect(self.use_selected_model)

        # Add buttons in logical order
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.browse_btn)
        button_layout.addWidget(self.use_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        apply_theme(self)
    
    def populate_model_list(self):
        """Populate list of available RAG models from HF cache"""
        self.model_list.clear()
        
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        
        if not cache_dir.exists():
            self.model_list.addItem("No models found in cache")
            return
        
        # Look for sentence-transformers models
        models_found = False
        for item in cache_dir.glob("models--*"):
            if item.is_dir():
                models_found = True
                # Extract model name from directory name
                model_name = item.name.replace("models--", "").replace("--", "/")
                
                # Check if it's fully downloaded (has snapshots)
                snapshots_dir = item / "snapshots"
                if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                    # Get size
                    size = self.get_dir_size(item)
                    size_str = self.format_size(size)
                    
                    display_text = f"{model_name} ({size_str})"
                    list_item = QListWidgetItem(display_text)
                    list_item.setData(Qt.ItemDataRole.UserRole, str(item))
                    
                    # Check if this is the currently used model
                    if hasattr(self.parent, 'rag_model') and self.parent.rag_model == model_name:
                        font = QFont()
                        font.setBold(True)
                        list_item.setFont(font)
                    
                    self.model_list.addItem(list_item)
        
        if not models_found:
            self.model_list.addItem("No sentence-transformers models found")
    
    def get_dir_size(self, path):
        """Get directory size in bytes"""
        total = 0
        try:
            for entry in path.rglob('*'):
                if entry.is_file():
                    total += entry.stat().st_size
        except:
            pass
        return total
    
    def format_size(self, size):
        """Format size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def download_model(self):
        """Download a new RAG model"""
        from PyQt6.QtWidgets import QInputDialog
        
        model_name, ok = QInputDialog.getText(
            self,
            "Download RAG Model",
            "Enter Hugging Face model ID (e.g., sentence-transformers/all-MiniLM-L6-v2):"
        )
        
        if ok and model_name.strip():
            # Trigger download via HF CLI
            if hasattr(self.parent, 'process_prompt'):
                self.parent.process_prompt(f"/hf download {model_name.strip()}")
                QTimer.singleShot(2000, self.populate_model_list)  # Refresh after delay
    
    def browse_local_models(self):
        """Open file dialog to browse for local models"""
        from PyQt6.QtWidgets import QFileDialog
        
        # Start in HF cache directory
        cache_dir = str(Path.home() / ".cache" / "huggingface" / "hub")
        
        # Open directory dialog
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Model Directory",
            cache_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if selected_dir:
            # Check if it looks like a valid model directory
            selected_path = Path(selected_dir)
            
            # Look for model files
            has_model_files = False
            model_files = list(selected_path.glob("*.bin")) + list(selected_path.glob("*.safetensors"))
            
            if model_files:
                has_model_files = True
                # Try to determine model name
                model_name = selected_path.name
                
                # Check if it's in HF cache structure
                if "models--" in str(selected_path):
                    # Extract from HF cache path
                    parts = str(selected_path).split("models--")
                    if len(parts) > 1:
                        model_name = parts[1].split(os.sep)[0].replace("--", "/")
                
                # Add to list if not already there
                items = [self.model_list.item(i).text() for i in range(self.model_list.count())]
                if not any(model_name in item for item in items):
                    # Get size
                    size = self.get_dir_size(selected_path)
                    size_str = self.format_size(size)
                    
                    display_text = f"{model_name} ({size_str}) [local]"
                    list_item = QListWidgetItem(display_text)
                    list_item.setData(Qt.ItemDataRole.UserRole, str(selected_path))
                    self.model_list.addItem(list_item)
                    self.model_list.setCurrentItem(list_item)
                    
                    QMessageBox.information(
                        self, 
                        "Model Added", 
                        f"Added local model:\n{model_name}\n\nPath: {selected_path}"
                    )
                else:
                    QMessageBox.information(self, "Model Exists", "This model is already in the list.")
            else:
                QMessageBox.warning(
                    self, 
                    "Invalid Model Directory", 
                    "Selected directory doesn't contain model files (.bin or .safetensors)"
                )

    def use_selected_model(self):
        """Use the selected model for RAG"""
        current = self.model_list.currentItem()
        if not current or current.text() == "No models found in cache":
            QMessageBox.warning(self, "No Selection", "Please select a model to use.")
            return
        
        model_name = current.text().split(" (")[0]  # Remove size info
        
        # Store the selected model in parent
        if hasattr(self.parent, 'set_rag_model'):
            self.parent.set_rag_model(model_name)
            QMessageBox.information(self, "Success", f"Now using RAG model: {model_name}")
            self.accept()
        else:
            QMessageBox.information(self, "Info", f"Selected model: {model_name}")