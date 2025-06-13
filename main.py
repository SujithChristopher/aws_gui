#!/usr/bin/env python3
"""
AWS S3 Bucket Browser GUI
A comprehensive S3 browser with preview and authenticated delete functionality.
"""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox

from src.workers.s3_worker import BOTO3_AVAILABLE
from src.ui.main_window import S3BrowserMainWindow

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("S3 Bucket Browser")
    
    # Check if boto3 is available
    if not BOTO3_AVAILABLE:
        QMessageBox.critical(
            None, "Missing Dependency",
            "This application requires the boto3 library.\n\n"
            "Install it using:\npip install boto3"
        )
        sys.exit(1)
    
    window = S3BrowserMainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 