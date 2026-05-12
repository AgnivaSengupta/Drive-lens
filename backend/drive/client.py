from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'backend', 'credentials', 'service-account.json')

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    return build("drive", "v3", credentials=creds)