import os
from pathlib import Path
from app.services.generator import CertificateGenerator


def test_generate_valid_certificate(tmp_path):
    output_pdf = tmp_path / "valid_cert.pdf"

    size = CertificateGenerator.generate(
        recipient_name="Alice Smith",
        title="Python Software Architecture Masterclass",
        description="For demonstrating outstanding proficiency in distributed systems and asynchronous programming.",
        issuer_name="Dr. Martin Fowler",
        issuer_title="Chief Architect",
        issue_date="October 08, 2026",
        certificate_code="CERT-ALICE123",
        output_file_path=str(output_pdf),
    )

    assert output_pdf.exists()
    assert size > 1000
    assert output_pdf.stat().st_size == size

    # Verify PDF magic header
    with open(output_pdf, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


def test_generate_with_long_name(tmp_path):
    output_pdf = tmp_path / "long_name_cert.pdf"
    long_name = "Professor Dr. Bartholomew Bartholomew-Montgomery III of Cambridge"

    size = CertificateGenerator.generate(
        recipient_name=long_name,
        title="Advanced Distributed Algorithms",
        description="Exceptional performance and contributions.",
        issuer_name="Dean of Faculty",
        issuer_title="Dean",
        issue_date="October 08, 2026",
        certificate_code="CERT-LONGNAME1",
        output_file_path=str(output_pdf),
    )

    assert output_pdf.exists()
    assert size > 1000


def test_generate_with_medium_name(tmp_path):
    output_pdf = tmp_path / "medium_name_cert.pdf"
    # Exactly 28 characters
    medium_name = "Alexander Hamilton-Washington"

    size = CertificateGenerator.generate(
        recipient_name=medium_name,
        title="Advanced Architecture",
        description="Exceptional performance.",
        issuer_name="Dean",
        issuer_title="Dean",
        issue_date="October 08, 2026",
        certificate_code="CERT-MEDNAME1",
        output_file_path=str(output_pdf),
    )

    assert output_pdf.exists()
    assert size > 1000



def test_generate_with_multiline_description(tmp_path):
    output_pdf = tmp_path / "multiline_cert.pdf"
    long_desc = (
        "In recognition of outstanding dedication, relentless effort, and exemplary execution "
        "throughout the comprehensive eight-week intensive workshop covering backend web frameworks, "
        "database scaling techniques, asynchronous worker pipelines, and automated test-driven development."
    )

    size = CertificateGenerator.generate(
        recipient_name="Bob Jones",
        title="Backend Engineering Intensive",
        description=long_desc,
        issuer_name="Elena Rostova",
        issuer_title="VP of Engineering",
        issue_date="October 08, 2026",
        certificate_code="CERT-BOB456",
        output_file_path=str(output_pdf),
    )

    assert output_pdf.exists()
    assert size > 1000


def test_generate_creates_nested_directories(tmp_path):
    nested_pdf = tmp_path / "deeply" / "nested" / "path" / "cert.pdf"

    CertificateGenerator.generate(
        recipient_name="Charlie Brown",
        title="Design Patterns",
        description="Completed course successfully.",
        issuer_name="Instructor",
        issuer_title="Senior Instructor",
        issue_date="October 08, 2026",
        certificate_code="CERT-CHARLIE789",
        output_file_path=str(nested_pdf),
    )

    assert nested_pdf.exists()
