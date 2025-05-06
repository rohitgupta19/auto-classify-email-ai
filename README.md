# Email Classifier AI

A simple email classification system that uses AWS Bedrock for AI-powered categorization and AWS Lambda for serverless processing. The system automatically classifies Gmail messages into categories and applies labels hourly.

## Features
- Automatic hourly email classification using AWS Bedrock
- Gmail integration with label management
- Serverless processing with AWS Lambda
- Smart categorization for emails into:
  - Action Required
  - Deadline Approaching
  - Meeting / Calendar Event
  - Follow-Up Needed
  - Updates / Notifications
  - Billing / Invoice
  - Reports / Summaries
  - Promotional Offers (auto-moved to spam)
  - Subscription Updates
  - Spam
  - Phishing / Unsafe
  - Unrecognized Sender
  - Personal
  - Job Applications / Careers
  - Internal Communications
  - Social / Networking

## Prerequisites
- Python 3.8 or higher
- AWS Account with Bedrock access
- Gmail API credentials
- Terraform (version >= 1.2.0)

## Development Setup

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd auto-classify-email-ai
   ```

2. Set up virtual environment:
   ```bash
   # Create virtual environment
   python -m venv .venv

   # Activate virtual environment
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   ```

3. Set up Gmail API:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials as JSON
   - Save as `credentials.json` in project root

4. Create `.env` file:
   ```ini
   # Gmail API Configuration
   GMAIL_CREDENTIALS='{"token":"your-token","refresh_token":"your-refresh-token","token_uri":"https://oauth2.googleapis.com/token","client_id":"your-client-id","client_secret":"your-client-secret","scopes":["https://www.googleapis.com/auth/gmail.modify"]}'

   # AWS Configuration
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```

5. Test locally:
   ```bash
   # Make sure virtual environment is activated
   python test_auth.py
   ```

## Deployment

1. Create `terraform.tfvars`:
   ```hcl
   aws_region = "your-aws-region"
   gmail_credentials = "your-gmail-credentials-json-string"
   ```

2. Deploy the infrastructure:
   ```bash
   # Package Lambda function
   ./package_lambda.sh

   # Deploy using Terraform
   cd terraform
   terraform init
   terraform apply
   ```

## How It Works

1. The Lambda function runs every hour to process unread emails
2. For each unread email:
   - Fetches email content via Gmail API
   - Uses AWS Bedrock (Claude v2) to analyze and classify the email
   - Applies appropriate Gmail label based on classification
   - Promotional emails are automatically moved to spam
   - Marks the email as read after processing

## Directory Structure
```
├── src/                    # Source code
│   ├── lambda/            # Lambda function
│   │   └── handler.py     # Main Lambda handler with classification logic
│   └── gmail/             # Gmail integration
├── terraform/             # Infrastructure code
├── test_auth.py          # Gmail authentication test
└── package_lambda.sh      # Deployment script
```

## Testing
Run the following tests to verify your setup:

```bash
# Activate virtual environment if not already activated
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Test Gmail authentication
python test_auth.py
```

## Troubleshooting

Common issues and solutions:

1. Virtual Environment Issues:
   - Make sure to activate the virtual environment before running any commands
   - Check Python version: `python --version` (should be 3.8+)
   - Reinstall dependencies if needed: `pip install -r requirements.txt`

2. Gmail Authorization:
   - Ensure GMAIL_CREDENTIALS in .env is valid JSON
   - Check if token.json is generated
   - Verify OAuth consent screen is configured

3. AWS Configuration:
   - Verify AWS credentials are set correctly
   - Check Bedrock service availability in your region
   - Ensure IAM roles have necessary permissions

4. Lambda Function:
   - Check CloudWatch logs for detailed error messages
   - Verify timeout settings (recommended: 3+ minutes)
   - Monitor memory usage and adjust if needed

## License
MIT License
