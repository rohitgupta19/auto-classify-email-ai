import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def generate_credentials():
    credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH', './credentials.json')
    
    # Load client configuration and run local server flow
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Create the credentials dictionary
    credentials_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    # Save the credentials
    with open('authorized_credentials.json', 'w') as f:
        json.dump(credentials_data, f)
    
    print("Pre-authorized credentials have been saved to 'authorized_credentials.json'")
    print("Use these credentials in your GMAIL_CREDENTIALS environment variable for Lambda")

if __name__ == '__main__':
    generate_credentials()