# This file is based off of Google's quickstart code modified by both me and ChatGPT
# Google quickstart code: https://developers.google.com/gmail/api/quickstart/python
import base64
import os.path
from mailcap import subst

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
  """Shows basic usage of the Gmail API.
  Lists the user's Gmail labels.
  """
  creds = configure_credentials()

  try:
    # Call the Gmail API
    service = build("gmail", "v1", credentials=creds)
    labels = service.users().labels().list(userId="me").execute()
    label_name = "INBOX"
    label_id = next((label["id"] for label in labels["labels"] if label["name"].upper() == label_name), None)
    results = service.users().messages().list(userId="me", labelIds=[label_id], maxResults=3).execute()
    messages = results.get("messages", [])

    if not messages:
      print("No labels found.")
      return
    for msg in messages:
      msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
      parts = msg_data["payload"].get("parts", [])
      for part in parts:
        if part["mimeType"] == "text/plain":
          body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
          subject = get_subject(msg_data)
          sender = get_sender(msg_data)
          print(f"{sender}\n{subject}\n{'='*100}\n{body}\n\n\n")
      #print(f"{msg_data["parts"]["headers"]}")

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")


def configure_credentials():
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      try:
        creds.refresh(Request())
      # handles expired refresh tokens
      except RefreshError:
        creds = force_authenticate(creds)
    else:
      creds = force_authenticate(creds)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())
  return creds

# forces authentication through web redirect
def force_authenticate(creds):
  flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json", SCOPES
  )
  creds = flow.run_local_server(port=0)
  return creds


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


if __name__ == "__main__":
  main()