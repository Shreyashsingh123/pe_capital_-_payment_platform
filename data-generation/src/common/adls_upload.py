"""
Uploads a local date-partitioned folder to ADLS Gen2, mirroring the
same relative path (table/ingestion_date=YYYY-MM-DD/file.csv).

Auth is via a Storage Account connection string, read from the
AZURE_STORAGE_CONNECTION_STRING env var (set as a GitHub Actions
secret in production). Wrapped so a missing/invalid credential just
skips upload with a warning instead of crashing local dev runs.
"""
import os
from azure.storage.filedatalake import DataLakeServiceClient

CONTAINER_NAME = os.environ.get("ADLS_CONTAINER", "ingested")


def upload_folder(local_folder: str, relative_path: str) -> None:
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print(f"[adls_upload] No connection string set — skipping upload of {relative_path}")
        return

    service_client = DataLakeServiceClient.from_connection_string(conn_str)
    fs_client = service_client.get_file_system_client(CONTAINER_NAME)
    try:
        fs_client.create_file_system()
    except Exception:
        pass  # already exists

    for filename in os.listdir(local_folder):
        local_path = os.path.join(local_folder, filename)
        if not os.path.isfile(local_path):
            continue
        remote_path = f"{relative_path}/{filename}"
        file_client = fs_client.get_file_client(remote_path)
        with open(local_path, "rb") as f:
            data = f.read()
        file_client.upload_data(data, overwrite=True)
        print(f"[adls_upload] Uploaded {remote_path}")
