# Google quickstart code: https://developers.google.com/gmail/api/quickstart/python
import base64
import os.path

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
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

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
          print(base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8"))
      #print(f"{msg_data["parts"]["headers"]}")

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")


if __name__ == "__main__":
  main()