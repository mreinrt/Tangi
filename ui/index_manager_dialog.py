import os
import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QApplication,
    QFileDialog, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont 

from Tangi.ui.theme import apply_theme
from Tangi.ui.rag_model_dialog import RAGModelDialog

logger = logging.getLogger(__name__)

class IndexManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Manage Index")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Manage your indexed codebases and RAG models.\n"
            "Select a directory to index or remove existing indexes."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Indexed projects group
        index_group = QGroupBox("Indexed Codebases")
        index_layout = QVBoxLayout()
        
        self.index_list = QListWidget()
        self.index_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Allow multi-select
        self.populate_index_list()
        index_layout.addWidget(self.index_list)
        
        # Index buttons
        index_btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton(" Add Directory to Index")
        self.add_btn.clicked.connect(self.add_index)
        
        self.remove_btn = QPushButton(" Remove Selected")
        self.remove_btn.clicked.connect(self.remove_index)
        
        self.select_btn = QPushButton(" Select CodeBase")
        self.select_btn.clicked.connect(self.select_codebase)
        
        self.refresh_btn = QPushButton(" Refresh")
        self.refresh_btn.clicked.connect(self.populate_index_list)
        
        index_btn_layout.addWidget(self.add_btn)
        index_btn_layout.addWidget(self.remove_btn)
        index_btn_layout.addWidget(self.select_btn)
        index_btn_layout.addWidget(self.refresh_btn)
        index_btn_layout.addStretch()
        
        index_layout.addLayout(index_btn_layout)
        index_group.setLayout(index_layout)
        layout.addWidget(index_group)
        
        # RAG Model Management button
        rag_group = QGroupBox("RAG Model")
        rag_layout = QVBoxLayout()
        
        self.current_model_label = QLabel("Current model: Not set")
        self.update_current_model_label()
        rag_layout.addWidget(self.current_model_label)
        
        self.manage_rag_btn = QPushButton(" Manage RAG Models")
        self.manage_rag_btn.clicked.connect(self.open_rag_dialog)
        rag_layout.addWidget(self.manage_rag_btn)
        
        rag_group.setLayout(rag_layout)
        layout.addWidget(rag_group)

        # Bottom row with status and close button
        bottom_layout = QHBoxLayout()
        
        # Status label on the left
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888; font-style: italic;")
        bottom_layout.addWidget(self.status_label)
        
        # Close button on the right
        bottom_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)
        
        layout.addLayout(bottom_layout)
        
        apply_theme(self)
        
        # Store reverse mapping for later use
        self.reverse_mapping = {}
        self.populate_index_list()
    
    def populate_index_list(self):
        """Populate list of indexed projects"""
        self.index_list.clear()
        
        index_dir = Path.home() / ".Tangi" / "code_index"
        mapping_file = Path.home() / ".Tangi" / "collection_mapping.json"
        
        if not index_dir.exists():
            self.index_list.addItem("No indexes found")
            return
        
        # Load mapping
        mapping = {}
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r') as f:
                    mapping = json.load(f)
            except:
                pass
        
        # Reverse mapping: collection name -> original path
        self.reverse_mapping = {v: k for k, v in mapping.items()}
        
        # Use ChromaDB API to get valid collections
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(index_dir))
            
            # Get collection objects from ChromaDB (returns list of Collection objects)
            collections = client.list_collections()
            
            for collection_obj in collections:
                try:
                    collection_name = collection_obj.name
                    count = collection_obj.count()
                    
                    # Get original path from reverse mapping
                    original_path = self.reverse_mapping.get(collection_name, "Unknown")
                    
                    item_text = f"{original_path} ({count} chunks)"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, collection_name)
                    
                    # Check if this is the currently active index
                    if hasattr(self.parent, 'current_code_context') and self.parent.current_code_context:
                        ctx_path = self.parent.current_code_context.get('path', '')
                        if original_path == ctx_path:
                            font = item.font()
                            font.setBold(True)
                            item.setFont(font)
                    
                    self.index_list.addItem(item)
                    
                except Exception as e:
                    # Still try to add from mapping if available
                    if collection_obj.name in self.reverse_mapping:
                        original_path = self.reverse_mapping[collection_obj.name]
                        item_text = f"{original_path} (unknown chunks)"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.ItemDataRole.UserRole, collection_obj.name)
                        self.index_list.addItem(item)
            
            # If no collections found, check if we have any in mapping
            if not collections and self.reverse_mapping:
                for collection_name, original_path in self.reverse_mapping.items():
                    item_text = f"{original_path} (unknown chunks)"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, collection_name)
                    self.index_list.addItem(item)
            
        except Exception as e:
            # Fall back to mapping only
            if self.reverse_mapping:
                for collection_name, original_path in self.reverse_mapping.items():
                    item_text = f"{original_path} (unknown chunks)"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, collection_name)
                    self.index_list.addItem(item)
            else:
                self.index_list.addItem("No valid indexes found")
    
    def select_codebase(self):
        """Select the chosen codebase for use in the main window"""
        current = self.index_list.currentItem()
        if not current or current.text() == "No indexes found" or "Unknown" in current.text():
            QMessageBox.warning(self, "No Selection", "Please select a valid codebase to use.")
            return
        
        # Extract path from item text
        text = current.text()
        path = text.split(" (")[0]  # Remove chunk count
        
        # Extract chunk count
        chunk_count = "0"
        if "(" in text and ")" in text:
            chunk_count = text.split("(")[1].split(" ")[0]
        
        # Get collection name from item data
        collection_name = current.data(Qt.ItemDataRole.UserRole)
        
        if not collection_name:
            QMessageBox.warning(self, "Error", "Could not find collection for selected path.")
            return
        
        # Set as current context in parent
        if hasattr(self.parent, 'set_current_codebase'):
            self.parent.set_current_codebase(path, collection_name, chunk_count)
            self.accept()  # Close dialog
    
    def add_index(self):
        """Add a new directory to index"""
        from PyQt6.QtWidgets import QFileDialog
        from Tangi.workers.index_worker import IndexWorker
        
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory to Index",
            str(Path.home())
        )
        
        if directory:
            # Start animation
            self.animating = True
            self.dot_count = 0
            self.animate_dots()
            
            # Create and start worker thread
            self.index_worker = IndexWorker(directory)
            self.index_worker.progress.connect(self.update_status)
            self.index_worker.finished.connect(self.on_index_finished)
            self.index_worker.error.connect(self.on_index_error)
            self.index_worker.start()

    def on_index_finished(self, chunk_count):
        """Handle successful indexing"""
        self.animating = False
        self.update_status(f"Index complete! {chunk_count} chunks")
        self.populate_index_list()
        QTimer.singleShot(3000, lambda: self.update_status(""))

    def on_index_error(self, error_msg):
        """Handle indexing error"""
        self.animating = False
        self.update_status(f"Error: {error_msg}")
        QTimer.singleShot(5000, lambda: self.update_status(""))

    def animate_dots(self):
        """Animate the status dots continuously"""
        if not self.animating:
            return
        
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        
        self.status_label.setText(f"Please Wait, Indexing{dots}")
        QApplication.processEvents()
        
        if self.animating:
            QTimer.singleShot(500, self.animate_dots)

    def refresh_clicked(self):
        """Handle refresh button click"""
        self.animating = False
        self.update_status("")
        self.populate_index_list()

    def update_status(self, message):
        """Update the status label"""
        self.status_label.setText(message)
        QApplication.processEvents()

    def remove_index(self):
        """Remove selected index(s)"""
        selected_items = self.index_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one index to remove.")
            return
        
        # Build list of paths to remove
        paths_to_remove = []
        for item in selected_items:
            text = item.text()
            if text == "No indexes found" or "Unknown" in text:
                continue
            path = text.split(" (")[0]
            paths_to_remove.append(path)
        
        if not paths_to_remove:
            QMessageBox.warning(self, "Invalid Selection", "Selected items cannot be removed.")
            return
        
        # Confirm deletion
        msg = f"Remove {len(paths_to_remove)} index(s)?\n\n"
        msg += "\n".join([f"  • {p}" for p in paths_to_remove[:5]])
        if len(paths_to_remove) > 5:
            msg += f"\n  ... and {len(paths_to_remove) - 5} more"
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Let the remove-index command handle everything
            for path in paths_to_remove:
                if hasattr(self.parent, 'process_prompt'):
                    self.parent.process_prompt(f"/remove-index {path}")
            
            # Refresh the list after a delay
            QTimer.singleShot(1500, self.populate_index_list)
    
    def open_rag_dialog(self):
        """Open the RAG model management dialog"""
        from Tangi.ui.rag_model_dialog import RAGModelDialog
        dialog = RAGModelDialog(self.parent)
        dialog.exec()
        self.update_current_model_label()
    
    def update_current_model_label(self):
        """Update the current model label"""
        if hasattr(self.parent, 'rag_model') and self.parent.rag_model:
            self.current_model_label.setText(f"Current model: {self.parent.rag_model}")
        else:
            self.current_model_label.setText("Current model: default (all-MiniLM-L6-v2)")