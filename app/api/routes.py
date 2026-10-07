import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.schemas import (
    CertificateJobCreateRequest,
    JobCreateResponse,
    JobResponse,
    CertificateItemResponse,
    CertificateVerificationResponse,
)
from app.services.job_service import JobService
from app.services.storage import StorageService

router = APIRouter(prefix="/api/v1", tags=["Certificates"])


def build_job_response(job: Job, request: Request, include_certificates: bool = False) -> JobResponse:
    """Helper to convert Job ORM instance into JobResponse schema with dynamic URLs."""
    base_url = str(request.base_url).rstrip("/")
    progress = (
        round((job.processed_count / job.total_count) * 100.0, 1)
        if job.total_count > 0
        else 0.0
    )

    zip_url = (
        f"{base_url}/api/v1/jobs/{job.id}/download"
        if job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIALLY_COMPLETED.value)
        and job.success_count > 0
        else None
    )

    cert_responses = None
    if include_certificates and job.certificates:
        cert_responses = []
        for c in job.certificates:
            c_download = (
                f"{base_url}/api/v1/certificates/{c.id}/download"
                if c.status == CertificateStatus.COMPLETED.value
                else None
            )
            cert_responses.append(
                CertificateItemResponse(
                    id=c.id,
                    job_id=c.job_id,
                    recipient_name=c.recipient_name,
                    recipient_email=c.recipient_email,
                    custom_id=c.custom_id,
                    certificate_code=c.certificate_code,
                    status=c.status,
                    file_size_bytes=c.file_size_bytes,
                    error_message=c.error_message,
                    download_url=c_download,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )

    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        issuer_name=job.issuer_name,
        issuer_title=job.issuer_title,
        issue_date=job.issue_date,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        progress_percentage=progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        certificates_download_url=zip_url,
        certificates=cert_responses,
    )


# 1. Submit bulk certificate generation job
@router.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit bulk certificate generation job",
    description="Accepts event information and a list of recipients, creates a background processing job, and returns immediately.",
)
def submit_certificate_job(
    payload: CertificateJobCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    job = JobService.create_job(db, payload)

    # Queue background task for non-blocking asynchronous generation
    background_tasks.add_task(JobService.process_job_task, job.id)

    base_url = str(request.base_url).rstrip("/")
    status_url = f"{base_url}/api/v1/jobs/{job.id}"

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        message="Certificate generation job accepted. Generation is processing in the background.",
        total_recipients=job.total_count,
        status_url=status_url,
        created_at=job.created_at,
    )


# 2. List all jobs
@router.get(
    "/jobs",
    response_model=List[JobResponse],
    summary="List certificate generation jobs",
)
def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status_filter:
        query = query.filter(Job.status == status_filter.upper())
    jobs = query.order_by(desc(Job.created_at)).offset(offset).limit(limit).all()
    return [build_job_response(j, request, include_certificates=False) for j in jobs]


