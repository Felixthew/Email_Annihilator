from fastapi import FastAPI, Request
from email_annihilator.config import Settings
from email_annihilator.gmail import GmailClient, build_service
from email_annihilator.summary import run, update_historyID, parse_configs

app = FastAPI()
settings = Settings()

def build_gmail() -> GmailClient:
    service = build_service(settings.token_path, settings.credentials_path, settings.local_auth)
    return GmailClient(service, settings.trigger_label, settings.topic, settings.recipient)

@app.post("/trigger/scheduled")
def scheduled_trigger():
    gmail = build_gmail()
    run(gmail, {})
    return {"status": "ok", "source": "scheduler"}

@app.post("/trigger/email")
async def email_trigger(request: Request):
    try:
        gmail = build_gmail()
        body = await update_historyID(gmail, request)
        configs = parse_configs(body)
        run(gmail, configs)
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
    run(build_gmail(), {})
