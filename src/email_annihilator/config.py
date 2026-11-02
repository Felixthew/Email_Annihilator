# App settings: values that stay the same across runs but could differ per deployment
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Gmail auth
    token_path: str = "secrets/token/token.json"
    credentials_path: str = "secrets/credentials.json"
    local_auth: bool = False  # True: open a browser OAuth flow when the token is invalid

    # Gmail behaviour
    trigger_label: str = "Label_5007763253467252103"
    topic: str = "projects/email-endeavor/topics/gmail-push"
    recipient: str = "watt.f@northeastern.edu"