# 3. Get single job status and progress
@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Check job status and progress",
    description="Retrieve the real-time status, counts (success/failed/processed), and completion details of a job.",
)
def get_job_status(
    job_id: str,
    include_certificates: bool = Query(False, description="Whether to include recipient certificate items"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )
    return build_job_response(job, request, include_certificates=include_certificates)


# 4. List certificates for a specific job
@router.get(
    "/jobs/{job_id}/certificates",
    response_model=List[CertificateItemResponse],
    summary="List recipients/certificates for a job",
    description="Retrieve individual certificate records and their statuses within a specific job.",
)
def get_job_certificates(
    job_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    request: Request = None,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )

    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status_filter:
        query = query.filter(Certificate.status == status_filter.upper())

    certs = query.order_by(Certificate.created_at).offset(offset).limit(limit).all()
    base_url = str(request.base_url).rstrip("/")

    results = []
    for c in certs:
        download_url = (
            f"{base_url}/api/v1/certificates/{c.id}/download"
            if c.status == CertificateStatus.COMPLETED.value
            else None
        )
        results.append(
            CertificateItemResponse(
                id=c.id,
                job_id=c.job_id,
                recipient_name=c.recipient_name,
                recipient_email=c.recipient_email,
                custom_id=c.custom_id,
                certificate_code=c.certificate_code,
                status=c.status,
                file_size_bytes=c.file_size_bytes,
                error_message=c.error_message,
                download_url=download_url,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return results


# 5. Bulk download ZIP archive of all certificates for a job
@router.get(
    "/jobs/{job_id}/download",
    summary="Bulk download all certificates as ZIP",
    description="Download a ZIP archive containing all successfully generated certificates for this job.",
)
def download_job_certificates_zip(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )

    if job.status in (JobStatus.PENDING.value, JobStatus.PROCESSING.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is currently '{job.status}'. Please wait for completion before downloading.",
        )

    if job.success_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No certificates were successfully generated for this job.",
        )

    zip_path = job.zip_file_path
    if not zip_path or not os.path.exists(zip_path):
        # Regenerate ZIP dynamically if file was missing or removed
        successful_certs = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id, Certificate.status == CertificateStatus.COMPLETED.value)
            .all()
        )
        if not successful_certs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No generated certificates available to package.",
            )
        zip_path = str(StorageService.create_job_zip_archive(job_id, successful_certs))
        job.zip_file_path = zip_path
        db.commit()

    safe_title = StorageService.sanitize_filename(job.title)
    download_filename = f"Certificates_{safe_title}_{job.id[:8]}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=download_filename,
    )


# 6. Get single certificate details
@router.get(
    "/certificates/{certificate_id}",
    response_model=CertificateItemResponse,
    summary="Get single certificate details",
)
def get_certificate_details(
    certificate_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found",
        )

    base_url = str(request.base_url).rstrip("/")
    download_url = (
        f"{base_url}/api/v1/certificates/{cert.id}/download"
        if cert.status == CertificateStatus.COMPLETED.value
        else None
    )

    return CertificateItemResponse(
        id=cert.id,
        job_id=cert.job_id,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        custom_id=cert.custom_id,
        certificate_code=cert.certificate_code,
        status=cert.status,
        file_size_bytes=cert.file_size_bytes,
        error_message=cert.error_message,
        download_url=download_url,
        created_at=cert.created_at,
        updated_at=cert.updated_at,
    )


# 7. Download single certificate PDF
@router.get(
    "/certificates/{certificate_id}/download",
    summary="Download individual certificate PDF",
)
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found",
        )

    if cert.status != CertificateStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate is in '{cert.status}' state and not ready for download. Error: {cert.error_message or 'None'}",
        )

    if not cert.file_path or not os.path.exists(cert.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated certificate file not found on disk.",
        )

    safe_name = StorageService.sanitize_filename(cert.recipient_name)
    download_filename = f"Certificate_{safe_name}_{cert.certificate_code}.pdf"
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=download_filename,
    )


# 8. Public Certificate Verification by unique code
@router.get(
    "/verify/{certificate_code}",
    response_model=CertificateVerificationResponse,
    summary="Verify certificate authenticity by code",
)
def verify_certificate(
    certificate_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert = (
        db.query(Certificate)
        .filter(Certificate.certificate_code == certificate_code.strip().upper())
        .first()
    )
    if not cert or not cert.job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No valid certificate found with code '{certificate_code}'",
        )

    base_url = str(request.base_url).rstrip("/")
    download_url = (
        f"{base_url}/api/v1/certificates/{cert.id}/download"
        if cert.status == CertificateStatus.COMPLETED.value
        else None
    )

    return CertificateVerificationResponse(
        certificate_code=cert.certificate_code,
        recipient_name=cert.recipient_name,
        title=cert.job.title,
        description=cert.job.description,
        issuer_name=cert.job.issuer_name,
        issuer_title=cert.job.issuer_title,
        issue_date=cert.job.issue_date,
        status=cert.status,
        is_valid=(cert.status == CertificateStatus.COMPLETED.value),
        download_url=download_url,
    )


# 9. Healthcheck endpoint
@router.get("/health", summary="Health check endpoint")
def health_check(db: Session = Depends(get_db)):
    # Test DB connectivity
    db.execute(Job.__table__.select().limit(1))
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": os.environ.get("TIMESTAMP", "")
    }
