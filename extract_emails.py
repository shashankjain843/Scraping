import os
import re
import sys
import pandas as pd

# =====================================================================
# CONFIGURATION SETTINGS (EASILY CONFIGURABLE)
# =====================================================================
INPUT_FILE = "linkedin_fresher_data_analyst_jobs_merged.csv"  # Supports .csv or .json
OUTPUT_FILE = "extracted_emails.csv"
TEXT_COLUMN_NAME = "Required Skills"       # Column containing full description/text
LINK_COLUMN_NAME = "Job Posting Link / URL" # Reference column for job link
LOG_FILE = "extraction_log.txt"

# Keywords for prioritizing emails (proximity-based ranking)
KEYWORDS = [
    "apply", "contact", "send resume to", "email us at", 
    "reach out to", "send cv to", "email", "recruiter", 
    "cv", "resume", "hr", "careers", "jobs", "hiring"
]

# Generic/placeholder/fake emails to ignore
PLACEHOLDER_PATTERNS = [
    "example.com", "noreply", "no-reply", "test@", 
    "yourname@", "domain.com", "support@", "privacy@", 
    "info@", "admin@", "placeholder"
]

# Regex pattern for standard emails
EMAIL_REGEX = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
# =====================================================================


def extract_best_email(text):
    """
    Extracts the best email from the given text.
    If multiple emails are found, it ranks them by proximity to context keywords.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    # Find all emails
    emails = re.findall(EMAIL_REGEX, text)
    if not emails:
        return None

    # Filter out placeholders
    valid_emails = []
    for email in emails:
        email_lower = email.lower()
        is_placeholder = False
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in email_lower:
                is_placeholder = True
                break
        if not is_placeholder:
            # Avoid exact duplicate matches within the same text block
            if email not in valid_emails:
                valid_emails.append(email)

    if not valid_emails:
        return None
    if len(valid_emails) == 1:
        return valid_emails[0]

    # Rank multiple emails by proximity to context keywords
    best_email = valid_emails[0]
    best_score = -1
    text_lower = text.lower()

    for email in valid_emails:
        email_pos = text_lower.find(email.lower())
        if email_pos == -1:
            continue

        score = 0
        for keyword in KEYWORDS:
            keyword_lower = keyword.lower()
            start = 0
            while True:
                pos = text_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                distance = abs(email_pos - pos)
                if distance < 150:  # 150-character window
                    # Closer keywords yield a higher score
                    score += (150 - distance)
                start = pos + len(keyword_lower)

        if score > best_score:
            best_score = score
            best_email = email

    return best_email


def main():
    print("=" * 60)
    print("LINKEDIN EMAIL EXTRACTION UTILITY")
    print("=" * 60)

    # 1. File Validation
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] Input file '{INPUT_FILE}' not found! Please check the path.")
        sys.exit(1)

    print(f"[INFO] Loading input file: {INPUT_FILE}...")
    try:
        if INPUT_FILE.endswith(".csv"):
            df = pd.read_csv(INPUT_FILE)
        elif INPUT_FILE.endswith(".json"):
            df = pd.read_json(INPUT_FILE)
        else:
            print("[ERROR] Unsupported file format! Please use a .csv or .json file.")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to read input file: {e}")
        sys.exit(1)

    # 2. Column Validation
    if TEXT_COLUMN_NAME not in df.columns:
        print(f"[ERROR] Required text column '{TEXT_COLUMN_NAME}' not found in the file.")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    has_link_col = LINK_COLUMN_NAME in df.columns
    if not has_link_col:
        print(f"[WARNING] Link column '{LINK_COLUMN_NAME}' not found. Link data will be empty.")

    # 3. Processing Loops
    total_jobs = len(df)
    print(f"[INFO] Scanned {total_jobs} rows. Processing extraction...")

    results = []
    seen_emails = set()
    
    unique_count = 0
    duplicate_count = 0
    skipped_count = 0

    log_entries = []
    log_entries.append(f"--- Extraction Run Started: {pd.Timestamp.now()} ---")
    log_entries.append(f"Input File: {INPUT_FILE} ({total_jobs} rows)")
    log_entries.append(f"Target Column: {TEXT_COLUMN_NAME}\n")

    for index, row in df.iterrows():
        try:
            job_link = row[LINK_COLUMN_NAME] if has_link_col else "Not Available"
            if pd.isna(job_link):
                job_link = "Not Available"
                
            text_content = row[TEXT_COLUMN_NAME]
            if pd.isna(text_content):
                text_content = ""

            # Extract email
            email = extract_best_email(text_content)

            if email:
                email_clean = email.strip()
                if email_clean.lower() in seen_emails:
                    status = "EMAIL_FOUND_DUPLICATE"
                    duplicate_count += 1
                    reason = f"Duplicate of previously extracted email: {email_clean}"
                else:
                    status = "EMAIL_FOUND"
                    seen_emails.add(email_clean.lower())
                    unique_count += 1
                    reason = "Successfully extracted new email"
                
                results.append({
                    "job_link": job_link,
                    "extracted_email": email_clean,
                    "status": status,
                    "original_text": text_content
                })
            else:
                status = "SKIPPED_NO_EMAIL"
                skipped_count += 1
                reason = "No valid email addresses found in text"
                
                results.append({
                    "job_link": job_link,
                    "extracted_email": "",
                    "status": status,
                    "original_text": text_content
                })

            log_entries.append(f"Row {index + 1}: Status={status} | Email={email or 'None'} | Link={job_link} | {reason}")

        except Exception as row_err:
            status = "SKIPPED_ERROR"
            skipped_count += 1
            results.append({
                "job_link": "Error",
                "extracted_email": "",
                "status": status,
                "original_text": str(row)
            })
            log_entries.append(f"Row {index + 1}: Status={status} | Error processing row: {row_err}")

    # 4. Save Outputs
    output_df = pd.DataFrame(results)
    
    # Sort output so that EMAIL_FOUND (new unique emails) are at the top, 
    # followed by EMAIL_FOUND_DUPLICATE, and then SKIPPED_NO_EMAIL.
    status_priority = {
        "EMAIL_FOUND": 1,
        "EMAIL_FOUND_DUPLICATE": 2,
        "SKIPPED_NO_EMAIL": 3,
        "SKIPPED_ERROR": 4
    }
    output_df["priority"] = output_df["status"].map(status_priority)
    output_df = output_df.sort_values(by="priority").drop(columns=["priority"])

    print(f"[INFO] Writing results to: {OUTPUT_FILE}...")
    try:
        if OUTPUT_FILE.endswith(".csv"):
            output_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        elif OUTPUT_FILE.endswith(".json"):
            # Convert back to clean json records
            output_df.to_json(OUTPUT_FILE, orient="records", indent=4, force_ascii=False)
        else:
            # Fallback to CSV
            output_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"[SUCCESS] Saved results to: {OUTPUT_FILE}")
    except Exception as save_err:
        print(f"[ERROR] Failed to save output file: {save_err}")

    # 5. Write Logs
    summary_text = (
        f"\n============================================================\n"
        f"RUN SUMMARY:\n"
        f"Total jobs scanned: {total_jobs}\n"
        f"Unique valid emails found: {unique_count}\n"
        f"Duplicate emails skipped: {duplicate_count}\n"
        f"Skipped (no email): {skipped_count}\n"
        f"============================================================\n"
    )
    print(summary_text)
    
    log_entries.append(summary_text)
    log_entries.append(f"--- Extraction Run Completed: {pd.Timestamp.now()} ---")
    
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as lf:
            lf.write("\n".join(log_entries))
        print(f"[INFO] Detailed logs written to: {LOG_FILE}")
    except Exception as log_err:
        print(f"[WARNING] Failed to write log file: {log_err}")


if __name__ == "__main__":
    main()
