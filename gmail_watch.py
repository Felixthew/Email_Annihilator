# gmail_watch.py
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          'https://www.googleapis.com/auth/gmail.send']
TOKEN_PATH = "secrets/token/token.json"
TARGET_LABEL = "Label_5007763253467252103"
TOPIC = "projects/email-endeavor/topics/gmail-push"

SYSTEM_LABELS = [
    "CHAT", "SENT", "INBOX", "IMPORTANT", "TRASH", "DRAFT", "SPAM",
    "CATEGORY_FORUMS", "CATEGORY_UPDATES", "CATEGORY_PERSONAL",
    "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "STARRED", "UNREAD"
]

try:
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
except Exception:
    flow = InstalledAppFlow.from_client_secrets_file("secrets/credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w") as token:
        token.write(creds.to_json())

service = build("gmail", "v1", credentials=creds)

# Stop all existing watches first
service.users().stop(userId="me").execute()
print("Stopped existing watches")

# First watch: exclude all system labels
exclude_response = service.users().watch(
    userId="me",
    body={
        "topicName": TOPIC,
        "labelIds": SYSTEM_LABELS,
        "labelFilterBehavior": "EXCLUDE"
    }
).execute()
print("Exclude watch registered:", exclude_response)

# Second watch: include only the Push Trigger label
include_response = service.users().watch(
    userId="me",
    body={
        "topicName": TOPIC,
        "labelIds": [TARGET_LABEL],
        "labelFilterBehavior": "INCLUDE"
    }
).execute()
print("Include watch registered:", include_response)