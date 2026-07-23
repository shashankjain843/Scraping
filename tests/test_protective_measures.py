import pytest
from backend.services.job_parser import parse_role_category
from backend.services.resume_parser import extract_name_from_resume
from backend.services.email_service import check_spam_trigger_words

def test_strict_role_matching():
    assert parse_role_category("Junior Data Analyst") == "data_analyst"
    assert parse_role_category("Senior Data Scientist") == "data_scientist"
    assert parse_role_category("Full Stack Developer") == "unmatched"

def test_spam_trigger_words():
    assert check_spam_trigger_words("URGENT OFFER", "Body text") is not None
    assert check_spam_trigger_words("Normal Application", "Body text") is None

def test_resume_name_fallback():
    assert extract_name_from_resume(None, default_name="Shashank Jain") == "Shashank Jain"
