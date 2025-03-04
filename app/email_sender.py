import base64
import os
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define Gmail API Scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def authenticate_gmail():
    """Authenticate and get Gmail API service."""
    creds = None
    token_path = "token.json"

    # Load existing credentials if available
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Authenticate if no valid credentials exist
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_email(sender, recipient, subject, message_text):
    """Create an email message."""
    message = MIMEText(message_text)
    message["to"] = recipient
    message["from"] = sender
    message["subject"] = subject
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return {"raw": encoded_message}


def send_email(sender, recipient, subject, message_text):
    """Send an email using Gmail API."""
    service = authenticate_gmail()
    email = create_email(sender, recipient, subject, message_text)
    sent_message = service.users().messages().send(userId="me", body=email).execute()
    print(f"Email sent successfully! Message ID: {sent_message['id']}")


# for testing
if __name__ == "__main__":
    load_dotenv()
    email = os.getenv("EMAIL")
    send_email(
        sender=email,
        recipient=email,
        subject="Price Drop Alert Test!",
        message_text="The price of your tracked item has dropped! Check it out now.",
    )
