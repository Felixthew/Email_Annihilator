# Email_Message.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Email:
    subject: str
    sender: str
    body: str
    time_sent: datetime
