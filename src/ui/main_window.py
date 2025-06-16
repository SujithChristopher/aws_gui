"""
Main window class for the S3 Browser application.
"""

import sys
import os
import io
import pandas as pd
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QLabel,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QStatusBar,
    QMessageBox, QTabWidget, QScrollArea, QFrame, QDialog,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QPixmap, QFont

from ..workers.s3_worker import S3Worker, BOTO3_AVAILABLE
from .dialogs import AuthenticationDialog, CredentialsDialog
from ..utils.formatters import format_size

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
        self.s3_worker.download_completed.connect(self.handle_download_completed)
        self.s3_worker.download_progress.connect(self.update_download_progress)
        
        self.worker_thread.start()
        
        # Current state
        self.current_bucket = None
        self.current_objects = []
        self.tree_view_mode = True
        self.sort_ascending = True
        self.current_sort = "Name"
        self.selected_items = set()  # Track selected items for download
        
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
        self.bucket_combo.setEditable(True)  # Allow manual entry
        self.bucket_combo.currentTextChanged.connect(self.on_bucket_changed)
        self.bucket_combo.lineEdit().returnPressed.connect(self.on_bucket_entered)
        controls_layout.addWidget(self.bucket_combo)
        
        # Load bucket button
        self.load_bucket_btn = QPushButton("Load Bucket")
        self.load_bucket_btn.clicked.connect(self.load_current_bucket)
        controls_layout.addWidget(self.load_bucket_btn)
        
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
        
        # Tree controls
        tree_controls = QHBoxLayout()
        tree_controls.addWidget(QLabel("Objects:"))
        
        # View mode toggle
        self.view_mode_btn = QPushButton("Tree View")
        self.view_mode_btn.setCheckable(True)
        self.view_mode_btn.setChecked(True)
        self.view_mode_btn.clicked.connect(self.toggle_view_mode)
        tree_controls.addWidget(self.view_mode_btn)
        
        # Sort options
        tree_controls.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Size", "Date Modified"])
        self.sort_combo.currentTextChanged.connect(self.sort_objects)
        tree_controls.addWidget(self.sort_combo)
        
        # Sort order
        self.sort_order_btn = QPushButton("↑")  # Ascending
        self.sort_order_btn.setMaximumWidth(30)
        self.sort_order_btn.setCheckable(True)
        self.sort_order_btn.clicked.connect(self.toggle_sort_order)
        tree_controls.addWidget(self.sort_order_btn)
        
        tree_controls.addStretch()
        left_layout.addLayout(tree_controls)
        
        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderLabels(["Name", "Size", "Modified", "ETag"])
        self.object_tree.itemClicked.connect(self.on_object_selected)
        self.object_tree.setSortingEnabled(False)  # We'll handle sorting manually
        left_layout.addWidget(self.object_tree)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected_object)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #ff4444; color: white; }")
        left_layout.addWidget(self.delete_btn)
        
        # Add download button next to delete button
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.download_selected_objects)
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("QPushButton { background-color: #44aa44; color: white; }")
        left_layout.addWidget(self.download_btn)
        
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
        
        # CSV preview
        self.csv_preview = QTableWidget()
        self.csv_preview.setAlternatingRowColors(True)
        self.csv_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.csv_preview.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.preview_tabs.addTab(self.csv_preview, "CSV")
        
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
        
        if buckets:
            self.bucket_combo.addItems(buckets)
        else:
            # If no buckets listed (no permission), add default bucket name
            self.bucket_combo.addItem("homerclouds")
            self.status_bar.showMessage("Cannot list buckets - enter bucket name manually or use default")
    
    def on_bucket_entered(self):
        """Handle manual bucket entry via Enter key"""
        self.load_current_bucket()
    
    def load_current_bucket(self):
        """Load the currently selected/entered bucket"""
        bucket_name = self.bucket_combo.currentText().strip()
        if bucket_name:
            self.current_bucket = bucket_name
            self.refresh_current_bucket()
    
    def on_bucket_changed(self, bucket_name: str):
        """Handle bucket selection change"""
        # Don't automatically load on text change since combo is editable
        # User needs to press Enter or click Load Bucket button
        pass
    
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
        
        if self.tree_view_mode:
            self.populate_tree_view(objects)
        else:
            self.populate_flat_view(objects)
        
        self.object_tree.resizeColumnToContents(0)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"Loaded {len(objects)} objects")
        
        # Clear selection
        self.delete_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.clear_preview()
    
    def populate_tree_view(self, objects: List[Dict[str, Any]]):
        """Populate tree view with folder structure"""
        # Sort objects first
        sorted_objects = self.sort_objects_list(objects)
        
        # Create folder structure
        folder_items = {}
        
        for obj in sorted_objects:
            key = obj['Key']
            parts = key.split('/')
            
            current_parent = self.object_tree.invisibleRootItem()
            current_path = ""
            
            # Create folder hierarchy
            for i, part in enumerate(parts[:-1]):  # All parts except the last (filename)
                current_path = current_path + part + "/" if current_path else part + "/"
                
                if current_path not in folder_items:
                    folder_item = QTreeWidgetItem()
                    folder_item.setText(0, part + "/")
                    folder_item.setText(1, "")  # Folders don't have size
                    folder_item.setText(2, "")  # Folders don't have modification date
                    folder_item.setText(3, "")  # Folders don't have ETag
                    folder_item.setData(0, Qt.UserRole, {"type": "folder", "path": current_path})
                    
                    # Style folders differently
                    font = folder_item.font(0)
                    font.setBold(True)
                    folder_item.setFont(0, font)
                    
                    # Check if folder is empty
                    if self.s3_worker.is_empty_folder(self.current_bucket, current_path):
                        folder_item.setText(0, part + "/ (empty)")
                        folder_item.setForeground(0, Qt.gray)
                    
                    current_parent.addChild(folder_item)
                    folder_items[current_path] = folder_item
                
                current_parent = folder_items[current_path]
            
            # Add the file to its parent folder (or root if no folders)
            filename = parts[-1]
            if filename:  # Don't add empty filenames (folder markers)
                file_item = QTreeWidgetItem()
                file_item.setText(0, filename)
                file_item.setText(1, format_size(obj['Size']))
                file_item.setText(2, obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'))
                file_item.setText(3, obj['ETag'][:16] + '...' if len(obj['ETag']) > 16 else obj['ETag'])
                file_item.setData(0, Qt.UserRole, obj)
                current_parent.addChild(file_item)
        
        # Expand first level folders
        for i in range(self.object_tree.topLevelItemCount()):
            item = self.object_tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).get("type") == "folder":
                self.object_tree.expandItem(item)
    
    def populate_flat_view(self, objects: List[Dict[str, Any]]):
        """Populate flat view (list all objects)"""
        sorted_objects = self.sort_objects_list(objects)
        
        for obj in sorted_objects:
            item = QTreeWidgetItem()
            item.setText(0, obj['Key'])
            item.setText(1, format_size(obj['Size']))
            item.setText(2, obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'))
            item.setText(3, obj['ETag'][:16] + '...' if len(obj['ETag']) > 16 else obj['ETag'])
            item.setData(0, Qt.UserRole, obj)
            self.object_tree.addTopLevelItem(item)
    
    def sort_objects_list(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort objects based on current sort settings"""
        if self.current_sort == "Name":
            key_func = lambda x: x['Key'].lower()
        elif self.current_sort == "Size":
            key_func = lambda x: x['Size']
        elif self.current_sort == "Date Modified":
            key_func = lambda x: x['LastModified']
        else:
            key_func = lambda x: x['Key'].lower()
        
        return sorted(objects, key=key_func, reverse=not self.sort_ascending)
    
    def toggle_view_mode(self):
        """Toggle between tree and flat view"""
        self.tree_view_mode = self.view_mode_btn.isChecked()
        self.view_mode_btn.setText("Tree View" if self.tree_view_mode else "Flat View")
        
        if self.current_objects:
            self.populate_object_tree(self.current_objects)
    
    def sort_objects(self, sort_type: str):
        """Handle sort type change"""
        self.current_sort = sort_type
        if self.current_objects:
            self.populate_object_tree(self.current_objects)
    
    def toggle_sort_order(self):
        """Toggle sort order between ascending and descending"""
        self.sort_ascending = not self.sort_ascending
        self.sort_order_btn.setText("↑" if self.sort_ascending else "↓")
        
        if self.current_objects:
            self.populate_object_tree(self.current_objects)
    
    def on_object_selected(self, item: QTreeWidgetItem):
        """Handle object selection"""
        obj_data = item.data(0, Qt.UserRole)
        if obj_data:
            # Check if it's a folder or file
            if isinstance(obj_data, dict) and obj_data.get("type") == "folder":
                # It's a folder, don't enable delete or load preview
                self.delete_btn.setEnabled(False)
                self.download_btn.setEnabled(True)  # Enable download for folders
                self.clear_preview()
                
                # Show folder info
                folder_path = obj_data.get("path", "")
                info = f"Folder: {folder_path}\n"
                info += f"Type: Directory"
                self.object_info.setText(info)
            else:
                # It's a file
                self.delete_btn.setEnabled(True)
                self.download_btn.setEnabled(True)
                self.load_object_preview(obj_data)
    
    def load_object_preview(self, obj_data: Dict[str, Any]):
        """Load preview for selected object"""
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(f"Loading preview for {obj_data['Key']}...")
        
        # Store current object key for content type detection
        self.current_object_key = obj_data['Key']
        
        # Show object info
        info = f"Key: {obj_data['Key']}\n"
        info += f"Size: {format_size(obj_data['Size'])}\n"
        info += f"Modified: {obj_data['LastModified']}\n"
        info += f"ETag: {obj_data['ETag']}"
        self.object_info.setText(info)
        
        self.s3_worker.download_object(self.current_bucket, obj_data['Key'])
    
    def display_object_preview(self, content: bytes, content_type: str):
        """Display object preview"""
        try:
            # Broaden CSV detection
            csv_types = [
                'text/csv',
                'application/csv',
                'application/vnd.ms-excel',
                'text/plain',
                'application/octet-stream',
            ]
            is_csv = False
            if self.current_object_key and self.current_object_key.lower().endswith('.csv'):
                is_csv = True
            elif any(content_type.startswith(t) for t in csv_types):
                if self.current_object_key and self.current_object_key.lower().endswith('.csv'):
                    is_csv = True
                elif content_type in ['text/csv', 'application/csv', 'application/vnd.ms-excel']:
                    is_csv = True
            if is_csv:
                self.display_csv_preview(content)
                self.preview_tabs.setCurrentIndex(1)  # CSV tab
                return

            # Text preview
            if content_type.startswith('text/') or content_type == 'application/json':
                text_content = content.decode('utf-8', errors='replace')
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
                    self.preview_tabs.setCurrentIndex(3)  # Image tab
                else:
                    self.image_label.setText("Failed to load image")
            else:
                self.image_label.setText("Not an image file")
            
        except UnicodeDecodeError:
            self.text_preview.setText(f"Binary content ({content_type})\nCannot display as text")
        
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
    
    def display_csv_preview(self, content: bytes):
        """Display CSV content in table format, fallback to text if parsing fails."""
        try:
            # Read CSV content
            csv_content = content.decode('utf-8', errors='replace')
            if not csv_content.strip():
                self.csv_preview.setRowCount(0)
                self.csv_preview.setColumnCount(0)
                self.csv_preview.setHorizontalHeaderLabels([])
                self.csv_preview.setVerticalHeaderLabels([])
                self.csv_preview.setToolTip('CSV file is empty.')
                return
            df = pd.read_csv(io.StringIO(csv_content))
            if df.empty or len(df.columns) == 0:
                raise ValueError('No table detected')
            # Set up table
            self.csv_preview.setRowCount(len(df))
            self.csv_preview.setColumnCount(len(df.columns))
            self.csv_preview.setHorizontalHeaderLabels(df.columns)
            # Fill table with data
            for i in range(len(df)):
                for j in range(len(df.columns)):
                    value = str(df.iloc[i, j])
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make read-only
                    self.csv_preview.setItem(i, j, item)
            # Resize columns to content
            self.csv_preview.resizeColumnsToContents()
            self.csv_preview.setToolTip('')
        except Exception as e:
            # Fallback: show as text
            self.csv_preview.setRowCount(0)
            self.csv_preview.setColumnCount(0)
            self.csv_preview.setHorizontalHeaderLabels([])
            self.csv_preview.setVerticalHeaderLabels([])
            self.csv_preview.setToolTip(f'Failed to parse CSV as table. Showing as text. Reason: {str(e)}')
            self.text_preview.setText(content.decode('utf-8', errors='replace'))
            self.preview_tabs.setCurrentIndex(0)  # Switch to Text tab
            self.status_bar.showMessage('CSV could not be parsed as a table. Showing as text.')
    
    def clear_preview(self):
        """Clear all preview content"""
        self.text_preview.clear()
        self.raw_preview.clear()
        self.image_label.clear()
        self.image_label.setText("No image selected")
        self.object_info.clear()
        self.csv_preview.setRowCount(0)
        self.csv_preview.setColumnCount(0)
        self.current_object_key = None
    
    def delete_selected_object(self):
        """Delete selected object with authentication"""
        current_item = self.object_tree.currentItem()
        if not current_item:
            return
        
        obj_data = current_item.data(0, Qt.UserRole)
        if not obj_data:
            return
        
        # Show authentication dialog
        auth_dialog = AuthenticationDialog(self, obj_data.get('Key', obj_data.get('path', 'Unknown')))
        if auth_dialog.exec() == QDialog.Accepted:
            password = auth_dialog.get_password()
            
            if password == self.admin_password:
                # Proceed with deletion
                self.progress_bar.setVisible(True)
                
                if isinstance(obj_data, dict) and obj_data.get("type") == "folder":
                    # Delete folder
                    self.status_bar.showMessage(f"Deleting folder {obj_data['path']}...")
                    self.s3_worker.delete_folder(self.current_bucket, obj_data['path'])
                else:
                    # Delete single file
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
        self.download_btn.setEnabled(False)
        self.clear_preview()
        
        QMessageBox.information(self, "Success", f"Object '{key}' was deleted successfully.")
    
    def show_error(self, error_message: str):
        """Show error message"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Error occurred")
        QMessageBox.critical(self, "Error", error_message)
    
    def download_selected_objects(self):
        """Download selected objects"""
        selected_items = self.object_tree.selectedItems()
        if not selected_items:
            return

        # Get download directory
        download_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly
        )
        
        if not download_dir:
            return

        # Collect objects to download
        objects_to_download = []
        for item in selected_items:
            obj_data = item.data(0, Qt.UserRole)
            if obj_data:
                if isinstance(obj_data, dict) and obj_data.get("type") == "folder":
                    # For folders, collect all files in the folder
                    folder_path = obj_data.get("path", "")
                    folder_objects = [obj for obj in self.current_objects 
                                   if obj['Key'].startswith(folder_path)]
                    objects_to_download.extend(folder_objects)
                else:
                    # For files, add directly
                    objects_to_download.append(obj_data)

        if not objects_to_download:
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Downloading files...")

        # Start download
        self.s3_worker.download_objects(self.current_bucket, objects_to_download, download_dir)

    def handle_download_completed(self, download_path: str):
        """Handle completed download"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"Download completed: {download_path}")
        
        QMessageBox.information(
            self,
            "Download Complete",
            f"Files have been downloaded to:\n{download_path}"
        )

    def update_download_progress(self, progress: int):
        """Update download progress bar"""
        self.progress_bar.setValue(progress)
    
    def closeEvent(self, event):
        """Clean up on application close"""
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept() 