#!/usr/bin/env python3
"""
AWS S3 Bucket Browser GUI
A comprehensive S3 browser with preview and authenticated delete functionality.
"""

import sys
import os
import io
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QLabel,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QStatusBar,
    QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QGroupBox,
    QCheckBox, QSpinBox, QTabWidget, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QIcon

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3Worker(QObject):
    """Worker thread for S3 operations"""
    
    bucket_listed = Signal(list)  # List of objects
    object_downloaded = Signal(bytes, str)  # Content and content type
    object_deleted = Signal(str)  # Object key
    error_occurred = Signal(str)  # Error message
    progress_updated = Signal(int)  # Progress percentage
    
    def __init__(self):
        super().__init__()
        self.s3_client = None
        self.current_bucket = None
        
    def set_credentials(self, access_key: str, secret_key: str, region: str):
        """Set AWS credentials"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            # Test connection
            self.s3_client.list_buckets()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to connect to AWS: {str(e)}")
            return False
    
    def list_buckets(self) -> List[str]:
        """List all available buckets"""
        if not self.s3_client:
            return []
        
        try:
            response = self.s3_client.list_buckets()
            return [bucket['Name'] for bucket in response['Buckets']]
        except Exception as e:
            self.error_occurred.emit(f"Failed to list buckets: {str(e)}")
            return []
    
    def list_objects(self, bucket_name: str, prefix: str = ""):
        """List objects in bucket"""
        if not self.s3_client:
            self.error_occurred.emit("S3 client not initialized")
            return
        
        try:
            self.current_bucket = bucket_name
            objects = []
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'Key': obj['Key'],
                            'Size': obj['Size'],
                            'LastModified': obj['LastModified'],
                            'ETag': obj['ETag'].strip('"')
                        })
            
            self.bucket_listed.emit(objects)
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to list objects: {str(e)}")
    
    def download_object(self, bucket_name: str, key: str):
        """Download object content for preview"""
        if not self.s3_client:
            self.error_occurred.emit("S3 client not initialized")
            return
        
        try:
            # Get object metadata first
            head_response = self.s3_client.head_object(Bucket=bucket_name, Key=key)
            content_type = head_response.get('ContentType', 'application/octet-stream')
            
            # Download object
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read()
            
            self.object_downloaded.emit(content, content_type)
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to download object: {str(e)}")
    
    def delete_object(self, bucket_name: str, key: str):
        """Delete object from bucket"""
        if not self.s3_client:
            self.error_occurred.emit("S3 client not initialized")
            return
        
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=key)
            self.object_deleted.emit(key)
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to delete object: {str(e)}")


class AuthenticationDialog(QDialog):
    """Dialog for delete authentication"""
    
    def __init__(self, parent=None, object_key: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Confirm Delete Operation")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        
        # Warning message
        warning = QLabel(f"⚠️ You are about to delete:\n\n{object_key}\n\nThis action cannot be undone!")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: red; font-weight: bold; padding: 10px;")
        layout.addWidget(warning)
        
        # Authentication input
        auth_group = QGroupBox("Authentication Required")
        auth_layout = QFormLayout()
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter admin password")
        auth_layout.addRow("Password:", self.password_input)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        self.password_input.setFocus()
    
    def get_password(self) -> str:
        return self.password_input.text()


class CredentialsDialog(QDialog):
    """Dialog for AWS credentials input"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AWS Credentials")
        self.setModal(True)
        self.setFixedSize(450, 250)
        
        layout = QVBoxLayout()
        
        # Instructions
        info = QLabel("Enter your AWS credentials to connect to S3:")
        layout.addWidget(info)
        
        # Credentials form
        form_layout = QFormLayout()
        
        self.access_key_input = QLineEdit()
        self.access_key_input.setPlaceholderText("AKIA...")
        form_layout.addRow("Access Key ID:", self.access_key_input)
        
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Secret Access Key:", self.secret_key_input)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems([
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-central-1', 'ap-southeast-1', 'ap-northeast-1'
        ])
        form_layout.addRow("Region:", self.region_combo)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_credentials(self) -> tuple:
        return (
            self.access_key_input.text(),
            self.secret_key_input.text(),
            self.region_combo.currentText()
        )


