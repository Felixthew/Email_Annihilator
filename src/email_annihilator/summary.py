# Email summarization: run orchestration, Gemini prompt, sending, trigger configs
# Parts modified by both me and ChatGPT
import re
import markdown
import zoneinfo

from datetime import datetime

from email_annihilator.gemini import GeminiClient
from email_annihilator.gmail import GmailClient
from email_annihilator.store import HistoryStore


def run(gmail: GmailClient, gemini: GeminiClient, prompt_path: str, configs):
  """
  Runs email summarization on authenticated account.
  :param gmail: GmailClient
  :param gemini: GeminiClient
  :param prompt_path: path to the prompt file
  :param configs: run configs in form of dict
  """
  hours = int(configs["hours"]) if "hours" in configs else 24
  emails = gmail.fetch_recent(hours)

  if not emails:
    print("No labels found.")
    return
  summary = summarize(gemini, prompt_path, emails, configs)
  gmail.send_html(summary)

def summarize(gemini: GeminiClient, prompt_path: str, emails, configs):
  """
  Summarizes the emails provided and returns the html
  :param gemini: GeminiClient
  :param prompt_path: path to the prompt file
  :param emails: Emails to be summarized
  :param configs: Configs for summary
  :return: html representation of the summary
  """
  # build the prompt
  with open(prompt_path, "r") as f:
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

  response = gemini.generate(prompt + email_text)
  # convert to HTML
  return markdown.markdown(response)

def update_historyID(gmail: GmailClient, store: HistoryStore, new_history_id) -> tuple[bool, str | None]:
  """
  Updates the history ID in firestore
  :param gmail: GmailClient
  :param store: HistoryStore
  :param new_history_id: the history ID from the pub sub notification
  :return: (should_run, body). should_run is False only on the first call, which just initializes the cursor.
           body is the newest email under the custom "trigger" label since last update, None if there is none.
  """
  last_history_id = store.get()

  # FIRST TIME BOOTSTRAP
  if last_history_id is None:
    store.set(new_history_id)
    return False, None

  try:
    # Pull everything since last cursor
    return True, gmail.latest_trigger_body(last_history_id)

  except Exception as e:
    # Log but DO NOT block cursor advancement
    print(f"Could not advance history: {e}")
    return True, None

  finally:
    store.set(new_history_id)

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

