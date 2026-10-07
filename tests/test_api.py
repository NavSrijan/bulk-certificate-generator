import io
import zipfile
from fastapi import status


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "documentation" in data
    assert data["endpoints"]["create_job"] == "POST /api/v1/jobs"


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_create_job_and_poll_status(client):
    payload = {
        "title": "Cloud Computing Masterclass",
        "description": "For mastery of containerization and orchestration architectures.",
        "issuer_name": "Tech Academy",
        "issuer_title": "Certification Board",
        "issue_date": "2026-10-08",
        "recipients": [
            {"name": "Alice Cooper", "email": "alice@example.com"},
            {"name": "Bob Dylan", "email": "bob@example.com", "custom_id": "STUDENT-99"},
        ],
    }

    # 1. Submit Job
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert "job_id" in body
    job_id = body["job_id"]
    assert body["total_recipients"] == 2
    assert "status_url" in body

    # 2. Check Job Status (TestClient executes background task synchronously during request)
    status_resp = client.get(f"/api/v1/jobs/{job_id}?include_certificates=true")
    assert status_resp.status_code == status.HTTP_200_OK
    job_data = status_resp.json()

    assert job_data["id"] == job_id
    assert job_data["status"] == "COMPLETED"
    assert job_data["total_count"] == 2
    assert job_data["processed_count"] == 2
    assert job_data["success_count"] == 2
    assert job_data["failed_count"] == 0
    assert job_data["progress_percentage"] == 100.0
    assert job_data["certificates_download_url"] is not None
    assert len(job_data["certificates"]) == 2

    # 3. Retrieve Certificate Metadata
    cert_1 = job_data["certificates"][0]
    cert_id = cert_1["id"]
    cert_code = cert_1["certificate_code"]

    cert_detail_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert cert_detail_resp.status_code == status.HTTP_200_OK
    assert cert_detail_resp.json()["recipient_name"] == "Alice Cooper"
    assert cert_detail_resp.json()["status"] == "COMPLETED"

    # 4. Download Single Certificate PDF
    pdf_resp = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert pdf_resp.status_code == status.HTTP_200_OK
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-")

    # 5. Bulk Download Job Certificates ZIP
    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_resp.status_code == status.HTTP_200_OK
    assert zip_resp.headers["content-type"] == "application/zip"

    # Check zip contents
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        file_list = zf.namelist()
        assert len(file_list) == 2
        assert any("Alice_Cooper" in f for f in file_list)
        assert any("Bob_Dylan" in f for f in file_list)

    # 6. Public Verification Endpoint
    verify_resp = client.get(f"/api/v1/verify/{cert_code}")
    assert verify_resp.status_code == status.HTTP_200_OK
    verify_data = verify_resp.json()
    assert verify_data["is_valid"] is True
    assert verify_data["recipient_name"] == "Alice Cooper"
    assert verify_data["title"] == "Cloud Computing Masterclass"


