from google.cloud import firestore

db = firestore.Client()

COLLECTION = "gmail_data"
DOC_ID = "historyID"

def get_last_history_id() -> str | None:
    doc = db.collection(COLLECTION).document(DOC_ID).get()
    if doc.exists:
        return doc.to_dict().get("last_history_id")
    return None

def set_last_history_id(history_id: str):
    db.collection(COLLECTION).document(DOC_ID).set(
        {"last_history_id": history_id},
        merge=True
    )
