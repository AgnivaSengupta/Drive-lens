import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1. Setup Credentials
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'credentials', 'service-account.json')

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# 2. Build the Service
service = build("drive", "v3", credentials=creds)

# 3. Test the Query (The 'q' parameter is the heart of the assignment)
# Replace with your specific folder ID
FOLDER_ID = "1tqF4Dj1R46f9LiF-zKX5goBdxSzgTIV2"


def test_search():
    query = f"'{FOLDER_ID}' in parents"
    results = (
        service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    )

    files = results.get("files", [])

    if not files:
        print("No files found.")
    else:
        print("Files found:")
        for file in files:
            print(f"{file['name']} ({file['id']})")


if __name__ == "__main__":
    test_search()
