import os
from dotenv import load_dotenv
from src.gmail.gmail_service import GmailService

def test_gmail_auth_and_messages():
    try:
        # Initialize the Gmail service
        gmail_service = GmailService()
        
        # Try to list labels - this will fail if authentication is not working
        labels = gmail_service.service.users().labels().list(userId='me').execute()
        
        print("✅ Authentication successful!")
        print("\nAvailable labels:")
        for label in labels['labels']:
            print(f"- {label['name']}")
            
        # Fetch recent messages
        print("\nFetching recent messages...")
        messages = gmail_service.service.users().messages().list(userId='me', maxResults=3).execute()
        
        if messages and 'messages' in messages:
            print("\nRecent message IDs:")
            for msg in messages['messages']:
                msg_id = msg['id']
                # Get message details
                msg_detail = gmail_service.service.users().messages().get(userId='me', id=msg_id, format='metadata').execute()
                subject = next((header['value'] for header in msg_detail['payload']['headers'] if header['name'].lower() == 'subject'), 'No subject')
                print(f"- Message ID: {msg_id}")
                print(f"  Subject: {subject}\n")
        else:
            print("No messages found in the inbox.")
            
    except Exception as e:
        print("❌ Test failed!")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    
    # Check if GMAIL_CREDENTIALS environment variable is set
    if not os.getenv('GMAIL_CREDENTIALS'):
        print("❌ GMAIL_CREDENTIALS environment variable is not set!")
        print("Please set it in your .env file")
        exit(1)
        
    test_gmail_auth_and_messages()