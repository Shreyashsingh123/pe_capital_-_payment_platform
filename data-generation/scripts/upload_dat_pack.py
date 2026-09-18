"""
ONE-TIME script to land the external .dat feed pack into ADLS..
Run manually, once, after extracting PE_Fund_Sample_DAT_Feed_Pack.zip:

    python scripts/upload_dat_pack.py --source ./dat_pack_extracted

Filename convention expected: <FEED_TYPE>_<YYYYMMDD>_<HHMMSS>[_SUFFIX].dat
Lands each file at:
    external_dat/<feed_type>/business_date=<YYYY-MM-DD>/<original filename>

MANIFEST.dat is uploaded once to external_dat/_manifest/.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FILENAME_PATTERN = re.compile(r"^([A-Z]+)_(\d{8})_(\d{6})(?:_(\w+))?\.dat$")
SKIP_FILES = {"README.txt"}


def upload_dat_pack(source_dir: str) -> None:
    files = sorted(os.listdir(source_dir))
    uploaded, skipped = 0, 0

    for filename in files:
        if filename in SKIP_FILES or filename.endswith(".zip"):
            continue

        if filename == "MANIFEST.dat":
            _upload_single_file(source_dir, filename, "external_dat/_manifest")
            uploaded += 1
            continue

        match = FILENAME_PATTERN.match(filename)
        if not match:
            print(f"[upload_dat_pack] Skipping unrecognized filename: {filename}")
            skipped += 1
            continue

        feed_type, date_str, _time_str, _suffix = match.groups()
        business_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
        remote_dir = f"external_dat/{feed_type.lower()}/business_date={business_date}"

        # upload_folder uploads every file in a local dir -- since we're
        # uploading one file at a time here, stage it via the same
        # underlying call by pointing at a temp single-file view.
        _upload_single_file(source_dir, filename, remote_dir)
        uploaded += 1

    print(f"[upload_dat_pack] Done. Uploaded {uploaded} files, skipped {skipped}.")


def _upload_single_file(source_dir: str, filename: str, remote_dir: str) -> None:
    """Uploads exactly one file to a specific remote path, reusing the
    same auth/connection pattern as adls_upload.upload_folder."""
    import os as _os
    from azure.storage.filedatalake import DataLakeServiceClient

    conn_str = _os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print(f"[upload_dat_pack] No connection string set — skipping {filename}")
        return

    container = _os.environ.get("ADLS_CONTAINER", "ingested")
    service_client = DataLakeServiceClient.from_connection_string(conn_str)
    fs_client = service_client.get_file_system_client(container)
    try:
        fs_client.create_file_system()
    except Exception:
        pass

    local_path = _os.path.join(source_dir, filename)
    remote_path = f"{remote_dir}/{filename}"
    file_client = fs_client.get_file_client(remote_path)
    with open(local_path, "rb") as f:
        data = f.read()
    file_client.upload_data(data, overwrite=True)
    print(f"[upload_dat_pack] Uploaded {remote_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to the extracted .dat pack folder")
    args = parser.parse_args()
    upload_dat_pack(args.source)
