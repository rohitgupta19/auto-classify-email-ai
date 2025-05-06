import base64
import os
import boto3
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
from datetime import datetime, timedelta, timezone

# Gmail API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# AWS Bedrock model details
BEDROCK_MODEL_ID = "anthropic.claude-v2"
BEDROCK_REGION = "us-east-1"

# Authenticate Gmail
def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# Get the latest unread email
def get_latest_unread_email(service):
    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=1).execute()
    messages = results.get('messages', [])
    if not messages:
        print("No unread messages.")
        return None, None
    msg_id = messages[0]['id']
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = msg['payload'].get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
    body_data = msg['payload']['parts'][0]['body'].get('data') if 'parts' in msg['payload'] else msg['payload']['body'].get('data')
    body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore') if body_data else ''
    return msg_id, f"Subject: {subject}\n\n{body}"


def get_unread_emails_last_24_hour(service):
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    query = 'label:UNREAD newer_than:1h'

    results = service.users().messages().list(
        userId='me',
        q=query,
        labelIds=['INBOX', 'UNREAD'],
        maxResults=100  # adjust as needed
    ).execute()

    messages = results.get('messages', [])
    if not messages:
        print("No unread emails in the last 1 day.")
        return []

    email_data = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
        headers = msg['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        
        payload = msg['payload']
        if 'parts' in payload:
            parts = payload['parts']
            for part in parts:
                body_data = part['body'].get('data')
                if body_data:
                    break
        else:
            body_data = payload['body'].get('data')

        body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore') if body_data else ''
        
        email_data.append((message['id'], f"Subject: {subject}\n\n{body}"))

    return email_data



def classify_with_bedrock(text):
    print("Email preview:", text[:100].replace('\n', ' ') + "...")
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    
    categories = [
        "Action Required", "Deadline Approaching", "Meeting / Calendar Event",
        "Follow-Up Needed", "Updates / Notifications", "Billing / Invoice",
        "Reports / Summaries", "Promotional Offers", "Subscription Updates",
        "Spam", "Phishing / Unsafe", "Unrecognized Sender", "Personal",
        "Job Applications / Careers", "Internal Communications", "Social / Networking"
    ]

    category_list = ", ".join(categories)

    prompt = (
        f"\n\nHuman: You are an intelligent enterprise email classifier specializing in security and content analysis. "
        f"Your task is to classify the given email into ONLY ONE of the following categories:\n"
        f"{category_list}\n\n"
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

    body = {
        "prompt": prompt,
        "max_tokens_to_sample": 50,
        "temperature": 0.3,
        "top_k": 250,
        "top_p": 1,
        "stop_sequences": ["\n\nHuman:", "\n", "Assistant:"]
    }

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )

    result = response["body"].read().decode("utf-8")
    try:
        # First check for payment-related keywords
        payment_keywords = ['payment', 'transaction', 'bill', 'invoice', 'receipt', 'successful', 'paid', 'credit', 'debit']
        if any(keyword in text.lower() for keyword in payment_keywords):
            print("Found payment-related keywords, classifying as 'Billing / Invoice'")
            return "Billing / Invoice"
            
        classification = json.loads(result).get("completion", "").strip()
        print(f"Raw classification result: {classification}")
        
        for category in categories:
            if category in classification:
                return category
                
        return "Other"
    except json.JSONDecodeError:
        return "Other"

# Add label to the email
def add_label(service, msg_id, label_name):
    # Get existing labels
    labels = service.users().labels().list(userId='me').execute()
    label_id = next((l['id'] for l in labels['labels'] if l['name'].lower() == label_name.lower()), None)

    # Create label if it doesn't exist
    if not label_id:
        label = {'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
        label_id = service.users().labels().create(userId='me', body=label).execute()['id']

    # Modify message to add label
    service.users().messages().modify(userId='me', id=msg_id, body={
        'addLabelIds': [label_id],
        'removeLabelIds': ['UNREAD']
    }).execute()
    print(f"Labeled message {msg_id} as '{label_name}'.")

# Main
def main():
    gmail_service = authenticate_gmail()
    #msg_id, content = get_latest_unread_email(gmail_service)
    emails= get_unread_emails_last_24_hour(gmail_service)
    for msg_id, content in emails:
        label = classify_with_bedrock(content)
        print(f"Classification result: {label}")
        if label == "Promotional Offers":
            print("Moving to spam email as it is promotional.")
            gmail_service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={
                        'addLabelIds': ['SPAM'],
                        'removeLabelIds': ['INBOX']
                    }
                ).execute()
        else:
            add_label(gmail_service, msg_id, label)

if __name__ == '__main__':
    main()
