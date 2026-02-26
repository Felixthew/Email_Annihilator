# app.py
from fastapi import FastAPI, Request, HTTPException
from quickstart import run, update_historyID
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

@app.get("/")
def health():
    return {"status": "alive"}
