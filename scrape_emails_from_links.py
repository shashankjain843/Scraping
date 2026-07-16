import os
import csv
import json
import time
import sys
import random
import re
import pandas as pd
from playwright.sync_api import sync_playwright

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeError in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# =====================================================================
# CONFIGURATION SETTINGS (EASILY CONFIGURABLE)
# =====================================================================
INPUT_FILE = "linkedin_fresher_data_analyst_jobs_merged.csv"  # Supports .csv or .json
OUTPUT_FILE = "extracted_emails_final.csv"
LINK_COLUMN_NAME = "Job Posting Link / URL"
COOKIE_FILE = "www.linkedin.com_cookies.json"
HEADLESS = True  # Set to True if you want browser to run hidden, False is safer

# Rate limiting delays
MIN_DELAY = 8
MAX_DELAY = 15
LONG_PAUSE_EVERY_N_JOBS = 15
LONG_PAUSE_MIN = 60
LONG_PAUSE_MAX = 90

# Priority context keywords
KEYWORDS = [
    "apply", "contact", "send resume to", "email us at", 
    "reach out to", "send cv to", "email", "recruiter", 
    "cv", "resume", "hr", "careers", "jobs", "hiring"
]

# Placeholder patterns to ignore
PLACEHOLDER_PATTERNS = [
    "example.com", "noreply", "no-reply", "test@", 
    "yourname@", "domain.com", "support@", "privacy@", 
    "info@", "admin@", "placeholder"
]

EMAIL_REGEX = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
# =====================================================================


