# Email summarization: run orchestration, Gemini prompt, sending, trigger configs
# Parts modified by both me and ChatGPT
import base64
import json
import re
import markdown
import zoneinfo

from dataclasses import dataclass
from datetime import datetime

from google import genai
from googleapiclient.errors import HttpError

from email_annihilator.store import get_last_history_id, set_last_history_id


HISTORY_FILE = "secrets/history_id/history_id.txt"
ACTIVE_PROMPT = "prompts/v2.txt"

@dataclass
class Email:
    subject: str
    sender: str
    body: str
    time_sent: datetime

def run(gmail, configs):
  """
  Runs email summarization on authenticated account.
  :param gmail: GmailClient
  :param configs: run configs in form of dict
  """
  hours = int(configs["hours"]) if "hours" in configs else 24
  try:
    emails = gmail.fetch_recent(hours)

    if not emails:
      print("No labels found.")
      return
    summary = summarize(emails, configs)
    send = gmail.send_html(summary)
    # print(send)
  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")

def summarize(emails, configs):
  """
  Summarizes the emails provided and returns the html
  :param emails: Emails to be summarized
  :param configs: Configs for summary
  :return: html representation of the summary
  """
  # Setup GeminiAPI client
  with open("secrets/gemini_api_key/gemini_api_key.txt", "r") as f:
    api_key = f.read().strip()
  client = genai.Client(api_key=api_key)

  # build the prompt
  with open(ACTIVE_PROMPT, "r") as f:
    prompt = f.read()
  tz = zoneinfo.ZoneInfo("America/New_York")
  prompt += f"{datetime.now(tz=tz)}\n"
  addon = configs["addon"] if "addon" in configs else "None"
  prompt += f"Additional request details: {addon}\n"
  prompt += "--- Emails for Summarization ---\n"

  # add the emails
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
  #print(response.text)
  # convert to HTML
  return markdown.markdown(response.text)

async def update_historyID(gmail, request):
  """
  Updates the history ID in firestore
  :param gmail: GmailClient
  :param request: The requested provided by pub sub
  :return: the body of the newest email under the custom "trigger" label since last update
  """
  new_history_id = await get_history_id_from_pubsub(request)
  last_history_id = get_last_history_id()

  # FIRST TIME BOOTSTRAP
  if last_history_id is None:
    set_last_history_id(new_history_id)
    return "Initialized history cursor", 200

  try:
    # Pull everything since last cursor
    return gmail.latest_trigger_body(last_history_id)

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

def parse_configs(body):
  """
  Parses the run configs from the body of a trigger email
  :param body: plain text body of the trigger email, None if there is none
  :return: The configs in the form of a dict
  """
  configs = {}
  if body is None:
    return configs

  body = body.lower()
  config_list = body.split(",")
  for config in config_list:
    pattern = "^[\w\s]*:[\w\s]*$"
    if re.match(pattern, config):
      cfg_pair = config.split(":")
      configs[cfg_pair[0].strip()] = cfg_pair[1]
    else:
      # TODO: handle invalid configs
      continue
  return configs

