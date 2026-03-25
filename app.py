# app.py
from fastapi import FastAPI, Request, HTTPException
from summarize import run, update_historyID, parse_configs, init_service
from gmail_watch import register_watch

app = FastAPI()

@app.post("/trigger/scheduled")
def scheduled_trigger():
    service = init_service()
    run(service, {})
    return {"status": "ok", "source": "scheduler"}

@app.post("/trigger/email")
async def email_trigger(request: Request):
    try:
        service = init_service()
        history = await update_historyID(service, request)
        configs = parse_configs(service, history)
        run(service, configs)
    except Exception as e:
        print("ERROR: ", e)
    return {"status": "ok", "source": "pubsub"}

@app.post("/trigger/watch")
def register_watch():
    # Update this to take service arg after app is published
    register_watch()
    return {"status": "ok"}

@app.get("/")
def health():
    return {"status": "alive"}
