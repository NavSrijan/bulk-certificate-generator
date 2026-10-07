import os
import re
import zipfile
from pathlib import Path
from typing import List
from app.config import settings


class StorageService:
    """Manages file storage paths and bulk ZIP archive creation."""

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize recipient name or title for safe use in file names."""
        # Replace non-alphanumeric characters with underscores
        cleaned = re.sub(r"[^\w\s-]", "", name).strip()
        cleaned = re.sub(r"[-\s]+", "_", cleaned).strip("_")
        return cleaned or "recipient"

    @classmethod
    def get_certificate_path(cls, job_id: str, certificate_id: str, recipient_name: str) -> Path:
        """Generate absolute path for an individual certificate PDF."""
        safe_name = cls.sanitize_filename(recipient_name)
        job_dir = Path(settings.STORAGE_DIR) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir / f"{certificate_id}_{safe_name}.pdf"

    @classmethod
    def get_zip_path(cls, job_id: str) -> Path:
        """Generate absolute path for a job's bulk ZIP archive."""
        zip_dir = Path(settings.ZIP_STORAGE_DIR)
        zip_dir.mkdir(parents=True, exist_ok=True)
        return zip_dir / f"certificates_job_{job_id}.zip"

    @classmethod
    def create_job_zip_archive(cls, job_id: str, certificates: List[dict]) -> Path:
        """
        Bundle all existing generated certificate PDFs for a job into a ZIP archive.
        certificates parameter is a list of dicts or objects with 'file_path', 'recipient_name', 'certificate_code'.
        """
        zip_path = cls.get_zip_path(job_id)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for cert in certificates:
                file_path = cert.get("file_path") if isinstance(cert, dict) else getattr(cert, "file_path", None)
                if file_path and os.path.exists(file_path):
                    name = cert.get("recipient_name") if isinstance(cert, dict) else getattr(cert, "recipient_name", "")
                    code = cert.get("certificate_code") if isinstance(cert, dict) else getattr(cert, "certificate_code", "")
                    safe_name = cls.sanitize_filename(name)
                    archive_name = f"Certificate_{safe_name}_{code}.pdf"
                    zip_file.write(file_path, arcname=archive_name)

        return zip_path
