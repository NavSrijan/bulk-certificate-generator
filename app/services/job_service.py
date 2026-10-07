import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.schemas import CertificateJobCreateRequest
from app.services.generator import CertificateGenerator
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobService:
    """Orchestrates job lifecycle, certificate creation, and background generation."""

    @staticmethod
    def generate_unique_certificate_code() -> str:
        """Generate a random 10-character unique alphanumeric certificate code."""
        random_hex = uuid.uuid4().hex[:8].upper()
        return f"CERT-{random_hex}"

    @classmethod
    def create_job(cls, db: Session, request: CertificateJobCreateRequest) -> Job:
        """Create a new Job and its constituent Certificate entries in PENDING state."""
        issue_date_str = (
            request.issue_date.strftime("%B %d, %Y")
            if request.issue_date
            else date.today().strftime("%B %d, %Y")
        )

        job = Job(
            title=request.title,
            description=request.description,
            issuer_name=request.issuer_name,
            issuer_title=request.issuer_title,
            issue_date=issue_date_str,
            status=JobStatus.PENDING.value,
            total_count=len(request.recipients),
            processed_count=0,
            success_count=0,
            failed_count=0,
        )
        db.add(job)
        db.flush()  # Populates job.id

        for item in request.recipients:
            cert_code = cls.generate_unique_certificate_code()
            cert = Certificate(
                job_id=job.id,
                recipient_name=item.name,
                recipient_email=str(item.email),
                custom_id=item.custom_id,
                certificate_code=cert_code,
                status=CertificateStatus.PENDING.value,
            )
            db.add(cert)

        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def process_job_task(cls, job_id: str) -> None:
        """
        Background worker executing certificate generation.
        Isolated per-item execution ensures one recipient failure does not affect others.
        """
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found for background execution.")
                return

            job.status = JobStatus.PROCESSING.value
            job.updated_at = utc_now()
            db.commit()

            certificates: List[Certificate] = (
                db.query(Certificate).filter(Certificate.job_id == job_id).all()
            )

            successful_certs = []

            for cert in certificates:
                cert.status = CertificateStatus.PROCESSING.value
                db.commit()

                try:
                    # Failure simulation hooks for testing failure isolation
                    if (
                        cert.recipient_email.endswith("@simulate-failure.com")
                        or cert.recipient_email.endswith("@fail.invalid")
                        or cert.recipient_name.startswith("FORCE_FAIL")
                    ):
                        raise ValueError(f"Simulated generation failure for recipient {cert.recipient_name}")

                    # Generate PDF certificate
                    out_path = StorageService.get_certificate_path(
                        job_id=job.id,
                        certificate_id=cert.id,
                        recipient_name=cert.recipient_name,
                    )

                    file_size = CertificateGenerator.generate(
                        recipient_name=cert.recipient_name,
                        title=job.title,
                        description=job.description,
                        issuer_name=job.issuer_name,
                        issuer_title=job.issuer_title,
                        issue_date=job.issue_date,
                        certificate_code=cert.certificate_code,
                        output_file_path=str(out_path),
                    )

                    cert.file_path = str(out_path)
                    cert.file_size_bytes = file_size
                    cert.status = CertificateStatus.COMPLETED.value
                    cert.error_message = None
                    job.success_count += 1
                    successful_certs.append(cert)

                except Exception as exc:
                    logger.warning(
                        f"Failed to generate certificate for {cert.recipient_name} ({cert.id}): {exc}"
                    )
                    cert.status = CertificateStatus.FAILED.value
                    cert.error_message = str(exc)
                    job.failed_count += 1

                finally:
                    job.processed_count += 1
                    job.updated_at = utc_now()
                    db.commit()

            # Determine final job status
            if job.failed_count == 0:
                job.status = JobStatus.COMPLETED.value
            elif job.success_count > 0:
                job.status = JobStatus.PARTIALLY_COMPLETED.value
            else:
                job.status = JobStatus.FAILED.value

            job.completed_at = utc_now()
            job.updated_at = utc_now()

            # Create bulk ZIP archive if any certificates succeeded
            if successful_certs:
                try:
                    zip_path = StorageService.create_job_zip_archive(job_id, successful_certs)
                    job.zip_file_path = str(zip_path)
                except Exception as zip_exc:
                    logger.error(f"Failed to create ZIP archive for job {job_id}: {zip_exc}")

            db.commit()

        except Exception as e:
            logger.exception(f"Fatal error while processing job {job_id}: {e}")
            try:
                if job:
                    job.status = JobStatus.FAILED.value
                    job.completed_at = utc_now()
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

