from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict


class RecipientInput(BaseModel):
    """Schema for individual recipient input."""

    name: str = Field(..., min_length=1, max_length=150, description="Full name of recipient")
    email: EmailStr = Field(..., description="Valid email address of recipient")
    custom_id: Optional[str] = Field(None, max_length=100, description="Optional organization / student identifier")

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipient name cannot be blank or whitespace only")
        return stripped


class CertificateJobCreateRequest(BaseModel):
    """Schema for submitting a bulk certificate generation job."""

    title: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Certificate title / event name (e.g. 'Advanced Python Engineering')",
    )
    description: str = Field(
        ...,
        min_length=2,
        max_length=600,
        description="Reason or achievement text displayed on the certificate",
    )
    issuer_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Name of the issuing person or authority",
    )
    issuer_title: Optional[str] = Field(
        default="Authorized Signatory",
        max_length=150,
        description="Official title or organization of the issuer",
    )
    issue_date: Optional[date] = Field(
        default=None,
        description="Date of issuance (YYYY-MM-DD). Defaults to current date if omitted.",
    )
    recipients: List[RecipientInput] = Field(
        ...,
        min_length=1,
        description="List of recipients to generate certificates for",
    )

    @field_validator("title", "description", "issuer_name")
    @classmethod
    def validate_non_blank_strings(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be blank or whitespace only")
        return stripped


class JobCreateResponse(BaseModel):
    """Immediate response after submitting a generation job."""

    job_id: str
    status: str
    message: str
    total_recipients: int
    status_url: str
    created_at: datetime


class CertificateItemResponse(BaseModel):
    """Schema representing an individual recipient certificate."""

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    custom_id: Optional[str] = None
    certificate_code: str
    status: str
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """Full job status, summary metrics, and optional certificate details."""

    id: str
    title: str
    description: str
    issuer_name: str
    issuer_title: Optional[str]
    issue_date: str
    status: str
    total_count: int
    processed_count: int
    success_count: int
    failed_count: int
    progress_percentage: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    certificates_download_url: Optional[str] = None
    certificates: Optional[List[CertificateItemResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class CertificateVerificationResponse(BaseModel):
    """Schema for public verification of a certificate code."""

    certificate_code: str
    recipient_name: str
    title: str
    description: str
    issuer_name: str
    issuer_title: Optional[str]
    issue_date: str
    status: str
    is_valid: bool
    download_url: Optional[str] = None
