import base64
import os
import boto3
import json
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
BEDROCK_MODEL_ID = "anthropic.claude-v2"
BEDROCK_REGION = "us-east-1"

def get_gmail_service():
    """Initialize Gmail service using credentials from environment variables"""
    try:
        logger.info("Starting Gmail service initialization...")
        
        # Log credential presence
        creds_json = os.environ.get('GMAIL_CREDENTIALS')
        if not creds_json:
            logger.error("GMAIL_CREDENTIALS environment variable not found")
            raise ValueError("GMAIL_CREDENTIALS environment variable is required")
        logger.info("Found GMAIL_CREDENTIALS environment variable")
        
        # Parse credentials JSON
        try:
            creds_data = json.loads(creds_json)
            logger.info("Successfully parsed credentials JSON")
            
            # Log presence of required fields (without exposing sensitive data)
            required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
            missing_fields = [field for field in required_fields if not creds_data.get(field)]
            
            if missing_fields:
                logger.error(f"Missing required fields in credentials: {', '.join(missing_fields)}")
                raise ValueError(f"Missing required credentials fields: {', '.join(missing_fields)}")
            
            logger.info("All required credential fields are present")
            logger.debug(f"Client ID: {creds_data['client_id'][:8]}...")  # Log only first 8 chars
            logger.debug(f"Token present: {bool(creds_data['token'])}")
            logger.debug(f"Refresh token present: {bool(creds_data['refresh_token'])}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GMAIL_CREDENTIALS JSON: {str(e)}")
            raise

        # Create credentials object
        try:
            creds = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=SCOPES
            )
            logger.info("Successfully created credentials object")
        except Exception as e:
            logger.error(f"Failed to create credentials object: {str(e)}")
            raise

        # Verify credentials validity
        try:
            if not creds.valid:
                logger.info("Credentials are not valid, checking refresh token...")
                if creds.expired and creds.refresh_token:
                    logger.info("Attempting to refresh expired credentials")
                    creds.refresh(Request())
                    logger.info("Successfully refreshed credentials")
                else:
                    logger.error("Credentials are invalid and cannot be refreshed")
                    raise ValueError("Invalid credentials - please re-authenticate")
        except Exception as e:
            logger.error(f"Error during credentials validation/refresh: {str(e)}")
            raise

        # Build and verify Gmail service
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            # Test the service with a simple API call
            service.users().getProfile(userId='me').execute()
            logger.info("Successfully verified Gmail service connection")
            
            return service
            
        except Exception as e:
            logger.error(f"Failed to build or verify Gmail service: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"Gmail service initialization failed: {str(e)}")
        raise

def get_unread_emails_last_hour(service):
    """Get unread emails from the last hour"""
    query = 'label:UNREAD newer_than:1h'
    
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            labelIds=['INBOX', 'UNREAD'],
            maxResults=100
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            logger.info("No unread emails in the last hour.")
            return []

        email_data = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            headers = msg['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
            
            payload = msg['payload']
            body_data = None
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body_data = part['body'].get('data')
                        if body_data:
                            break
            else:
                body_data = payload['body'].get('data')

            body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore') if body_data else ''
            email_data.append((message['id'], f"Subject: {subject}\n\n{body}"))
            logger.info(f"Fetched {len(email_data)} unread emails from the last hour.")
        return email_data
    except Exception as e:
        logger.error(f"Error fetching emails: {str(e)}")
        raise

def classify_with_bedrock(text: str, region: str = BEDROCK_REGION, model_id: str = BEDROCK_MODEL_ID) -> str:
    """
    Classify email content using AWS Bedrock with strict rules
    """
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        
        categories = [
            "Action Required", "Deadline Approaching", "Meeting / Calendar Event",
            "Follow-Up Needed", "Updates / Notifications", "Billing / Invoice",
            "Reports / Summaries", "Promotional Offers", "Subscription Updates",
            "Spam", "Phishing / Unsafe", "Unrecognized Sender", "Personal",
            "Job Applications / Careers", "Internal Communications", "Social / Networking"
        ]

        prompt = (
            f"\n\nHuman: You are an intelligent enterprise email classifier specializing in security and content analysis. "
            f"Your task is to classify the given email into ONLY ONE of the following categories:\n"
            f"{', '.join(categories)}\n\n"
            f"STRICT CLASSIFICATION RULES:\n"
            f"1. DO NOT provide any explanation, just output the exact category name\n"
            f"2. Messages about account suspension, security alerts, or urgent actions = 'Phishing / Unsafe'\n"
            f"3. Words like 'congratulations', 'promotion', 'achievement' for career/job = 'Job Applications / Careers'\n"
            f"4. Marketing, sales, discounts, limited time offers = 'Promotional Offers'\n"
            f"5. If unsure about sender authenticity for urgent messages = 'Phishing / Unsafe'\n"
            f"6. Payment confirmations, bill payments, transaction alerts = 'Billing / Invoice'\n\n"
            f"Examples:\n"
            f"- 'Your account needs immediate attention' → 'Phishing / Unsafe'\n"
            f"- 'Congratulations on your job promotion!' → 'Job Applications / Careers'\n"
            f"- '50% off sale ends today!' → 'Promotional Offers'\n"
            f"- 'Team meeting at 3pm' → 'Meeting / Calendar Event'\n"
            f"- 'Transaction alert: Payment successful' → 'Billing / Invoice'\n"
            f"- 'Your bill payment was received' → 'Billing / Invoice'\n\n"
            f"Payment-Related Keywords: payment, transaction, bill, invoice, receipt, successful, paid, credit, debit\n\n"
            f"DO NOT EXPLAIN YOUR CHOICE. RESPOND WITH ONLY THE CATEGORY NAME.\n\n"
            f"Email content:\n{text}\n\nAssistant:"
        )

        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 50,
                "temperature": 0.3,  # Reduced temperature for more consistent outputs
                "top_k": 250,
                "top_p": 1,
                "stop_sequences": ["\n\nHuman:", "\n", "Assistant:"]  # Added more stop sequences
            })
        )

        result = json.loads(response["body"].read())
        classification = result.get("completion", "").strip()
        
        # Clean up any explanatory text and get just the category
        # First, check for payment-related keywords to ensure proper classification
        payment_keywords = ['payment', 'transaction', 'bill', 'invoice', 'receipt', 'successful', 'paid', 'credit', 'debit']
        if any(keyword in text.lower() for keyword in payment_keywords):
            logger.info(f"Found payment-related keywords in text, defaulting to 'Billing / Invoice'")
            return "Billing / Invoice"
        
        for category in categories:
            if category in classification:
                logger.info(f"Found category '{category}' in classification result: {classification}")
                return category
        
        logger.warning(f"No valid category found in classification result: {classification}")
        return "Other"
    
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        return "Other"

