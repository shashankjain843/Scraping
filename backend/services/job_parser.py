import re
from typing import Tuple, Optional, Set

TARGET_CITIES = {
    "jaipur": "Jaipur",
    "noida": "Noida",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "ahmedabad": "Ahmedabad",
}

def parse_experience(title: str, description: str) -> Tuple[bool, bool]:
    """
    Parses experience level from title and description text.
    Returns (bucket_0_1, bucket_1_3).
    
    Bucket A (0-1 years): matches 0-1, fresher, entry level, 0 years, junior/intern.
    Bucket B (1-3 years): matches 1-3, 1-2, 2-3, 0-2 years (includes 1-2 years).
    """
    text = f"{title} {description}".lower()
    
    bucket_0_1 = False
    bucket_1_3 = False
    
    # Explicit freshers / entry level terms
    fresher_terms = [
        r"\bfresher\b", r"\bfreshers\b", r"\bentry[- ]level\b",
        r"\bgraduate trainee\b", r"\btrainee\b", r"\b0[- ]yr\b",
        r"\b0[- ]years?\b", r"\b0 to 1\b", r"\b0[- ]1\b"
    ]
    if any(re.search(term, text) for term in fresher_terms):
        bucket_0_1 = True

    # Search for numeric ranges e.g. "0-2 years", "1-3 years", "1 to 2 yrs"
    range_match = re.search(r'(\d+)\s*(?:to|-|\+)\s*(\d+)\s*(?:years?|yrs?|yr)', text)
    if range_match:
        min_exp = int(range_match.group(1))
        max_exp = int(range_match.group(2))
        
        if min_exp == 0 and max_exp <= 1:
            bucket_0_1 = True
        elif min_exp <= 1 and max_exp >= 2:
            bucket_0_1 = True
            bucket_1_3 = True
        elif min_exp >= 1 and min_exp <= 3:
            bucket_1_3 = True

    # Search for single number mentions e.g. "1 year experience", "2 yrs exp"
    if not (bucket_0_1 or bucket_1_3):
        single_match = re.finditer(r'\b([0-3])\s*(?:years?|yrs?|yr)\b', text)
        for m in single_match:
            val = int(m.group(1))
            if val in (0, 1):
                bucket_0_1 = True
            if val in (2, 3):
                bucket_1_3 = True

    # Default fallback: if title specifically mentions "Junior", "Jr", "Intern", "Associate", "Trainee"
    if not (bucket_0_1 or bucket_1_3):
        if re.search(r'\b(?:junior|jr|intern|associate|trainee)\b', text):
            bucket_0_1 = True
        else:
            # Default for unmentioned experience: mark for both buckets
            bucket_0_1 = True
            bucket_1_3 = True

    return bucket_0_1, bucket_1_3



def parse_city(location_display: str) -> Optional[str]:
    """
    Parses and maps Adzuna location display name to canonical city name.
    Returns canonical city string or None if not matching target cities.
    Target cities: Jaipur, Noida, Gurgaon, Delhi, Pune, Hyderabad, Bangalore, Ahmedabad.
    """
    if not location_display:
        return None
        
    loc_lower = location_display.lower()
    
    for key, canonical in TARGET_CITIES.items():
        # Match whole word pattern or substring
        if re.search(r'\b' + re.escape(key) + r'\b', loc_lower):
            return canonical
            
    return None


def parse_role_category(title: str, description: str = "") -> Optional[str]:
    """
    Classifies job strictly into 'data_analyst' or 'data_scientist'.
    Returns 'data_analyst', 'data_scientist', or 'unmatched' if neither matches clearly.
    """
    title_lower = title.lower()
    
    # 1. Check Data Scientist keywords in Title
    ds_keywords = [
        r"\bdata scientist\b", r"\bdata science\b", r"\bjr data scientist\b",
        r"\bjunior data scientist\b", r"\bmachine learning engineer\b", r"\bml engineer\b"
    ]
    is_ds_title = any(re.search(kw, title_lower) for kw in ds_keywords)
    
    # 2. Check Data Analyst keywords in Title
    da_keywords = [
        r"\bdata analyst\b", r"\bdata analytics\b", r"\bjr data analyst\b",
        r"\bjunior data analyst\b", r"\bbusiness intelligence analyst\b", r"\bbi analyst\b"
    ]
    is_da_title = any(re.search(kw, title_lower) for kw in da_keywords)
    
    if is_ds_title and not is_da_title:
        return "data_scientist"
    if is_da_title and not is_ds_title:
        return "data_analyst"
    if is_ds_title and is_da_title:
        if "scientist" in title_lower:
            return "data_scientist"
        return "data_analyst"

    # 3. Description fallback
    desc_lower = description.lower()
    is_ds_desc = "data scientist" in desc_lower or "machine learning" in desc_lower
    is_da_desc = "data analyst" in desc_lower or "sql" in desc_lower or "tableau" in desc_lower

    if is_ds_desc and not is_da_desc:
        return "data_scientist"
    if is_da_desc and not is_ds_desc:
        return "data_analyst"

    # If match is uncertain (neither role keyword found), flag as unmatched
    return "unmatched"

