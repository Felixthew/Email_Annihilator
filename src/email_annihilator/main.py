import base64
import json

from google.cloud import firestore
from fastapi import FastAPI, Request
from email_annihilator.config import Settings
from email_annihilator.gemini import GeminiClient
from email_annihilator.gmail import GmailClient, build_service
from email_annihilator.summary import run, update_historyID, parse_configs
from email_annihilator.store import HistoryStore

app = FastAPI()
settings = Settings()

def build_gmail() -> GmailClient:
    service = build_service(settings.token_path, settings.credentials_path, settings.local_auth)
    return GmailClient(service, settings.trigger_label, settings.topic, settings.recipient)

def build_store() -> HistoryStore:
    return HistoryStore(firestore.Client())

def build_gemini() -> GeminiClient:
    with open(settings.gemini_key_path, "r") as f:
        return GeminiClient(f.read().strip(), settings.gemini_model)

async def get_history_id_from_pubsub(request: Request):
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

@app.post("/trigger/scheduled")
def scheduled_trigger():
    run(build_gmail(), build_gemini(), settings.prompt_path, {})
    return {"status": "ok", "source": "scheduler"}

@app.post("/trigger/email")
async def email_trigger(request: Request):
    try:
        gmail = build_gmail()
        new_history_id = await get_history_id_from_pubsub(request)
        should_run, trigger_configs = update_historyID(gmail, build_store(), new_history_id)
        if should_run:
            run(gmail, build_gemini(), settings.prompt_path, parse_configs(trigger_configs))
    except Exception as e:
        print("ERROR: ", e)
    return {"status": "ok", "source": "pubsub"}

@app.post("/trigger/watch")
def register_watch():
    build_gmail().register_watch()
    return {"status": "ok"}

@app.get("/")
def health():
    return {"status": "alive"}


if __name__ == "__main__":
    # one-off 24h summary, no server
    run(build_gmail(), build_gemini(), settings.prompt_path, {})
