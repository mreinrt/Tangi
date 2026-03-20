from PyQt6.QtCore import QThread, pyqtSignal
from Tangi.rag.indexer import CodeIndexer

class IndexWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
    
    def run(self):
        try:
            self.progress.emit("Loading embedding model...")
            indexer = CodeIndexer()
            
            self.progress.emit("Scanning files...")
            chunk_count = indexer.index_directory(self.directory)
            
            self.finished.emit(chunk_count)
        except Exception as e:
            self.error.emit(str(e))