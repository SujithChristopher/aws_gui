"""
Dialog classes for authentication and credentials input.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QFormLayout, QGroupBox, QComboBox
)
from PySide6.QtCore import Qt
import os
import json

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


CREDENTIALS_PATH = os.path.join(os.path.expanduser('~'), '.aws_credentials.json')

class CredentialsDialog(QDialog):
    """Dialog for AWS credentials input"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AWS Credentials")
        self.setModal(True)
        self.setFixedSize(450, 300)
        
        layout = QVBoxLayout()
        
        # Instructions
        info = QLabel("Enter your AWS credentials to connect to S3:")
        layout.addWidget(info)
        
        # Note about bucket access
        note = QLabel("Note: If you don't have ListAllMyBuckets permission, "
                     "you can manually enter the bucket name 'homerclouds'.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(note)
        
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
        
        # Load credentials if available
        self.load_credentials()
    
    def get_credentials(self) -> tuple:
        return (
            self.access_key_input.text(),
            self.secret_key_input.text(),
            self.region_combo.currentText()
        )

    def accept(self):
        # Save credentials on accept
        self.save_credentials()
        super().accept()

    def save_credentials(self):
        creds = {
            'access_key': self.access_key_input.text(),
            'secret_key': self.secret_key_input.text(),
            'region': self.region_combo.currentText()
        }
        try:
            with open(CREDENTIALS_PATH, 'w') as f:
                json.dump(creds, f)
        except Exception:
            pass  # Ignore errors

    def load_credentials(self):
        if os.path.exists(CREDENTIALS_PATH):
            try:
                with open(CREDENTIALS_PATH, 'r') as f:
                    creds = json.load(f)
                self.access_key_input.setText(creds.get('access_key', ''))
                self.secret_key_input.setText(creds.get('secret_key', ''))
                region = creds.get('region', '')
                idx = self.region_combo.findText(region)
                if idx >= 0:
                    self.region_combo.setCurrentIndex(idx)
            except Exception:
                pass  # Ignore errors 