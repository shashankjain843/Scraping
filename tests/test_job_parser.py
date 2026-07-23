import pytest
from backend.services.job_parser import parse_experience, parse_city, parse_role_category

def test_parse_experience_bucket_a():
    # 0-1 years tests
    b0_1, b1_3 = parse_experience("Junior Data Analyst", "Looking for 0-1 years of experience in SQL and Python.")
    assert b0_1 is True
    assert b1_3 is False

    b0_1, b1_3 = parse_experience("Fresher Data Scientist", "Entry level position for fresh graduates.")
    assert b0_1 is True

def test_parse_experience_bucket_b_and_overlap():
    # 1-3 years tests (including 1-2 years)
    b0_1, b1_3 = parse_experience("Data Analyst", "Requires 1-2 years of experience with Power BI.")
    assert b1_3 is True
    assert b0_1 is True # 1 year overlaps 0-1 and 1-3

    b0_1, b1_3 = parse_experience("Data Scientist", "2-3 years exp required in Machine Learning.")
    assert b1_3 is True
    assert b0_1 is False

    b0_1, b1_3 = parse_experience("Data Analyst", "Looking for 1-3 years experience.")
    assert b1_3 is True

def test_parse_city_mapping():
    assert parse_city("Gurgaon, Haryana") == "Gurgaon"
    assert parse_city("Gurugram") == "Gurgaon"
    assert parse_city("Bengaluru, Karnataka") == "Bangalore"
    assert parse_city("Bangalore City") == "Bangalore"
    assert parse_city("New Delhi, Delhi") == "Delhi"
    assert parse_city("Noida, Uttar Pradesh") == "Noida"
    assert parse_city("Pune, Maharashtra") == "Pune"
    assert parse_city("Hyderabad, Telangana") == "Hyderabad"
    assert parse_city("Jaipur, Rajasthan") == "Jaipur"
    assert parse_city("Ahmedabad, Gujarat") == "Ahmedabad"
    assert parse_city("Mumbai, Maharashtra") is None # Not in allowed list

def test_parse_role_category():
    assert parse_role_category("Jr Data Analyst", "SQL, Excel") == "data_analyst"
    assert parse_role_category("Data Analytics Associate", "Tableau, Python") == "data_analyst"
    assert parse_role_category("Data Scientist - Entry Level", "Python, Scikit-Learn") == "data_scientist"
    assert parse_role_category("Machine Learning Engineer", "PyTorch, Deep Learning") == "data_scientist"
