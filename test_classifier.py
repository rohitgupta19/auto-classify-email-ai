import requests
import json
import sys

def test_email_classification(message_id):
    """
    Test the email classification API with a Gmail message ID
    """
    api_endpoint = "https://gxt9hbgydc.execute-api.us-east-1.amazonaws.com/prod/classify"
    
    # Prepare the request
    payload = {
        "messageId": message_id
    }
    
    # Make the request
    try:
        response = requests.post(api_endpoint, json=payload)
        
        # Pretty print the response
        print("\nAPI Response Status:", response.status_code)
        print("\nResponse Body:")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error making request: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_classifier.py <gmail_message_id>")
        print("Example: python test_classifier.py 18c1234567890abc")
        sys.exit(1)
    
    message_id = sys.argv[1]
    test_email_classification(message_id)