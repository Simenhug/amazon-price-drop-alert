import base64
import json
import os
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.price_data_processor import PriceDataProcessor, PriceDropDTO

# Define Gmail API Scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
S3_BUCKET_NAME = "amazon-product-price-history"
GOOGLE_TOKEN_S3_OBJECT_KEY = "secrets/token.json"
GOOGLE_CREDENTIALS_S3_OBJECT_KEY = "secrets/credentials.json"

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


def generate_new_token():
    """
    run this locally if Lambda failed to refresh google credentials token
    this will request a new google credentials token. This will require manual authentication
    via a web browser and only works locally
    """
    print("Generating new token.json...")
    s3.download_file(
        S3_BUCKET_NAME, GOOGLE_CREDENTIALS_S3_OBJECT_KEY, "/tmp/credentials.json"
    )
    flow = InstalledAppFlow.from_client_secrets_file("/tmp/credentials.json", SCOPES)
    creds = flow.run_local_server(prompt="consent")  # Forces new refresh token
    print("new credentials:", creds.to_json())
    save_token_to_s3(creds)  # Update S3 with the refreshed token


def authenticate_gmail():
    """Authenticate using a refresh token stored in S3."""
    google_token_json = get_token_from_s3()

    if not google_token_json:
        raise Exception("Missing token.json. Please re-authenticate.")

    google_token = Credentials.from_authorized_user_info(google_token_json, SCOPES)

    # Refresh token if expired
    if google_token and google_token.expired and google_token.refresh_token:
        print("Refreshing expired credentials...")
        try:
            google_token.refresh(Request())
            save_token_to_s3(google_token)
        except RefreshError as e:
            raise Exception(
                "Refresh token is invalid or revoked. Manual re-authentication required."
            ) from e

    return build("gmail", "v1", credentials=google_token)


def create_email_with_price_drops(
    sender, recipient, subject, price_drops: list[PriceDropDTO]
) -> dict[str, str]:
    """
    Create an email message with HTML content and embedded images for price drops.
    :param sender: Sender's email address
    :param recipient: Recipient's email address
    :param subject: Email subject
    :param price_drops: List of PriceDropDTOs
    :return: Encoded email message
    """
    # Generate HTML content and collect image paths
    html_content = "<html><body><h1>Hello!</h1><p>Here are price drops that you might be interested in:</p><ul>"
    image_paths = []

    for drop in price_drops:
        html_content += (
            f"<li>"
            f"<a href='{drop.url}'>{drop.product_name}</a><br>"
            f"Previous Price: {drop.previous_price}<br>"
            f"Current Price: {drop.current_price}<br>"
        )

        if drop.price_chart_path:
            image_name = os.path.basename(drop.price_chart_path)
            html_content += f"<img src='cid:{image_name}' alt='Price Chart'><br>"
            image_paths.append(drop.price_chart_path)

        html_content += "</li>"

    html_content += "</ul><p>Best regards,<br>Your Price Alert Team</p></body></html>"

    # Create a multipart message
    message = MIMEMultipart("related")
    message["to"] = recipient
    message["from"] = sender
    message["subject"] = subject

    # Create the HTML part
    html_part = MIMEMultipart("alternative")
    html_part.attach(MIMEText(html_content, "html"))
    message.attach(html_part)

    # Attach images if provided
    if image_paths:
        for image_path in image_paths:
            with open(image_path, "rb") as img_file:
                img = MIMEImage(img_file.read())
                img.add_header("Content-ID", f"<{os.path.basename(image_path)}>")
                img.add_header(
                    "Content-Disposition",
                    "inline",
                    filename=os.path.basename(image_path),
                )
                message.attach(img)

    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return {"raw": encoded_message}


def send_email(sender, recipient, subject, price_drops: list[PriceDropDTO]):
    """Send an email using Gmail API."""
    service = authenticate_gmail()
    email = create_email_with_price_drops(sender, recipient, subject, price_drops)
    sent_message = service.users().messages().send(userId="me", body=email).execute()
    print(f"Email sent successfully! Message ID: {sent_message['id']}")


class EmailSenderTestingTool:
    def test_send_email(self):
        """Test the send_email function."""
        email = os.getenv("EMAIL")
        price_data_processor = PriceDataProcessor()
        price_drops = price_data_processor.check_price_drops()
        price_drops = price_data_processor.plot_price_graphs(price_drops)
        send_email(
            sender=email,
            recipient=email,
            subject="Price Drop Alert!",
            price_drops=price_drops,
        )

    def test_credentials(self):
        """Test the credentials."""
        authenticate_gmail()


# for testing
if __name__ == "__main__":
    load_dotenv()
    test = EmailSenderTestingTool()
    test.test_send_email()
    # generate_new_token()  # run this if token refresh fails on Lambda