class S3BrowserMainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AWS S3 Bucket Browser")
        self.setGeometry(100, 100, 1200, 800)
        
        # Admin password for delete operations
        self.admin_password = "admin123"  # Change this in production
        
        # Initialize worker
        self.worker_thread = QThread()
        self.s3_worker = S3Worker()
        self.s3_worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.s3_worker.bucket_listed.connect(self.populate_object_tree)
        self.s3_worker.object_downloaded.connect(self.display_object_preview)
        self.s3_worker.object_deleted.connect(self.handle_object_deleted)
        self.s3_worker.error_occurred.connect(self.show_error)
        
        self.worker_thread.start()
        
        # Current state
        self.current_bucket = None
        self.current_objects = []
        
        self.setup_ui()
        self.show_credentials_dialog()
    
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        # Bucket selection
        controls_layout.addWidget(QLabel("Bucket:"))
        self.bucket_combo = QComboBox()
        self.bucket_combo.currentTextChanged.connect(self.on_bucket_changed)
        controls_layout.addWidget(self.bucket_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_current_bucket)
        controls_layout.addWidget(self.refresh_btn)
        
        # Connection status
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red;")
        controls_layout.addWidget(self.connection_status)
        
        controls_layout.addStretch()
        
        # Reconnect button
        self.reconnect_btn = QPushButton("Reconnect")
        self.reconnect_btn.clicked.connect(self.show_credentials_dialog)
        controls_layout.addWidget(self.reconnect_btn)
        
        layout.addLayout(controls_layout)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Object tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Objects:"))
        
        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderLabels(["Name", "Size", "Modified", "ETag"])
        self.object_tree.itemClicked.connect(self.on_object_selected)
        left_layout.addWidget(self.object_tree)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected_object)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #ff4444; color: white; }")
        left_layout.addWidget(self.delete_btn)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Preview:"))
        
        # Preview tabs
        self.preview_tabs = QTabWidget()
        
        # Text preview
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.preview_tabs.addTab(self.text_preview, "Text")
        
        # Raw preview
        self.raw_preview = QTextEdit()
        self.raw_preview.setReadOnly(True)
        self.raw_preview.setFont(QFont("Courier", 10))
        self.preview_tabs.addTab(self.raw_preview, "Raw")
        
        # Image preview
        self.image_preview = QScrollArea()
        self.image_label = QLabel("No image selected")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_preview.setWidget(self.image_label)
        self.preview_tabs.addTab(self.image_preview, "Image")
        
        right_layout.addWidget(self.preview_tabs)
        
        # Object info
        self.object_info = QTextEdit()
        self.object_info.setReadOnly(True)
        self.object_info.setMaximumHeight(100)
        right_layout.addWidget(self.object_info)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def show_credentials_dialog(self):
        """Show credentials input dialog"""
        if not BOTO3_AVAILABLE:
            QMessageBox.critical(
                self, "Missing Dependency",
                "boto3 library is required. Install it with:\npip install boto3"
            )
            return
        
        dialog = CredentialsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            access_key, secret_key, region = dialog.get_credentials()
            
            if access_key and secret_key:
                self.progress_bar.setVisible(True)
                self.status_bar.showMessage("Connecting to AWS...")
                
                if self.s3_worker.set_credentials(access_key, secret_key, region):
                    self.connection_status.setText("Connected")
                    self.connection_status.setStyleSheet("color: green;")
                    self.load_buckets()
                else:
                    self.connection_status.setText("Failed")
                    self.connection_status.setStyleSheet("color: red;")
                
                self.progress_bar.setVisible(False)
                self.status_bar.clearMessage()
    
    def load_buckets(self):
        """Load available buckets"""
        buckets = self.s3_worker.list_buckets()
        self.bucket_combo.clear()
        self.bucket_combo.addItems(buckets)
    
    def on_bucket_changed(self, bucket_name: str):
        """Handle bucket selection change"""
        if bucket_name and bucket_name != self.current_bucket:
            self.current_bucket = bucket_name
            self.refresh_current_bucket()
    
    def refresh_current_bucket(self):
        """Refresh current bucket contents"""
        if self.current_bucket:
            self.progress_bar.setVisible(True)
            self.status_bar.showMessage(f"Loading objects from {self.current_bucket}...")
            self.s3_worker.list_objects(self.current_bucket)
    
    def populate_object_tree(self, objects: List[Dict[str, Any]]):
        """Populate the object tree with S3 objects"""
        self.object_tree.clear()
        self.current_objects = objects
        
        for obj in objects:
            item = QTreeWidgetItem()
            item.setText(0, obj['Key'])
            item.setText(1, self.format_size(obj['Size']))
            item.setText(2, obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'))
            item.setText(3, obj['ETag'][:16] + '...' if len(obj['ETag']) > 16 else obj['ETag'])
            item.setData(0, Qt.UserRole, obj)
            self.object_tree.addTopLevelItem(item)
        
        self.object_tree.resizeColumnToContents(0)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"Loaded {len(objects)} objects")
        
        # Clear selection
        self.delete_btn.setEnabled(False)
        self.clear_preview()
    
    def on_object_selected(self, item: QTreeWidgetItem):
        """Handle object selection"""
        obj_data = item.data(0, Qt.UserRole)
        if obj_data:
            self.delete_btn.setEnabled(True)
            self.load_object_preview(obj_data)
    
    def load_object_preview(self, obj_data: Dict[str, Any]):
        """Load preview for selected object"""
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(f"Loading preview for {obj_data['Key']}...")
        
        # Show object info
        info = f"Key: {obj_data['Key']}\n"
        info += f"Size: {self.format_size(obj_data['Size'])}\n"
        info += f"Modified: {obj_data['LastModified']}\n"
        info += f"ETag: {obj_data['ETag']}"
        self.object_info.setText(info)
        
        self.s3_worker.download_object(self.current_bucket, obj_data['Key'])
    
    def display_object_preview(self, content: bytes, content_type: str):
        """Display object preview"""
        try:
            # Text preview
            if content_type.startswith('text/') or content_type == 'application/json':
                text_content = content.decode('utf-8')
                self.text_preview.setText(text_content)
                self.preview_tabs.setCurrentIndex(0)  # Text tab
            else:
                self.text_preview.setText(f"Binary content ({content_type})\nSize: {len(content)} bytes")
            
            # Raw preview (hex dump)
            hex_content = ' '.join(f'{b:02x}' for b in content[:1000])  # First 1000 bytes
            if len(content) > 1000:
                hex_content += '\n... (truncated)'
            self.raw_preview.setText(hex_content)
            
            # Image preview
            if content_type.startswith('image/'):
                pixmap = QPixmap()
                if pixmap.loadFromData(content):
                    # Scale image to fit
                    scaled_pixmap = pixmap.scaled(600, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_label.setPixmap(scaled_pixmap)
                    self.preview_tabs.setCurrentIndex(2)  # Image tab
                else:
                    self.image_label.setText("Failed to load image")
            else:
                self.image_label.setText("Not an image file")
            
        except UnicodeDecodeError:
            self.text_preview.setText(f"Binary content ({content_type})\nCannot display as text")
        
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
    
    def clear_preview(self):
        """Clear all preview content"""
        self.text_preview.clear()
        self.raw_preview.clear()
        self.image_label.clear()
        self.image_label.setText("No image selected")
        self.object_info.clear()
    
    def delete_selected_object(self):
        """Delete selected object with authentication"""
        current_item = self.object_tree.currentItem()
        if not current_item:
            return
        
        obj_data = current_item.data(0, Qt.UserRole)
        if not obj_data:
            return
        
        # Show authentication dialog
        auth_dialog = AuthenticationDialog(self, obj_data['Key'])
        if auth_dialog.exec() == QDialog.Accepted:
            password = auth_dialog.get_password()
            
            if password == self.admin_password:
                # Proceed with deletion
                self.progress_bar.setVisible(True)
                self.status_bar.showMessage(f"Deleting {obj_data['Key']}...")
                self.s3_worker.delete_object(self.current_bucket, obj_data['Key'])
            else:
                QMessageBox.warning(self, "Authentication Failed", "Incorrect password!")
    
    def handle_object_deleted(self, key: str):
        """Handle successful object deletion"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"Deleted {key}")
        
        # Refresh the bucket
        QTimer.singleShot(1000, self.refresh_current_bucket)
        
        # Clear selection and preview
        self.delete_btn.setEnabled(False)
        self.clear_preview()
        
        QMessageBox.information(self, "Success", f"Object '{key}' was deleted successfully.")
    
    def show_error(self, error_message: str):
        """Show error message"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Error occurred")
        QMessageBox.critical(self, "Error", error_message)
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format byte size to human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} PB"
    
    def closeEvent(self, event):
        """Clean up on application close"""
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()


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