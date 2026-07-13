"""
UnifyOps - Storage Service

Manages file persistence to Google Cloud Storage (GCS) (FR-1.1.3).
Provides local file storage fallback for development when GCP credentials are not active.
"""

import os
from pathlib import Path
from google.cloud import storage  # type: ignore
from app.core.config import settings

# Setup local storage directory for dev/fallback
LOCAL_STORAGE_DIR = Path("storage")
LOCAL_STORAGE_DIR.mkdir(exist_ok=True)


class StorageService:
    """Manages file storage operations to Cloud Storage or local fallback."""

    def __init__(self) -> None:
        self.bucket_name = settings.gcs_bucket_name
        self.use_gcs = False

        # Attempt to initialize GCS client
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                self.client = storage.Client()
                # Check if bucket exists/reachable
                self.bucket = self.client.bucket(self.bucket_name)
                self.use_gcs = True
            except Exception as e:
                # Log or handle fallback
                print(
                    f"[StorageService] Failed to initialize GCS client: {e}. Falling back to local storage."
                )
        else:
            print(
                "[StorageService] GOOGLE_APPLICATION_CREDENTIALS not set. Falling back to local storage."
            )

    def upload_file(
        self,
        file_content: bytes,
        destination_blob_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Uploads a file's raw content to storage (GCS or local fallback).
        Returns the URI path (e.g. gs://... or local file path).
        """
        if self.use_gcs:
            try:
                blob = self.bucket.blob(destination_blob_name)
                blob.upload_from_string(file_content, content_type=content_type)
                return f"gs://{self.bucket_name}/{destination_blob_name}"
            except Exception as e:
                print(
                    f"[StorageService] GCS Upload failed: {e}. Falling back to local write."
                )

        # Local fallback
        local_path = LOCAL_STORAGE_DIR / destination_blob_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_content)
        return str(local_path.absolute())

    def download_file(self, file_path: str) -> bytes:
        """Downloads a file's content from storage."""
        if file_path.startswith("gs://"):
            try:
                blob_path = file_path.replace(f"gs://{self.bucket_name}/", "")
                blob = self.bucket.blob(blob_path)
                return blob.download_as_bytes()
            except Exception as e:
                print(f"[StorageService] GCS Download failed: {e}")
                # Try local storage fallback if the file is copied locally
                local_fallback_name = file_path.split("/")[-1]
                local_path = LOCAL_STORAGE_DIR / local_fallback_name
                if local_path.exists():
                    return local_path.read_bytes()
                raise e

        # Local file path
        path = Path(file_path)
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"File not found: {file_path}")


storage_service = StorageService()
