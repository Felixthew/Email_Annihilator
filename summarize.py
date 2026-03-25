# This file is based off of Google's quickstart code modified by both me and ChatGPT
# Google quickstart code: https://developers.google.com/gmail/api/quickstart/python
import base64
import json
import os.path
import os
import pickle
import markdown

from datetime import datetime, timedelta, timezone

from google import genai
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from Email_Message import Email
from firestore_manager import get_last_history_id, set_last_history_id


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          'https://www.googleapis.com/auth/gmail.send']

_mode = "cloud"
TOKEN_PATH = "secrets/token/token.json"
HISTORY_FILE = "secrets/history_id/history_id.txt"
ACTIVE_PROMPT = "prompts/v2.txt"

def run(hours = 48):
  """
  Runs email summarization on authenticated account.
  :param hours: Timeframe of emails to summarize
  """
  creds = configure_credentials()
  try:
    # Call the Gmail API
    service = build("gmail", "v1", credentials=creds)
    labels = service.users().labels().list(userId="me").execute()
    label_name = "INBOX"
    print([(label["name"], label["id"]) for label in labels["labels"]])
    label_id = next((label["id"] for label in labels["labels"] if label["name"].upper() == label_name), None)
    results = fetch_mail(service, label_id, hours=hours)
    messages = results.get("messages", [])

    if not messages:
      print("No labels found.")
      return
    emails = []
    for msg in messages:
      msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
      parts = msg_data["payload"].get("parts", [])
      for part in parts:
        if part["mimeType"] == "text/plain":
          emails.append(Email(
            body=base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8"),
            subject=get_subject(msg_data),
            sender=get_sender(msg_data),
            time_sent=get_time_sent(msg_data)
          ))
    # with open("emails.pkl", 'wb') as f:
    #   print(emails)
    #   pickle.dump(emails, f)
    summary = summarize(emails)
    send = send_summary(service,summary)
    print(send)
  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")

def fetch_mail(service, label_id, hours=24):
  # Get UTC time __ hours ago
  time_n_hours_ago = datetime.now() - timedelta(hours=hours)
  timestamp = int(time_n_hours_ago.timestamp())

  query = f"after:{timestamp}"

  return service.users().messages().list(userId="me", q=query,  labelIds=[label_id], maxResults=100).execute()


def configure_credentials():
  if not os.path.exists(TOKEN_PATH):
    raise RuntimeError("token.json missing — authenticate locally first")

  creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

  if creds.expired and creds.refresh_token:
    creds.refresh(Request())

  if not creds.valid:
    if _mode == "local":
      creds = force_authenticate(creds)
      with open(TOKEN_PATH, "w") as token:
        token.write(creds.to_json())
    else:
      raise RuntimeError("Credentials invalid and cannot refresh")

  return creds

# forces authentication through web redirect
def force_authenticate(creds):
  flow = InstalledAppFlow.from_client_secrets_file(
    "secrets/credentials.json", SCOPES
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

def summarize(emails):
  """
  Summarizes the emails provided and returns the html
  :param emails: Emails to be summarized
  :return: html representation of the summary
  """
  with open("secrets/gemini_api_key/gemini_api_key.txt", "r") as f:
    api_key = f.read().strip()
  client = genai.Client(api_key=api_key)

  with open(ACTIVE_PROMPT, "r") as f:
    prompt = f.read()
  prompt += f"{datetime.now().astimezone()}\n--- Emails for Summarization ---\n"
  email_text = ""
  for i, email in enumerate(emails):
    email_text += f"--- Email {i + 1} ---\n"
    email_text += f"From: {email.sender}\n"
    email_text += f"Subject: {email.subject}\n"
    email_text += f"Time sent: {email.time_sent}\n"
    email_text += f"Body:\n{email.body}\n\n"

  response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents= prompt + email_text
  )
  print(response.text)
  # convert to HTML
  return markdown.markdown(response.text)

def send_summary(service, summary):
  """
  Sends the summary email
  :param service: The service to send the email through
  :param summary: The summary to be sent
  :return: The gmail API response on send
  """
  try:
    message = EmailMessage()

    message.set_content("The summary is in html")

    message.add_alternative(summary, subtype="html")

    message["To"] = "watt.f@northeastern.edu"
    message["From"] = "Email Condenser"
    message["Subject"] = "Email Summary"

    # encoded message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    create_message = {"raw": encoded_message}
    # pylint: disable=E1101
    send_message = (
      service.users()
      .messages()
      .send(userId="me", body=create_message)
      .execute()
    )
    print(f'Message Id: {send_message["id"]}')
  except HttpError as error:
    print(f"An error occurred: {error}")
    send_message = None
  return send_message

async def update_historyID(request):
  """
  Updates the history ID in firestore
  :param request: The requested provided by pub sub
  """
  new_history_id = await get_history_id_from_pubsub(request)
  last_history_id = get_last_history_id()

  # FIRST TIME BOOTSTRAP
  if last_history_id is None:
    set_last_history_id(new_history_id)
    return "Initialized history cursor", 200

  try:
    creds = configure_credentials()
    service = build("gmail", "v1", credentials=creds)
    # Pull everything since last cursor
    history = service.users().history().list(
      userId="me",
      startHistoryId=last_history_id,
      historyTypes=["messageAdded"],
      labelId="Label_5007763253467252103"
    ).execute()

    # process_history(history)  # your existing logic

  except Exception as e:
    # Log but DO NOT block cursor advancement
    print("Could not advance history")

  finally:
    set_last_history_id(new_history_id)

async def get_history_id_from_pubsub(request):
  """
  Extracts the history ID from the pub sub request
  :param request: The pub sub request
  :return: the history ID
  """
  envelope = await request.json()
  msg = envelope["message"]
  data = base64.b64decode(msg["data"]).decode("utf-8")
  payload = json.loads(data)
  return payload["historyId"]

if __name__ == "__main__":
  run()