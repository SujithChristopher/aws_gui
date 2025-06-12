AWS S3 Bucket Browser

A simple web-based tool to browse, view, and delete files from your AWS S3 buckets.
✨ Features

    📂 List all objects in a specified S3 bucket

    👁️ View/download files

    🗑️ Delete files from the bucket

🚀 Getting Started
Prerequisites

    AWS account with access to S3

    AWS credentials (via environment variables or IAM role)

    Python 3.7+

    boto3 installed

Installation

    Clone the repository:

git clone https://github.com/your-username/s3-bucket-browser.git
cd s3-bucket-browser

    Install dependencies:

pip install -r requirements.txt

    Set up AWS credentials via AWS CLI or environment variables:

export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_DEFAULT_REGION=your-region

    Run the application:

python app.py

⚙️ Configuration

You can configure the bucket name and region either in the code or using environment variables (if supported in your implementation).
🛡️ Security Note

Make sure to:

    Limit access via IAM policies

    Use roles if deploying on AWS services like EC2 or Lambda

    Never expose your AWS credentials in code or client-side scripts

🧹 To-Do

    Add file upload support

    Pagination for large buckets

    Search/filter functionality

📄 License

MIT License. See LICENSE for more information.