def test_input_validation_empty_recipients(client):
    payload = {
        "title": "Data Engineering",
        "description": "Completed course",
        "issuer_name": "Instructor",
        "recipients": [],  # Empty
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_input_validation_invalid_email(client):
    payload = {
        "title": "Data Engineering",
        "description": "Completed course",
        "issuer_name": "Instructor",
        "recipients": [
            {"name": "Valid Name", "email": "not-an-email-at-all"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_input_validation_blank_name_and_title(client):
    payload = {
        "title": "   ",  # Blank title
        "description": "Valid description",
        "issuer_name": "Issuer",
        "recipients": [
            {"name": "   ", "email": "valid@example.com"},  # Blank name
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_partial_failure_isolation_via_api(client):
    """Ensure invalid / failing recipient does not stop valid recipient generation."""
    payload = {
        "title": "Resilience Engineering",
        "description": "Testing graceful degradation and failure isolation.",
        "issuer_name": "Chaos Testing Lab",
        "recipients": [
            {"name": "Valid Recipient", "email": "valid@example.com"},
            {"name": "Failing Recipient", "email": "fail_user@simulate-failure.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    # Check status
    status_resp = client.get(f"/api/v1/jobs/{job_id}?include_certificates=true")
    assert status_resp.status_code == status.HTTP_200_OK
    job_data = status_resp.json()

    assert job_data["status"] == "PARTIALLY_COMPLETED"
    assert job_data["total_count"] == 2
    assert job_data["processed_count"] == 2
    assert job_data["success_count"] == 1
    assert job_data["failed_count"] == 1

    certs = job_data["certificates"]
    success_cert = next(c for c in certs if c["recipient_email"] == "valid@example.com")
    failed_cert = next(c for c in certs if c["recipient_email"] == "fail_user@simulate-failure.com")

    assert success_cert["status"] == "COMPLETED"
    assert success_cert["download_url"] is not None

    assert failed_cert["status"] == "FAILED"
    assert failed_cert["download_url"] is None
    assert "Simulated generation failure" in failed_cert["error_message"]

    # Failed certificate download should return 400
    failed_dl_resp = client.get(f"/api/v1/certificates/{failed_cert['id']}/download")
    assert failed_dl_resp.status_code == status.HTTP_400_BAD_REQUEST

    # Bulk download ZIP should still contain the 1 successful certificate
    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_resp.status_code == status.HTTP_200_OK
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        file_list = zf.namelist()
        assert len(file_list) == 1
        assert "Valid_Recipient" in file_list[0]


def test_not_found_endpoints(client):
    resp1 = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert resp1.status_code == status.HTTP_404_NOT_FOUND

    resp2 = client.get("/api/v1/certificates/00000000-0000-0000-0000-000000000000")
    assert resp2.status_code == status.HTTP_404_NOT_FOUND

    resp3 = client.get("/api/v1/verify/CERT-NONEXISTENT")
    assert resp3.status_code == status.HTTP_404_NOT_FOUND


def test_list_jobs(client):
    # Create two jobs
    for i in range(2):
        client.post(
            "/api/v1/jobs",
            json={
                "title": f"Batch Event {i}",
                "description": "Annual training",
                "issuer_name": "Organizer",
                "recipients": [{"name": f"User {i}", "email": f"user{i}@example.com"}],
            },
        )

    list_resp = client.get("/api/v1/jobs?limit=10")
    assert list_resp.status_code == status.HTTP_200_OK
    jobs = list_resp.json()
    assert len(jobs) >= 2


def test_filter_job_certificates_by_status(client):
    payload = {
        "title": "Status Filter Test Event",
        "description": "Testing status filtering query parameter.",
        "issuer_name": "QA Lead",
        "recipients": [
            {"name": "Pass User 1", "email": "pass1@example.com"},
            {"name": "Pass User 2", "email": "pass2@example.com"},
            {"name": "Fail User", "email": "fail@simulate-failure.com"},
        ],
    }

    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    # Filter completed
    completed_resp = client.get(f"/api/v1/jobs/{job_id}/certificates?status=COMPLETED")
    assert completed_resp.status_code == status.HTTP_200_OK
    completed_items = completed_resp.json()
    assert len(completed_items) == 2
    assert all(c["status"] == "COMPLETED" for c in completed_items)

    # Filter failed
    failed_resp = client.get(f"/api/v1/jobs/{job_id}/certificates?status=FAILED")
    assert failed_resp.status_code == status.HTTP_200_OK
    failed_items = failed_resp.json()
    assert len(failed_items) == 1
    assert failed_items[0]["status"] == "FAILED"


def test_bulk_generation_large_batch(client):
    """Test generating a bulk batch of 35 certificates efficiently."""
    recipients = [
        {"name": f"Participant {i}", "email": f"participant_{i}@example.com", "custom_id": f"P-{i:03d}"}
        for i in range(1, 36)
    ]
    payload = {
        "title": "Large Scale Enterprise Workshop",
        "description": "Demonstrating high-throughput bulk certificate generation performance.",
        "issuer_name": "Enterprise Education Board",
        "recipients": recipients,
    }

    resp = client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == status.HTTP_202_ACCEPTED
    job_id = resp.json()["job_id"]
    assert resp.json()["total_recipients"] == 35

    job_status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job_status["status"] == "COMPLETED"
    assert job_status["success_count"] == 35
    assert job_status["failed_count"] == 0
    assert job_status["progress_percentage"] == 100.0

    # Bulk zip should contain all 35
    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_resp.status_code == status.HTTP_200_OK
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        assert len(zf.namelist()) == 35


def test_download_job_with_all_failed(client):
    payload = {
        "title": "All Failed Event",
        "description": "All fail.",
        "issuer_name": "Issuer",
        "recipients": [
            {"name": "Fail 1", "email": "f1@simulate-failure.com"},
            {"name": "Fail 2", "email": "f2@simulate-failure.com"},
        ],
    }
    resp = client.post("/api/v1/jobs", json=payload)
    job_id = resp.json()["job_id"]

    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "No certificates were successfully generated" in zip_resp.json()["detail"]


def test_list_jobs_filtered_by_status(client):
    resp = client.get("/api/v1/jobs?status=COMPLETED")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert all(j["status"] == "COMPLETED" for j in data)


def test_get_job_certificates_not_found(client):
    resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/certificates")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_download_job_zip_while_processing(db_session, client):
    from app.models import Job, JobStatus
    # Insert job with PROCESSING status
    job = Job(
        title="Processing Job",
        description="Currently running",
        issuer_name="Board",
        issue_date="2026-10-08",
        status=JobStatus.PROCESSING.value,
        total_count=5,
    )
    db_session.add(job)
    db_session.commit()

    resp = client.get(f"/api/v1/jobs/{job.id}/download")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "currently 'PROCESSING'" in resp.json()["detail"]


def test_download_certificate_not_completed_or_missing_file(db_session, client):
    from app.models import Job, Certificate, CertificateStatus
    job = Job(
        title="Sample Job",
        description="Testing cert download errors",
        issuer_name="Board",
        issue_date="2026-10-08",
    )
    db_session.add(job)
    db_session.flush()

    # 1. Cert still PENDING
    cert_pending = Certificate(
        job_id=job.id,
        recipient_name="Pending Recipient",
        recipient_email="pending@example.com",
        certificate_code="CERT-PENDING1",
        status=CertificateStatus.PENDING.value,
    )
    # 2. Cert COMPLETED but file missing on disk
    cert_missing_file = Certificate(
        job_id=job.id,
        recipient_name="Ghost Recipient",
        recipient_email="ghost@example.com",
        certificate_code="CERT-GHOST1",
        status=CertificateStatus.COMPLETED.value,
        file_path="/path/to/nonexistent/file.pdf",
    )
    db_session.add_all([cert_pending, cert_missing_file])
    db_session.commit()

    # Download pending
    resp1 = client.get(f"/api/v1/certificates/{cert_pending.id}/download")
    assert resp1.status_code == status.HTTP_400_BAD_REQUEST
    assert "not ready for download" in resp1.json()["detail"]

    # Download completed but missing file
    resp2 = client.get(f"/api/v1/certificates/{cert_missing_file.id}/download")
    assert resp2.status_code == status.HTTP_404_NOT_FOUND
    assert "not found on disk" in resp2.json()["detail"]


def test_direct_get_db_generator():
    from app.database import get_db
    gen = get_db()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass


