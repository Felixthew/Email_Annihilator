# Gmail API access: auth, fetching, parsing, sending, watch registration
# Parts based off of Google's quickstart code: https://developers.google.com/gmail/api/quickstart/python
import base64
import os.path
from dataclasses import dataclass

from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from email_annihilator.config import Settings

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          'https://www.googleapis.com/auth/gmail.send']

SYSTEM_LABELS = [
    "CHAT", "SENT", "INBOX", "IMPORTANT", "TRASH", "DRAFT", "SPAM",
    "CATEGORY_FORUMS", "CATEGORY_UPDATES", "CATEGORY_PERSONAL",
    "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "STARRED", "UNREAD"
]


@dataclass
class Email:
    subject: str
    sender: str
    body: str
    time_sent: datetime


class GmailClient:
    def __init__(self, service, trigger_label: str, topic: str, recipient: str):
        """
        :param service: an authenticated gmail API service, see build_service
        :param trigger_label: id of the label that on-demand trigger emails land under
        :param topic: the pub/sub topic gmail pushes notifications to
        :param recipient: address the summary is sent to
        """
        self.service = service
        self.trigger_label = trigger_label
        self.topic = topic
        self.recipient = recipient

    def fetch_recent(self, hours: int) -> list[Email]:
        """
        Fetches inbox emails from the last n hours
        :param hours: how far back to look
        :return: the emails, empty if there are none or the gmail API call failed
        """
        try:
            labels = self.service.users().labels().list(userId="me").execute()
            inbox_label_name = "INBOX"
            label_id = next((label["id"] for label in labels["labels"] if label["name"].upper() == inbox_label_name), None)
            results = self._fetch_mail(label_id, hours)

            emails = []
            for msg in results.get("messages", []):
                msg_data = self.service.users().messages().get(userId="me", id=msg["id"]).execute()
                emails.append(Email(
                    body=get_body(msg_data),
                    subject=get_subject(msg_data),
                    sender=get_sender(msg_data),
                    time_sent=get_time_sent(msg_data)
                ))
            return emails
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def _fetch_mail(self, label_id, hours):
        # Get UTC time __ hours ago
        time_n_hours_ago = datetime.now() - timedelta(hours=hours)
        timestamp = int(time_n_hours_ago.timestamp())

        query = f"after:{timestamp}"

        return self.service.users().messages().list(userId="me", q=query, labelIds=[label_id], maxResults=100).execute()

    def send_html(self, html: str):
        """
        Sends an html email to the recipient
        :param html: The email body
        :return: The gmail API response on send, None if sending failed
        """
        try:
            message = EmailMessage()

            message.set_content("The summary is in html")

            message.add_alternative(html, subtype="html")

            message["To"] = self.recipient
            message["From"] = "Email Condenser"
            message["Subject"] = "Email Summary"

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"raw": encoded_message}
            # pylint: disable=E1101
            send_message = (
                self.service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            print(f'Message Id: {send_message["id"]}')
        except HttpError as error:
            print(f"An error occurred: {error}")
            send_message = None
        return send_message

    def latest_trigger_body(self, since_history_id: str) -> str | None:
        """
        Gets the body of the newest email added under the trigger label since a history id
        :param since_history_id: the history cursor to start from
        :return: the plain text body, None if there is no trigger email (or it has no plain text part)
        """
        history = self.service.users().history().list(
            userId="me",
            startHistoryId=since_history_id,
            historyTypes=["messageAdded"],
            labelId=self.trigger_label
        ).execute()

        message_ids = []
        for record in history.get("history", []):
            for added in record.get("messagesAdded", []):
                message_ids.append(added["message"]["id"])

        if not message_ids:
            return None

        msg_data = self.service.users().messages().get(
            userId="me",
            id=message_ids[-1],
        ).execute()
        return get_body(msg_data)

    def register_watch(self):
        """
        Registers a gmail watch on the trigger label. Note: this must be achieved by excluding all other labels first then
        registering a watch for the label due to feature being bugged.
        """
        # Stop all existing watches first
        self.service.users().stop(userId="me").execute()
        print("Stopped existing watches")

        # First watch: exclude all system labels
        exclude_response = self.service.users().watch(
            userId="me",
            body={
                "topicName": self.topic,
                "labelIds": SYSTEM_LABELS,
                "labelFilterBehavior": "EXCLUDE"
            }
        ).execute()
        print("Exclude watch registered:", exclude_response)

        # Second watch: include only the Push Trigger label
        include_response = self.service.users().watch(
            userId="me",
            body={
                "topicName": self.topic,
                "labelIds": [self.trigger_label],
                "labelFilterBehavior": "INCLUDE"
            }
        ).execute()
        print("Include watch registered:", include_response)


def build_service(token_path: str, credentials_path: str, local_auth: bool = False):
    """
    Builds an authenticated gmail API service
    :param token_path: path to the OAuth token
    :param credentials_path: path to the OAuth client, only used for the local browser flow
    :param local_auth: whether invalid credentials may be fixed through a browser flow
    """
    creds = configure_credentials(token_path, credentials_path, local_auth)
    return build("gmail", "v1", credentials=creds)


def configure_credentials(token_path: str, credentials_path: str, local_auth: bool):
    if not os.path.exists(token_path):
        raise RuntimeError("token.json missing")

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        if local_auth:
            creds = force_authenticate(credentials_path)
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        else:
            raise RuntimeError("Credentials invalid and cannot refresh")

    return creds


# forces authentication through web redirect
def force_authenticate(credentials_path: str):
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds


def get_body(msg_data):
    parts = msg_data["payload"].get("parts", [])
    for part in parts:
        if part["mimeType"] == "text/plain":
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")


#ChatGPT generated
def get_sender(email_data):
    """Extracts the sender's email from the email headers."""
    headers = email_data["payload"]["headers"]
    for header in headers:
        if header["name"] == "From":
            return header["value"]  # Format: "Sender Name <email@example.com>"
    return "Unknown Sender"


#ChatGPT generated
def get_subject(email_data):
    """Extracts the subject from the email headers."""
    headers = email_data["payload"]["headers"]
    for header in headers:
        if header["name"] == "Subject":
            return header["value"]
    return "No Subject"


def get_time_sent(email_data):
    """
    Extracts the time the email was sent as a datetime object (UTC).
    If the 'Date' header is missing or invalid, returns None.
    """
    headers = email_data["payload"]["headers"]
    for header in headers:
        if header["name"].lower() == "date":
            try:
                return parsedate_to_datetime(header["value"]).astimezone()
            except Exception:
                return None
    return None


if __name__ == "__main__":
    settings = Settings()
    service = build_service(settings.token_path, settings.credentials_path, settings.local_auth)
    GmailClient(service, settings.trigger_label, settings.topic, settings.recipient).register_watch()
