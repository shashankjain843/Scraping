import re
from typing import List

# Regex pattern as specified: [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}
EMAIL_REGEX = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

def extract_emails_from_text(text: str) -> List[str]:
    """
    Extracts all unique email addresses present in publicly visible text via regex.
    Does NOT guess or look up emails externally.
    """
    if not text:
        return []
    
    matches = EMAIL_REGEX.findall(text)
    # Deduplicate and ignore common invalid extensions if needed
    seen = set()
    valid_emails = []
    for email in matches:
        e_lower = email.lower()
        if e_lower not in seen and not e_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
            seen.add(e_lower)
            valid_emails.append(email)
            
    return valid_emails
