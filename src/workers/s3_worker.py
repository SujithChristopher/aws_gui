"""
S3 Worker class for handling AWS S3 operations in a background thread.
"""

import logging
import os
import zipfile
import tempfile
from typing import List, Dict, Any
from PySide6.QtCore import QObject, Signal

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
    download_completed = Signal(str)  # Download path
    download_progress = Signal(int)  # Download progress percentage
    
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
            # Test connection with a simple call that doesn't require ListAllMyBuckets
            # We'll test when actually accessing a bucket
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
            # If listing buckets fails (no permission), return empty list
            # User can manually enter bucket name
            logger.warning(f"Cannot list buckets: {str(e)}")
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

    def delete_folder(self, bucket_name: str, prefix: str):
        """Delete all objects in a folder (prefix)"""
        if not self.s3_client:
            self.error_occurred.emit("S3 client not initialized")
            return
        
        try:
            # List all objects with the prefix
            objects = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            for page in page_iterator:
                if 'Contents' in page:
                    objects.extend([{'Key': obj['Key']} for obj in page['Contents']])
            
            if not objects:
                self.error_occurred.emit(f"No objects found in folder: {prefix}")
                return
            
            # Delete all objects in the folder
            self.s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': objects}
            )
            
            self.object_deleted.emit(prefix)
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to delete folder: {str(e)}")

    def is_empty_folder(self, bucket_name: str, prefix: str) -> bool:
        """Check if a folder (prefix) is empty"""
        if not self.s3_client:
            return False
        
        try:
            # List objects with the prefix
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=1  # We only need to know if there's at least one object
            )
            
            # If no Contents key or empty Contents, folder is empty
            return 'Contents' not in response or len(response['Contents']) == 0
            
        except Exception as e:
            logger.error(f"Failed to check if folder is empty: {str(e)}")
            return False

    def download_objects(self, bucket_name: str, objects: List[Dict[str, Any]], download_path: str):
        """Download multiple objects, optionally creating a zip file"""
        if not self.s3_client:
            self.error_occurred.emit("S3 client not initialized")
            return

        try:
            if len(objects) == 1:
                # Single file download
                obj = objects[0]
                key = obj['Key']
                local_path = os.path.join(download_path, os.path.basename(key))
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Download file
                self.s3_client.download_file(bucket_name, key, local_path)
                self.download_completed.emit(local_path)
                
            else:
                # Multiple files - create zip
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Download all files to temp directory
                    total_size = sum(obj['Size'] for obj in objects)
                    downloaded_size = 0
                    
                    for obj in objects:
                        key = obj['Key']
                        temp_path = os.path.join(temp_dir, key)
                        
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                        
                        # Download file
                        self.s3_client.download_file(bucket_name, key, temp_path)
                        
                        # Update progress
                        downloaded_size += obj['Size']
                        progress = int((downloaded_size / total_size) * 100)
                        self.download_progress.emit(progress)
                    
                    # Create zip file
                    zip_path = os.path.join(download_path, "s3_download.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(temp_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, temp_dir)
                                zipf.write(file_path, arcname)
                    
                    self.download_completed.emit(zip_path)
                    
        except Exception as e:
            self.error_occurred.emit(f"Failed to download objects: {str(e)}") 