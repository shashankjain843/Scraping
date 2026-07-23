import os
import re
from pathlib import Path
from typing import Optional

def extract_name_from_resume(file_path: Optional[str], default_name: str = "") -> str:
    """
    Extracts candidate full name from an uploaded resume file (PDF/DOCX)
    or falls back to user profile default_name.
    """
    if not file_path or not os.path.exists(file_path):
        return default_name or "Applicant"

    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    try:
        if ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            full_text = []
            for p in doc.paragraphs:
                if p.text.strip():
                    full_text.append(p.text.strip())
            text = "\n".join(full_text[:10]) # Look in top 10 lines
        elif ext == ".pdf":
            # Basic text extract from PDF
            with open(file_path, "rb") as f:
                content = f.read().decode("latin1", errors="ignore")
                # Clean PDF string
                text = re.sub(r'[\r\n]+', '\n', content)[:2000]
    except Exception:
        pass

    if text:
        # Search for first non-generic name line
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            # Skip header keywords e.g. "Resume", "Curriculum Vitae"
            if re.search(r'\b(?:resume|cv|curriculum|profile|email|phone|contact)\b', line, re.IGNORECASE):
                continue
            # If line looks like a name (2-4 capitalized words, no numbers/special chars)
            if re.match(r'^[A-Z][a-zA-Z\.\'\-]{1,20}(?:\s+[A-Z][a-zA-Z\.\'\-]{1,20}){1,3}$', line):
                return line

    return default_name or "Applicant"
