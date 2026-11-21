from google.cloud import firestore


class HistoryStore:
    def __init__(self, db: firestore.Client):
        """
        :param db: a firestore client, built in main.py
        """
        self.doc = db.collection("gmail_data").document("historyID")

    def get(self) -> str | None:
        snap = self.doc.get()
        return snap.to_dict().get("last_history_id") if snap.exists else None

    def set(self, history_id: str):
        self.doc.set({"last_history_id": history_id})