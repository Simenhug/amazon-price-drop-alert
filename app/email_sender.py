import base64
import json
import os
from email.mime.text import MIMEText

import boto3
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Define Gmail API Scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
S3_BUCKET_NAME = "amazon-product-price-history"
GOOGLE_TOKEN_S3_OBJECT_KEY = "secrets/token.json"

s3 = boto3.client("s3")


def get_token_from_s3():
    """Retrieve token.json from S3."""
    try:
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=GOOGLE_TOKEN_S3_OBJECT_KEY)
        token_data = response["Body"].read().decode("utf-8")
        return json.loads(token_data)
    except Exception as e:
        print(f"Error fetching token from S3: {e}")
        return None


def save_token_to_s3(creds):
    """Save updated token.json to S3."""
    try:
        token_data = json.dumps(json.loads(creds.to_json()))
        s3.put_object(
            Bucket=S3_BUCKET_NAME, Key=GOOGLE_TOKEN_S3_OBJECT_KEY, Body=token_data
        )
        print("Updated token.json saved to S3.")
    except Exception as e:
        print(f"Error saving token to S3: {e}")


def authenticate_gmail():
    """Authenticate using a refresh token stored in S3."""
    creds_data = get_token_from_s3()

    if not creds_data:
        print("No valid credentials found. Exiting authentication.")
        return None

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token_to_s3(creds)  # Update S3 with the refreshed token

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
        subject="Email Test!",
        message_text="The is an email test. Hope you have a great day :)",
    )
