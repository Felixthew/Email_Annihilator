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

_mode = "local"
TOKEN_PATH = "secrets/token/token.json"
HISTORY_FILE = "secrets/history_id/history_id.txt"

def run(hours = 48):
  """Shows basic usage of the Gmail API.
  Lists the user's Gmail labels.
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
  with open("secrets/gemini_api_key/gemini_api_key.txt", "r") as f:
    api_key = f.read().strip()
  client = genai.Client(api_key=api_key)

  prompt = f"""
      You are a highly skilled and efficient personal assistant specializing in email summarization. Your primary goal is to provide a concise and actionable summary of my daily emails, prioritizing information that is most critical to my academic and personal assignments.
      
      Your judgment should be based on the following hierarchy of importance:
      Tier 1 (Critical Information):
      - Assignments: Due dates, submission details, and requirements for all school assignments.
      - Class/Course Info: Updates to course schedules, changes in class times, or new materials posted by professors.
      - Action Items: Any explicit requests for a response or a task I need to complete.

      Tier 2 (Secondary Information):
      - Meeting and event details (e.g., location, time, and agenda).
      - General announcements from academic or personal services.

      Tier 3 (Less Important Information):
      - Promotional emails, newsletters, or general company updates.
      - Social invites or non-critical personal messages.

      The final summary should be structured in two distinct parts:

      Part 1: Key Action Items and Critical Information
      - This section must be a single, highly condensed paragraph that combines all the most important information from Tier 1 emails. It should be written in a direct, to-the-point style, as if you are telling me what I absolutely need to know right now.
      - The paragraph should be a cohesive narrative, not a list of bullet points.

      Part 2: Less Important Updates (Bullet Points)
      - This section should be a concise bullet-point list summarizing the less critical information from Tier 2 and Tier 3 emails.
      - Each bullet point should start with the sender and a brief summary.
      - If an email has no relevant information, it should not be included in the summary at all.
      
      Note: All emails are forwarded from watt.f@northeastern.edu. Please ignore the forwarding details and treat the original sender as the source of the email. Ignore any emails that were not forwarded into the inbox. Also ignore previous "Email summary" emails those are previous summaries you provided.
      Also note the time sent of the emails in relation to the time of this request which is {datetime.now().astimezone()}
      --- Emails for Summarization ---
      """
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
  envelope = await request.json()
  msg = envelope["message"]
  data = base64.b64decode(msg["data"]).decode("utf-8")
  payload = json.loads(data)
  return payload["historyId"]

if __name__ == "__main__":
  run()