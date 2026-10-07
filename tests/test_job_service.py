import zipfile
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.schemas import CertificateJobCreateRequest, RecipientInput
from app.services.job_service import JobService


def test_create_job(db_session):
    request = CertificateJobCreateRequest(
        title="Microservices in Python",
        description="Completed comprehensive microservices course.",
        issuer_name="Jane Doe",
        issuer_title="Head of Curriculum",
        recipients=[
            RecipientInput(name="Alice Smith", email="alice@example.com", custom_id="ID-101"),
            RecipientInput(name="Bob Jones", email="bob@example.com", custom_id="ID-102"),
        ],
    )

    job = JobService.create_job(db_session, request)

    assert job.id is not None
    assert job.title == "Microservices in Python"
    assert job.status == JobStatus.PENDING.value
    assert job.total_count == 2
    assert job.processed_count == 0
    assert job.success_count == 0
    assert job.failed_count == 0

    certs = db_session.query(Certificate).filter(Certificate.job_id == job.id).all()
    assert len(certs) == 2
    assert certs[0].recipient_name == "Alice Smith"
    assert certs[0].certificate_code.startswith("CERT-")
    assert certs[0].status == CertificateStatus.PENDING.value


def test_process_job_all_success(db_session):
    request = CertificateJobCreateRequest(
        title="Data Science Bootcamp",
        description="Successfully analyzed and built ML pipelines.",
        issuer_name="Dr. Andrew",
        recipients=[
            RecipientInput(name="Dev 1", email="dev1@example.com"),
            RecipientInput(name="Dev 2", email="dev2@example.com"),
            RecipientInput(name="Dev 3", email="dev3@example.com"),
        ],
    )

    job = JobService.create_job(db_session, request)
    job_id = job.id

    # Run processing
    JobService.process_job_task(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()
    assert updated_job.status == JobStatus.COMPLETED.value
    assert updated_job.total_count == 3
    assert updated_job.processed_count == 3
    assert updated_job.success_count == 3
    assert updated_job.failed_count == 0
    assert updated_job.completed_at is not None
    assert updated_job.zip_file_path is not None

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    for c in certs:
        assert c.status == CertificateStatus.COMPLETED.value
        assert c.file_path is not None
        assert c.file_size_bytes > 0
        assert c.error_message is None

    # Verify ZIP contents
    with zipfile.ZipFile(updated_job.zip_file_path, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 3


def test_process_job_failure_isolation(db_session):
    """A failure in one certificate generation must NOT prevent others from succeeding."""
    request = CertificateJobCreateRequest(
        title="Web Security Essentials",
        description="Understanding application penetration testing and secure code design.",
        issuer_name="Chief CISO",
        recipients=[
            RecipientInput(name="Good User 1", email="good1@example.com"),
            RecipientInput(name="Faulty Recipient", email="faulty@simulate-failure.com"),  # triggers failure
            RecipientInput(name="Good User 2", email="good2@example.com"),
        ],
    )

    job = JobService.create_job(db_session, request)
    job_id = job.id

    JobService.process_job_task(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()
    assert updated_job.status == JobStatus.PARTIALLY_COMPLETED.value
    assert updated_job.total_count == 3
    assert updated_job.processed_count == 3
    assert updated_job.success_count == 2
    assert updated_job.failed_count == 1

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).order_by(Certificate.recipient_name).all()
    faulty_cert = next(c for c in certs if c.recipient_email == "faulty@simulate-failure.com")
    assert faulty_cert.status == CertificateStatus.FAILED.value
    assert "Simulated generation failure" in faulty_cert.error_message
    assert faulty_cert.file_path is None

    good_certs = [c for c in certs if c.recipient_email != "faulty@simulate-failure.com"]
    assert len(good_certs) == 2
    for c in good_certs:
        assert c.status == CertificateStatus.COMPLETED.value
        assert c.file_path is not None
        assert c.file_size_bytes > 0

    # The ZIP should still package the 2 successful certificates
    assert updated_job.zip_file_path is not None
    with zipfile.ZipFile(updated_job.zip_file_path, "r") as zf:
        assert len(zf.namelist()) == 2


def test_process_job_all_failed(db_session):
    request = CertificateJobCreateRequest(
        title="Failure Simulation",
        description="All items are designed to fail.",
        issuer_name="Tester",
        recipients=[
            RecipientInput(name="User 1", email="user1@simulate-failure.com"),
            RecipientInput(name="User 2", email="user2@simulate-failure.com"),
        ],
    )

    job = JobService.create_job(db_session, request)
    job_id = job.id

    JobService.process_job_task(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()
    assert updated_job.status == JobStatus.FAILED.value
    assert updated_job.total_count == 2
    assert updated_job.processed_count == 2
    assert updated_job.success_count == 0
    assert updated_job.failed_count == 2
    assert updated_job.zip_file_path is None