def add_label(service, msg_id, label_name):
    """Add or create label and apply to email"""
    try:
        labels = service.users().labels().list(userId='me').execute()
        label_id = next((l['id'] for l in labels['labels'] if l['name'].lower() == label_name.lower()), None)

        if not label_id:
            label = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            label_id = service.users().labels().create(userId='me', body=label).execute()['id']

        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={
                'addLabelIds': [label_id],
                'removeLabelIds': ['UNREAD']
            }
        ).execute()
        logger.info(f"Labeled message {msg_id} as '{label_name}'")
    
    except Exception as e:
        logger.error(f"Error adding label: {str(e)}")
        raise

def lambda_handler(event, context):
    """AWS Lambda handler function"""
    try:
        # Initialize Gmail service
        gmail_service = get_gmail_service()
        
        # Get unread emails from last hour
        emails = get_unread_emails_last_hour(gmail_service)
        
        processed_count = 0
        for msg_id, content in emails:
            # Extract subject from content (format is "Subject: {subject}\n\n{body}")
            subject = content.split('\n\n')[0].replace('Subject: ', '')
            # Classify email
            label = classify_with_bedrock(content)
            logger.info(f"Classification result for email '{subject}' (ID: {msg_id}): {label}")
            add_label(gmail_service, msg_id, label)
            processed_count += 1
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {processed_count} emails',
                'processedEmails': processed_count
            })
        }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }