# app.py
from fastapi import FastAPI, Request, HTTPException
from summarize import run, update_historyID
from gmail_watch import register_watch
import os

app = FastAPI()

@app.post("/trigger/scheduled")
def scheduled_trigger():
    run()
    return {"status": "ok", "source": "scheduler"}

@app.post("/trigger/email")
async def email_trigger(request: Request):
    try:
        await update_historyID(request)
        run()
    except Exception as e:
        print("ERROR: ", e)
    return {"status": "ok", "source": "pubsub"}

@app.post("/trigger/watch")
def register_watch():
    register_watch()
    return {"status": "ok"}
@app.get("/")
def health():
    return {"status": "alive"}
