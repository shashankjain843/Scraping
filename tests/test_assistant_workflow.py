import pytest
from backend.services.email_extractor import extract_emails_from_text

def test_regex_email_extractor():
    sample_text = (
        "We are hiring a Data Analyst in Jaipur! Please send your resume to hr@company.com "
        "or contact careers.india@techcorp.co.in for more info."
    )
    emails = extract_emails_from_text(sample_text)
    assert len(emails) == 2
    assert "hr@company.com" in emails
    assert "careers.india@techcorp.co.in" in emails

def test_no_email_extracted():
    sample_text = "Apply via our official company portal link. No direct email address provided here."
    emails = extract_emails_from_text(sample_text)
    assert len(emails) == 0
