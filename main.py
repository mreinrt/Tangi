#!/usr/bin/env python3
"""
Tangi - Main entry point
Created by BigSlimThic
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication

# Fix Qt portal error
os.environ['QT_QPA_PLATFORM'] = 'xcb'

# Disable ChromaDB telemetry to prevent API mismatch errors
os.environ['CHROMA_TELEMETRY'] = 'false'
os.environ['CHROMA_API_IMPL'] = 'chromadb.api.segment.SegmentAPI'

# Ensure log directory exists before setting up logging
log_dir = os.path.expanduser("~/.Tangi")
os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "Tangi.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from Tangi.ui.main_window import RawChat
from Tangi.ui.theme import set_theme, CURRENT_THEME

def main():
    """Main application entry point"""
    # Ensure storage directory exists
    os.makedirs(os.path.expanduser("~/.Tangi"), exist_ok=True)
    
    app = QApplication(sys.argv)
    set_theme(CURRENT_THEME)

    w = RawChat()
    w.resize(900, 650)
    w.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()