def log_message(msg, level="INFO"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def extract_best_email(text):
    """
    Extracts the best email from the given text.
    Ranks multiple emails by proximity to context keywords.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    emails = re.findall(EMAIL_REGEX, text)
    if not emails:
        return None

    # Filter placeholders
    valid_emails = []
    for email in emails:
        email_lower = email.lower()
        is_placeholder = False
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in email_lower:
                is_placeholder = True
                break
        if not is_placeholder:
            if email not in valid_emails:
                valid_emails.append(email)

    if not valid_emails:
        return None
    if len(valid_emails) == 1:
        return valid_emails[0]

    # Rank by proximity to keywords
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
                if distance < 150:
                    score += (150 - distance)
                start = pos + len(keyword_lower)

        if score > best_score:
            best_score = score
            best_email = email

    return best_email


def clean_url(url):
    """Normalizes a LinkedIn URL by removing query parameters, subdomains, and trailing slashes."""
    if not isinstance(url, str):
        return ""
    url = url.split("?")[0].strip().lower().rstrip("/")
    url = url.replace("https://in.linkedin.com", "https://www.linkedin.com")
    url = url.replace("https://linkedin.com", "https://www.linkedin.com")
    return url


def load_and_convert_cookies(filepath):
    """
    Loads cookies from a Netscape formatting file, a raw li_at token string,
    or a Playwright JSON storage state, and returns Playwright compatible cookies.
    """
    if not os.path.exists(filepath):
        log_message(f"Cookie file '{filepath}' not found!", "WARNING")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        log_message(f"Failed to read cookie file: {e}", "ERROR")
        return []

    if not content:
        return []

    # Case 1: Try JSON parsing first (both Playwright storageState and JSON list format)
    try:
        json_data = json.loads(content)
        if isinstance(json_data, dict) and "cookies" in json_data:
            log_message("Loaded cookies from Playwright storage state JSON format.")
            return json_data["cookies"]
        elif isinstance(json_data, list):
            log_message("Loaded cookies from JSON list format. Reformatting to Playwright standard...")
            playwright_cookies = []
            for c in json_data:
                name = c.get("name")
                    
                domain = c.get("domain", "")
                if isinstance(domain, str) and domain:
                    domain = domain.replace("www.linkedin.com", "linkedin.com")
                    if not domain.startswith("."):
                        domain = "." + domain
                else:
                    domain = ".linkedin.com"
                    
                val = c.get("value", "")
                if isinstance(val, str):
                    val = val.strip()
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                        
                # Map standard cookie fields
                cookie = {
                    "name": name,
                    "value": val,
                    "domain": domain,
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", False)
                }
                # Translate expirationDate to expires
                exp = c.get("expirationDate") or c.get("expires")
                if exp and float(exp) > 0:
                    cookie["expires"] = float(exp)
                # Translate sameSite
                ss = c.get("sameSite", "").lower()
                if "lax" in ss:
                    cookie["sameSite"] = "Lax"
                elif "strict" in ss:
                    cookie["sameSite"] = "Strict"
                elif "none" in ss or "no_restriction" in ss:
                    cookie["sameSite"] = "None"
                # If unspecified/other, let Playwright default it
                
                playwright_cookies.append(cookie)
            return playwright_cookies
    except Exception:
        pass

    # Case 2: Raw single line token (like raw li_at cookie value)
    if "\t" not in content and "\n" not in content and len(content) > 50:
        log_message("Treating cookie file content as a raw li_at token.")
        return [{
            "name": "li_at",
            "value": content,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True
        }]

    # Case 3: Parse Netscape formatting
    log_message("Parsing cookies from Netscape text format...")
    cookies = []
    lines = content.splitlines()
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain, flag, path, secure, expiration, name, value = parts[:7]
            secure_bool = secure.upper() in ["TRUE", "1"]
            try:
                expires_val = float(expiration)
            except ValueError:
                expires_val = time.time() + 86400 * 30  # Default 30 days
            
            cookie_dict = {
                "name": name,
                "value": value,
                "domain": domain if domain.startswith(".") else f".{domain}",
                "path": path,
                "secure": secure_bool,
                "httpOnly": False
            }
            if expires_val > 0:
                cookie_dict["expires"] = expires_val
            cookies.append(cookie_dict)
            
    log_message(f"Successfully parsed {len(cookies)} cookies from Netscape file.")
    return cookies


def check_and_handle_checkpoint(page):
    """
    Checks if a login/CAPTCHA checkpoint has been triggered.
    Pauses execution and alerts the user to solve it manually in the browser.
    """
    url = page.url.lower()
    if "checkpoint" in url or "login" in url or "signup" in url:
        log_message("=" * 60, "WARNING")
        log_message("LinkedIn CAPTCHA, Verification, or Sign In screen detected!", "WARNING")
        log_message("Please solve the verification / log in manually in the open browser window.", "WARNING")
        log_message("Verification solve hone ke baad script resume ho jayegi.", "WARNING")
        log_message("=" * 60, "WARNING")

        # Wait until user resolves checkpoint/login
        while "checkpoint" in page.url.lower() or "login" in page.url.lower() or "signup" in page.url.lower():
            time.sleep(5)
            if page.is_closed():
                log_message("Browser was closed. Exiting script.", "ERROR")
                sys.exit(1)

        log_message("Verification resolved! Resuming extraction...", "INFO")
        
        # Save updated session state
        try:
            page.context.storage_state(path=COOKIE_FILE)
            log_message(f"Naya session cookies storage_state '{COOKIE_FILE}' mein save kar liye gaye hain.", "INFO")
        except Exception as e:
            log_message(f"Failed to save session cookies: {e}", "WARNING")


def append_to_csv_progress(row_dict, headers):
    """Progressively appends a processed row to the CSV file (crash-safety), preserving all columns."""
    file_exists = os.path.exists(OUTPUT_FILE)
    try:
        with open(OUTPUT_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row_dict)
            
        # Keep Excel output updated
        try:
            excel_path = OUTPUT_FILE.replace(".csv", ".xlsx")
            df_all = pd.read_csv(OUTPUT_FILE)
            df_all.to_excel(excel_path, index=False)
        except Exception as excel_err:
            log_message(f"Warning: Failed to update Excel output file: {excel_err}", "WARNING")
    except Exception as e:
        log_message(f"Failed to write progressive save to output CSV: {e}", "ERROR")


def main():
    log_message("=" * 60)
    log_message("LINKEDIN JOB PAGE EMAIL SCRAPER")
    log_message("=" * 60)

    # 1. Load Input Data
    if not os.path.exists(INPUT_FILE):
        log_message(f"Input file '{INPUT_FILE}' not found!", "ERROR")
        sys.exit(1)

    try:
        if INPUT_FILE.endswith(".csv"):
            df = pd.read_csv(INPUT_FILE)
        elif INPUT_FILE.endswith(".json"):
            df = pd.read_json(INPUT_FILE)
        else:
            log_message("Unsupported file format! Please use a .csv or .json file.", "ERROR")
            sys.exit(1)
    except Exception as e:
        log_message(f"Failed to read input file: {e}", "ERROR")
        sys.exit(1)

    if LINK_COLUMN_NAME not in df.columns:
        log_message(f"Column '{LINK_COLUMN_NAME}' not found in input file headers.", "ERROR")
        sys.exit(1)

    # Clean job links and remove duplicates from input
    df_clean = df.dropna(subset=[LINK_COLUMN_NAME])
    job_links = df_clean[LINK_COLUMN_NAME].unique().tolist()
    total_jobs = len(job_links)
    log_message(f"Successfully loaded {total_jobs} unique job links from input file.")

    # 2. Check for already processed links (Incremental Resume support)
    processed_links = set()
    success_count = 0
    skipped_count = 0
    failed_count = 0

    headers = list(df.columns)
    if "extracted_email" not in headers:
        headers.append("extracted_email")
    if "status" not in headers:
        headers.append("status")

    if os.path.exists(OUTPUT_FILE):
        try:
            processed_df = pd.read_csv(OUTPUT_FILE)
            if "job_link" in processed_df.columns or LINK_COLUMN_NAME in processed_df.columns or ("Company Name" in processed_df.columns and processed_df["Company Name"].astype(str).str.startswith("http").any()):
                col_key = "job_link" if "job_link" in processed_df.columns else LINK_COLUMN_NAME
                
                # Group previous processing results
                for _, row in processed_df.iterrows():
                    comp_val = str(row.get("Company Name", ""))
                    if comp_val.startswith("http"):
                        link = comp_val
                        status = row.get("Job Title")
                    else:
                        link = row.get(col_key)
                        status = row.get("status")
                        
                    if pd.notna(link):
                        link_clean = clean_url(str(link))
                        if link_clean:
                            processed_links.add(link_clean)
                        if status == "EMAIL_FOUND":
                            success_count += 1
                        elif status == "SKIPPED_NO_EMAIL":
                            skipped_count += 1
                        elif status in ["FAILED_TO_LOAD", "SKIPPED_ERROR", "CANCELLED_INTERRUPTED"]:
                            failed_count += 1
            
            # Check if output columns match new headers or if there are empty rows/shifted rows that need merging (migration support)
            has_missing_data = False
            has_shifted_data = False
            if "Company Name" in processed_df.columns:
                has_shifted_data = processed_df["Company Name"].astype(str).str.startswith("http").any()
                # Check for NaNs/blanks in Company Name for non-shifted rows
                non_shifted = processed_df[~processed_df["Company Name"].astype(str).str.startswith("http")]
                if not non_shifted.empty:
                    has_missing_data = (non_shifted["Company Name"].isna() | (non_shifted["Company Name"] == "")).sum() > 0
                else:
                    has_missing_data = True
                
            if set(processed_df.columns) != set(headers) or has_missing_data or has_shifted_data:
                log_message("Output file headers do not match or contain shifted/missing row details. Migrating old entries to preserve all columns...")
                migration_rows = []
                col_key = "job_link" if "job_link" in processed_df.columns else LINK_COLUMN_NAME
                for _, row_prev in processed_df.iterrows():
                    comp_val = str(row_prev.get("Company Name", ""))
                    if comp_val.startswith("http"):
                        link_val = comp_val
                        email_val = row_prev.get("City / Location", "")
                        status_val = row_prev.get("Job Title", "")
                    else:
                        link_val = row_prev.get(col_key)
                        email_val = row_prev.get("extracted_email", "")
                        status_val = row_prev.get("status", "")
                        
                    if pd.notna(link_val) and str(link_val).strip():
                        link_clean = clean_url(str(link_val))
                        # Find corresponding row in original input df
                        orig_rows = df_clean[df_clean[LINK_COLUMN_NAME].apply(clean_url) == link_clean]
                        if not orig_rows.empty:
                            mig_dict = orig_rows.iloc[0].to_dict()
                        else:
                            mig_dict = {col: "" for col in df.columns}
                            mig_dict[LINK_COLUMN_NAME] = str(link_val).strip()
                        
                        mig_dict["extracted_email"] = str(email_val) if pd.notna(email_val) else ""
                        mig_dict["status"] = str(status_val) if pd.notna(status_val) else ""
                        migration_rows.append(mig_dict)
                
                # Re-index columns in migrated rows to match headers
                migrated_df = pd.DataFrame(migration_rows)
                migrated_df = migrated_df.reindex(columns=headers)
                migrated_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
                try:
                    migrated_df.to_excel(OUTPUT_FILE.replace(".csv", ".xlsx"), index=False)
                except Exception:
                    pass
                log_message("Migration complete! All previous progress was preserved and converted.")
                
            log_message(f"Found {len(processed_links)} already processed links in output file. Skipping them.")
        except Exception as e:
            log_message(f"Error loading/migrating processed links: {e}. Starting fresh.", "WARNING")

    # Filter out already processed links
    remaining_df = df_clean[~df_clean[LINK_COLUMN_NAME].apply(clean_url).isin(processed_links)]
    log_message(f"Remaining jobs to process: {len(remaining_df)}/{total_jobs}")

    if remaining_df.empty:
        log_message("Saare job links already process ho chuke hain! Nayi details save karne ki zaroorat nahi hai.")
        sys.exit(0)

    # 3. Setup Playwright & Load Session
    with sync_playwright() as p:
        log_message("Launching Chromium browser...")
        browser = p.chromium.launch(headless=HEADLESS)
        
        context_args = {
            "viewport": {"width": 1280, "height": 800}
        }
        
        context = browser.new_context(**context_args)
        
        # Load and set cookies from linkedin_cookies.txt
        loaded_cookies = load_and_convert_cookies(COOKIE_FILE)
        if loaded_cookies:
            context.add_cookies(loaded_cookies)
            log_message("Cookies loaded and injected into Playwright context.")
        else:
            log_message("No cookies injected. Starting with empty context.", "WARNING")
            
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Test request to verify login status
        log_message("Verifying LinkedIn login status with loaded cookies...")
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=45000)
            page.wait_for_load_state("domcontentloaded")
            
            # Check if redirected to login/signup or if login fields are visible
            if "login" in page.url.lower() or "signup" in page.url.lower() or page.locator("input[name='session_key']").is_visible(timeout=5000):
                log_message("=" * 60, "ERROR")
                log_message("Cookies expired, please re-export", "ERROR")
                log_message("=" * 60, "ERROR")
                browser.close()
                sys.exit(1)
            
            log_message("Successfully logged into LinkedIn via cookies!")
        except Exception as check_err:
            if "Cookies expired" in str(check_err):
                sys.exit(1)
            # Check if it was a redirect to login
            if "login" in page.url.lower() or "signup" in page.url.lower():
                log_message("=" * 60, "ERROR")
                log_message("Cookies expired, please re-export", "ERROR")
                log_message("=" * 60, "ERROR")
                browser.close()
                sys.exit(1)
            log_message(f"Login validation check encountered a network/loading warning: {check_err}. Proceeding with jobs...")

        # 4. Processing Loop
        for idx, (_, row) in enumerate(remaining_df.iterrows()):
            job_link_clean = str(row[LINK_COLUMN_NAME]).strip()
            # Force www.linkedin.com to prevent regional subdomain redirect loops
            job_link_clean = re.sub(r'https?://[a-z]{2}\.linkedin\.com', 'https://www.linkedin.com', job_link_clean)
            log_message(f"\n[{idx+1}/{len(remaining_df)}] Navigating to: {job_link_clean}")
            
            row_dict = row.to_dict()
            status = "FAILED_TO_LOAD"
            extracted_email = ""
            
            try:
                # Open page
                response = page.goto(job_link_clean, timeout=60000)
                status_code = response.status if response else "Unknown"
                if status_code != 200:
                    log_message(f"Page returned status code: {status_code}", "WARNING")
                page.wait_for_load_state("domcontentloaded")
                
                # Check CAPTCHA/Login Checkpoint
                check_and_handle_checkpoint(page)
                
                # Wait for main container elements
                page.wait_for_timeout(3000)
                
                # Click description expand button (Show more)
                show_more_selectors = [
                    ".jobs-description__footer-button",
                    ".jobs-description-content__show-more-button",
                    "button[aria-label*='Show more']",
                    "button:has-text('Show more')",
                    "button:has-text('See more')"
                ]
                
                expanded = False
                for selector in show_more_selectors:
                    try:
                        locator = page.locator(selector).first
                        if locator.is_visible(timeout=1000):
                            locator.click()
                            log_message(f"Clicked description expand button: '{selector}'")
                            page.wait_for_timeout(1000)
                            expanded = True
                            break
                    except Exception:
                        pass
                
                # Click meet-the-hiring-team expansion buttons if visible
                try:
                    hiring_team_button = page.locator("button:has-text('Hiring Team'), button[aria-label*='hiring team']").first
                    if hiring_team_button.is_visible(timeout=1000):
                        hiring_team_button.click()
                        log_message("Clicked Hiring Team details button.")
                        page.wait_for_timeout(1000)
                except Exception:
                    pass
                
                # Extract page visible text
                page_text = page.locator("body").inner_text()
                
                # Parse email
                email = extract_best_email(page_text)
                
                if email:
                    status = "EMAIL_FOUND"
                    extracted_email = email.strip()
                    success_count += 1
                    log_message(f"SUCCESS: EMAIL FOUND: {extracted_email}")
                else:
                    status = "SKIPPED_NO_EMAIL"
                    skipped_count += 1
                    log_message("NO_EMAIL: No email found in page text.")
                    
            except KeyboardInterrupt:
                log_message("KeyboardInterrupt detected. Saving current progress and exiting gracefully...", "WARNING")
                row_dict["extracted_email"] = extracted_email
                row_dict["status"] = "CANCELLED_INTERRUPTED"
                append_to_csv_progress(row_dict, headers)
                break
            except Exception as page_err:
                status = "FAILED_TO_LOAD"
                failed_count += 1
                log_message(f"WARNING: Failed to load or extract from page: {page_err}", "WARNING")
                
            # Progressive save (crash-safety)
            row_dict["extracted_email"] = extracted_email
            row_dict["status"] = status
            append_to_csv_progress(row_dict, headers)
            
            # Rate limiting delays
            try:
                if idx < len(remaining_df) - 1:
                    # Random delay between jobs
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    log_message(f"Sleeping {delay:.2f} seconds to protect rate limits...")
                    time.sleep(delay)
                    
                    # Longer break after every N jobs
                    if (idx + 1) % LONG_PAUSE_EVERY_N_JOBS == 0:
                        long_pause = random.randint(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
                        log_message(f"Taking a human-like longer break for {long_pause} seconds...")
                        time.sleep(long_pause)
            except KeyboardInterrupt:
                log_message("KeyboardInterrupt detected during sleep. Exiting gracefully...", "WARNING")
                break

        # 5. Summarize
        log_message("=" * 60)
        log_message("SCRAPE COMPLETED")
        log_message(f"Total jobs processed: {len(remaining_df)}")
        log_message(f"Overall database stats: Emails Found={success_count} | No Email={skipped_count} | Failed={failed_count}")
        log_message("=" * 60)
        
        # Close browser
        browser.close()


if __name__ == "__main__":
    main()
