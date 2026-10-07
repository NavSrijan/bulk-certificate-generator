#!/usr/bin/env python3
"""
Interactive demonstration script for the Bulk Certificate Generator API.
This script demonstrates the complete lifecycle:
1. Submitting a bulk generation job
2. Polling progress asynchronously
3. Downloading an individual certificate PDF
4. Downloading the consolidated ZIP archive
5. Verifying a certificate via the public verification endpoint
"""

import sys
import time
import httpx

BASE_URL = "http://127.0.0.1:8000"


def run_demo():
    print("=" * 70)
    print("🎓 BULK CERTIFICATE GENERATOR - END-TO-END DEMO")
    print("=" * 70)

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Health check
        try:
            health = client.get("/api/v1/health")
            if health.status_code != 200:
                print(f"❌ Server returned non-200 on /health: {health.status_code}")
                sys.exit(1)
            print("✅ Server is UP and healthy!")
        except Exception as e:
            print(f"❌ Could not connect to {BASE_URL}. Is the server running?")
            print(f"   Start it using: uvicorn app.main:app --reload")
            print(f"   Error: {e}")
            sys.exit(1)

        # 2. Submit Bulk Job
        payload = {
            "title": "Full-Stack Distributed Systems Engineering",
            "description": "For demonstrated excellence in architecting resilient backend systems, asynchronous pipelines, and fault-tolerant APIs.",
            "issuer_name": "Dr. Grace Hopper",
            "issuer_title": "Dean of Computer Science",
            "issue_date": "2026-10-08",
            "recipients": [
                {"name": "Alice Johnson", "email": "alice.johnson@example.com", "custom_id": "STUDENT-101"},
                {"name": "Bob Smith", "email": "bob.smith@example.com", "custom_id": "STUDENT-102"},
                {"name": "Charlie Chaplin", "email": "charlie@simulate-failure.com", "custom_id": "STUDENT-103"},  # Simulated failure
                {"name": "Diana Prince", "email": "diana.prince@example.com", "custom_id": "STUDENT-104"},
                {"name": "Edward Norton", "email": "edward.norton@example.com", "custom_id": "STUDENT-105"},
            ],
        }

        print("\n[Step 1] Submitting Bulk Generation Request...")
        print(f"  • Event Title: {payload['title']}")
        print(f"  • Issuer: {payload['issuer_name']} ({payload['issuer_title']})")
        print(f"  • Total Recipients: {len(payload['recipients'])}")

        post_res = client.post("/api/v1/jobs", json=payload)
        if post_res.status_code != 202:
            print(f"❌ Job submission failed: {post_res.status_code} {post_res.text}")
            sys.exit(1)

        job_info = post_res.json()
        job_id = job_info["job_id"]
        print(f"  ✓ Job Accepted! ID: {job_id}")
        print(f"  ✓ Status URL: {job_info['status_url']}")

        # 3. Poll for Completion
        print("\n[Step 2] Polling Job Progress...")
        while True:
            poll_res = client.get(f"/api/v1/jobs/{job_id}?include_certificates=true")
            data = poll_res.json()
            status = data["status"]
            processed = data["processed_count"]
            total = data["total_count"]
            pct = data["progress_percentage"]

            print(f"  ⏳ Status: {status:<18} | Processed: {processed}/{total} ({pct:.0f}%) | Success: {data['success_count']} | Failed: {data['failed_count']}")

            if status in ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED"):
                break
            time.sleep(0.5)

        print("\n[Step 3] Generation Results:")
        print(f"  • Final Status: {data['status']}")
        print(f"  • Successful: {data['success_count']}")
        print(f"  • Failed: {data['failed_count']}")

        # 4. Inspect Individual Certificates
        first_success_cert = None
        for c in data["certificates"]:
            state_icon = "✅" if c["status"] == "COMPLETED" else "❌"
            err = f" (Error: {c['error_message']})" if c["error_message"] else ""
            print(f"    {state_icon} {c['recipient_name']:<18} [{c['certificate_code']}] -> {c['status']}{err}")
            if c["status"] == "COMPLETED" and not first_success_cert:
                first_success_cert = c

        # 5. Download Sample Certificate PDF
        if first_success_cert:
            print(f"\n[Step 4] Downloading Sample PDF for {first_success_cert['recipient_name']}...")
            cert_dl = client.get(f"/api/v1/certificates/{first_success_cert['id']}/download")
            if cert_dl.status_code == 200:
                sample_path = f"sample_cert_{first_success_cert['id'][:8]}.pdf"
                with open(sample_path, "wb") as f:
                    f.write(cert_dl.content)
                print(f"  ✓ Downloaded: {sample_path} ({len(cert_dl.content)} bytes)")
            else:
                print(f"  ❌ Download failed: {cert_dl.status_code}")

        # 6. Bulk Download ZIP Archive
        if data["certificates_download_url"]:
            print("\n[Step 5] Downloading Bulk ZIP Archive...")
            zip_dl = client.get(f"/api/v1/jobs/{job_id}/download")
            if zip_dl.status_code == 200:
                zip_filename = f"sample_certificates_{job_id[:8]}.zip"
                with open(zip_filename, "wb") as f:
                    f.write(zip_dl.content)
                print(f"  ✓ Downloaded ZIP: {zip_filename} ({len(zip_dl.content)} bytes)")
            else:
                print(f"  ❌ ZIP download failed: {zip_dl.status_code}")

        # 7. Public Certificate Verification
        if first_success_cert:
            code = first_success_cert["certificate_code"]
            print(f"\n[Step 6] Public Verification Lookup for Code '{code}'...")
            ver_res = client.get(f"/api/v1/verify/{code}")
            if ver_res.status_code == 200:
                vdata = ver_res.json()
                print(f"  ✓ Verification Result:")
                print(f"    - Code:        {vdata['certificate_code']}")
                print(f"    - Recipient:   {vdata['recipient_name']}")
                print(f"    - Event/Title: {vdata['title']}")
                print(f"    - Issuer:      {vdata['issuer_name']} ({vdata['issuer_title']})")
                print(f"    - Issue Date:  {vdata['issue_date']}")
                print(f"    - Valid:       {vdata['is_valid']}")
            else:
                print(f"  ❌ Verification failed: {ver_res.status_code}")

    print("\n" + "=" * 70)
    print("🎉 DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
