# AWS S3 Bucket Browser

A comprehensive GUI application for browsing and managing AWS S3 buckets. Features include:
- Tree and flat view of bucket contents
- File preview (text, CSV, images, and raw/hex)
- **CSV preview**: Table view for standard CSVs, with fallback to raw text for non-standard/metadata CSVs
- Secure file deletion with authentication
- Download single or multiple files/folders (multiple items are zipped)
- Remembers AWS credentials securely (locally, not synced to git)
- Support for custom bucket access

## Project Structure

```
aws_gui/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .gitignore              # Ignores credentials, cache, and temp files
├── src/                    # Source code directory
│   ├── __init__.py
│   ├── workers/           # Background worker classes
│   │   ├── __init__.py
│   │   └── s3_worker.py   # S3 operations worker
│   ├── ui/                # UI components
│   │   ├── __init__.py
│   │   ├── dialogs.py     # Dialog windows (credentials, delete auth)
│   │   └── main_window.py # Main application window
│   └── utils/             # Utility functions
│       ├── __init__.py
│       └── formatters.py  # Data formatting utilities
```

## Setup

1. Install Python 3.8 or later
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```
2. Enter your AWS credentials when prompted (these will be remembered locally for next time):
   - Access Key ID
   - Secret Access Key
   - Region
3. Select or enter a bucket name to browse

## Features

- **Tree/Flat View**: Toggle between hierarchical and flat views of bucket contents
- **File Preview**:
  - **Text**: View plain text and JSON files
  - **CSV**: Table view for standard CSVs; if parsing fails, raw text is shown
  - **Image**: Preview image files
  - **Raw**: Hex dump of file content
- **Secure Deletion**: Password-protected file deletion
- **Download**:
  - Download single files directly
  - Download multiple files or folders as a zip archive
- **Sorting**: Sort by name, size, or modification date
- **Manual Bucket Entry**: Support for buckets without ListAllMyBuckets permission
- **Remembers Credentials**: AWS credentials are stored locally in your home directory as `.aws_credentials.json` (never synced to git)

## Security Notes

- AWS credentials are stored in memory and in a local file (`~/.aws_credentials.json`), which is ignored by git.
- File deletion requires authentication.
- **.gitignore** ensures that credentials and temp files are never committed.

## Dependencies

- PySide6: Qt-based GUI framework
- boto3: AWS SDK for Python
- pandas: For robust CSV parsing

## FAQ

**Q: What if a CSV file doesn't show as a table?**
- If the CSV has extra header lines or metadata, the app will show the raw text instead of a table, so you can always view the file.

**Q: Will my credentials be uploaded to GitHub?**
- No. The `.aws_credentials.json` file is ignored by git and only stored locally.

**Q: How do I download a whole folder?**
- Select the folder and click "Download Selected". All files in the folder will be downloaded and zipped.

---

Feel free to open issues or request features!
