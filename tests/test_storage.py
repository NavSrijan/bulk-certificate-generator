import os
import zipfile
from app.services.storage import StorageService


def test_sanitize_filename():
    assert StorageService.sanitize_filename("John Doe") == "John_Doe"
    assert StorageService.sanitize_filename("Jane / Doe & Sons!") == "Jane_Doe_Sons"
    assert StorageService.sanitize_filename("   ---   ") == "recipient"
    assert StorageService.sanitize_filename("José-María") == "José_María"


def test_create_job_zip_archive(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.ZIP_STORAGE_DIR", str(tmp_path / "zips"))

    # Create dummy pdf files
    pdf1 = tmp_path / "pdf1.pdf"
    pdf2 = tmp_path / "pdf2.pdf"
    pdf1.write_bytes(b"%PDF-test1")
    pdf2.write_bytes(b"%PDF-test2")

    certs = [
        {"file_path": str(pdf1), "recipient_name": "Alice Bob", "certificate_code": "CERT-1111"},
        {"file_path": str(pdf2), "recipient_name": "Charlie Day", "certificate_code": "CERT-2222"},
    ]

    zip_path = StorageService.create_job_zip_archive("test-job-123", certs)
    assert os.path.exists(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert len(names) == 2
        assert "Certificate_Alice_Bob_CERT-1111.pdf" in names
        assert "Certificate_Charlie_Day_CERT-2222.pdf" in names
