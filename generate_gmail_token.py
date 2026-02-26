"""
Script to generate Gmail OAuth token locally.
Run this once to authenticate and generate gmail_token.json
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

# Scopes needed for reading emails and creating drafts
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose'
]

def generate_token():
    """Generate OAuth token for Gmail API"""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_file = os.path.join(script_dir, 'credentials', 'gmail_credentials.json')
    token_file_path = os.path.join(script_dir, 'credentials', 'gmail_token.json')

    # Make sure gmail_credentials.json exists
    if not os.path.exists(creds_file):
        print("❌ Error: credentials/gmail_credentials.json not found!")
        print("Please download it from Google Cloud Console first")
        return

    # Create flow from credentials
    flow = InstalledAppFlow.from_client_secrets_file(
        creds_file,
        SCOPES
    )

    # Run local server for authentication
    creds = flow.run_local_server(port=8080)

    # Save token for future use
    with open(token_file_path, 'w') as token_file:
        token_file.write(creds.to_json())

    print("✅ Token generated successfully!")
    print("📁 Saved as gmail_token.json")
    print("\nNext steps:")
    print("1. Add to your .env file:")
    print("   GMAIL_CREDENTIALS_FILE=gmail_credentials.json")
    print("   GMAIL_TOKEN_FILE=gmail_token.json")

if __name__ == '__main__':
    generate_token()
