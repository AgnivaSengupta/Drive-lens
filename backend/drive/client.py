import json
import os

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build


load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SERVICE_ACCOUNT_FILE = os.path.join(
    PROJECT_ROOT, "credentials", "service-account.json"
)
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", DEFAULT_SERVICE_ACCOUNT_FILE)
if not os.path.isabs(SERVICE_ACCOUNT_FILE):
    SERVICE_ACCOUNT_FILE = os.path.join(PROJECT_ROOT, SERVICE_ACCOUNT_FILE)

def get_drive_service():
    service_account_json = os.getenv("SERVICE_ACCOUNT_JSON")
    if service_account_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=SCOPES,
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES,
        )

    return build("drive", "v3", credentials=creds)
