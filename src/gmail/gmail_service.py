import os
import json
import base64
import re
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailService:
    def __init__(self):
        logger.info("Initializing Gmail Service...")
        self.service = self._get_gmail_service()
        self.user_id = 'me'

    def _get_gmail_service(self):
        try:
            credentials_json = os.getenv('GMAIL_CREDENTIALS')
            if not credentials_json:
                logger.error("GMAIL_CREDENTIALS environment variable is not set")
                raise ValueError("GMAIL_CREDENTIALS environment variable is not set")

            logger.info("Found GMAIL_CREDENTIALS environment variable")
            
            try:
                creds_data = json.loads(credentials_json)
                logger.info("Successfully parsed credentials JSON")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GMAIL_CREDENTIALS JSON: {str(e)}")
                raise

            try:
                creds = Credentials(
                    token=creds_data.get('token'),
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    client_id=creds_data.get('client_id'),
                    client_secret=creds_data.get('client_secret'),
                    scopes=SCOPES
                )
                logger.info("Created credentials object with:")
                logger.info(f"- Client ID: {creds_data.get('client_id')}")
                logger.info(f"- Token present: {bool(creds_data.get('token'))}")
                logger.info(f"- Refresh token present: {bool(creds_data.get('refresh_token'))}")
            except Exception as e:
                logger.error(f"Failed to create credentials object: {str(e)}")
                raise

            if not creds.valid:
                logger.info("Credentials are not valid, checking if they can be refreshed...")
                if creds.expired and creds.refresh_token:
                    logger.info("Attempting to refresh expired credentials")
                    creds.refresh(Request())
                    logger.info("Successfully refreshed credentials")
                else:
                    logger.error("Credentials are invalid and cannot be refreshed")
                    raise ValueError("Invalid credentials - please re-authenticate locally first")

            logger.info("Building Gmail service with valid credentials")
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {str(e)}")
            raise

    def _sanitize_message_id(self, message_id):
        """Sanitize the message ID to ensure it's in the correct format for the Gmail API"""
        # Remove any whitespace and special characters
        message_id = message_id.strip()
        # Remove any padding that might have been added
        message_id = message_id.rstrip('=')
        # Ensure the ID only contains valid base64url characters
        message_id = re.sub(r'[^a-zA-Z0-9\-_]', '', message_id)
        return message_id

    def get_email(self, message_id):
        try:
            # Sanitize the message ID before using it
            sanitized_id = self._sanitize_message_id(message_id)
            message = self.service.users().messages().get(
                userId=self.user_id, 
                id=sanitized_id, 
                format='full'
            ).execute()

            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            
            # Get email body
            body = ''
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode()
                        break
            elif 'body' in message['payload']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode()

            return {
                'subject': subject,
                'from': from_email,
                'body': body
            }
        except Exception as e:
            print(f"Error fetching email: {str(e)}")
            return None

    def apply_label(self, message_id, label_name):
        try:
            # Sanitize the message ID before using it
            sanitized_id = self._sanitize_message_id(message_id)
            
            # Get or create label
            labels = self.service.users().labels().list(userId=self.user_id).execute()
            label_id = next((label['id'] for label in labels['labels'] 
                           if label['name'].lower() == label_name.lower()), None)
            
            if not label_id:
                label = self.service.users().labels().create(
                    userId=self.user_id,
                    body={
                        'name': label_name,
                        'messageListVisibility': 'show',
                        'labelListVisibility': 'labelShow'
                    }
                ).execute()
                label_id = label['id']

            # Apply label
            self.service.users().messages().modify(
                userId=self.user_id,
                id=sanitized_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            return True
            
        except Exception as e:
            print(f"Error applying label: {str(e)}")
            return False