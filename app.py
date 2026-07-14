import os
import csv
import time
import random
import re
import sys
import logging
import datetime
import requests
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from flask import Flask, render_template, request, jsonify, redirect, url_for
from playwright.sync_api import sync_playwright
from apscheduler.schedulers.background import BackgroundScheduler
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reconfigure stdout to use UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flask_app")

app = Flask(__name__)

# Constants / Configurations
SCRAPE_INTERVAL_HOURS = 24
SESSION_FILE = "linkedin_session.json"
JOBS_CSV = "linkedin_fresher_data_analyst_jobs_merged.csv"
JOBS_JSON = "linkedin_fresher_data_analyst_jobs_merged.json"
EMAILS_CSV = "generated_cold_emails.csv"
EMAILS_JSON = "generated_cold_emails.json"
LOG_FILE = "scheduler_log.txt"
TRACKER_FILE = "sent_emails_tracker.json"
MAX_DAILY_EMAILS = 10

# Statistics tracking
stats = {
    "jobs_scraped": 0,
    "emails_generated": 0,
    "emails_sent": 0
}

import threading
scraper_running = False
scraper_lock = threading.Lock()

apply_running = False
apply_thread_lock = threading.Lock()

email_running = False
email_lock = threading.Lock()

# Default Resume Data for Cold Email Generator
RESUME_DATA = {
    "Name": "Shashank Jain",
    "Role": "Data Analyst",
    "Skills": [
        "Python", "SQL", "Pandas", "Numpy", "Data Cleaning", "Exploratory Data Analysis (EDA)", "Insight Generation",
        "Power BI", "Tableau", "PostgreSQL", "MongoDB", "FastAPI", "LangChain", "RAG", "Git", "JupyterNotebook", "VS Code", "SDLC",
        "Communication", "Problem Solving", "Teamwork", "Adaptability"
    ],
    "Experience": [
        {
            "Company": "Appic Software Development (On-Site)",
            "Details": "Performed exploratory data analysis and preprocessing on 10,000+ rows using Pandas and NumPy; Applied data cleaning and transformation techniques improving dataset quality by 25%; Created interactive Power BI dashboards for KPI tracking reducing manual reporting effort by 30%."
        }
    ],
    "Projects": [
        {
            "Name": "Sales and Revenue Performance Analysis",
            "Technologies": ["Python", "Numpy", "SQL", "Streamlit", "Seaborn"],
            "Details": "Built a Python SQL ETL pipeline to clean 100k+ transactions and run YoY sales and cohort retention models in SQLite; Developed a Holt's linear forecasting model (31.6% MAPE) and RFM customer segmentation to analyze lifetime value; Developed an interactive Streamlit dashboard that identified a 30% discount tipping point, projecting a 1.8% gross profit margin increase."
        },
        {
            "Name": "Healthcare Analytics Dashboard",
            "Technologies": ["Python", "Pandas", "PostgreSQL", "XGBoost", "Streamlit"],
            "Details": "Designed a healthcare analytics system that predicts 30-day patient readmission risk using clinical and demographic patient data; Built a disease outbreak forecasting module analyzing historical case trends to predict future outbreak patterns by region and time; Developed an interactive dashboard comparing treatment effectiveness across patient groups using survival analysis to support hospital decision-making."
        }
    ],
    "Contact": {
        "Phone": "+91-7878927128",
        "LinkedIn": "linkedin.com/in/shashankjain",
        "GitHub": "github.com/shashankjain843"
    }
}

# Logging helper
def log_scheduler(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip(), flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        # Also write to logs.txt
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to log scheduler: {e}")

def save_emails_atomically(emails_list):
    """
    Saves the list of emails to JSON and CSV atomically to prevent corruption.
    """
    # 1. Write JSON atomically
    temp_json = EMAILS_JSON + ".tmp"
    try:
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(emails_list, f, indent=4, ensure_ascii=False)
        if os.path.exists(EMAILS_JSON):
            try:
                os.remove(EMAILS_JSON)
            except:
                pass
        os.rename(temp_json, EMAILS_JSON)
    except Exception as e:
        log_scheduler(f"[ERROR] Failed to save emails JSON atomically: {e}")
        if os.path.exists(temp_json):
            try:
                os.remove(temp_json)
            except:
                pass

    # 2. Write CSV atomically
    temp_csv = EMAILS_CSV + ".tmp"
    try:
        with open(temp_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Company", "Job Title", "Generated Email", "Job URL", "Recipient Email", "Send Status"])
            for email in emails_list:
                writer.writerow([
                    email.get("Company", "") or "",
                    email.get("Job Title", "") or "",
                    email.get("Generated Email", "") or "",
                    email.get("Job URL", "") or "",
                    email.get("Recipient Email", "Not Found") or "Not Found",
                    email.get("Send Status", "Not Sent") or "Not Sent"
                ])
        if os.path.exists(EMAILS_CSV):
            try:
                os.remove(EMAILS_CSV)
            except:
                pass
        os.rename(temp_csv, EMAILS_CSV)
    except Exception as e:
        log_scheduler(f"[ERROR] Failed to save emails CSV atomically: {e}")
        if os.path.exists(temp_csv):
            try:
                os.remove(temp_csv)
            except:
                pass



# Helper to retry browser actions
def retry_action(action_fn, action_name, max_attempts=3, initial_delay=2):
    attempt = 0
    delay = initial_delay
    while attempt < max_attempts:
        try:
            return action_fn()
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                log_scheduler(f"[ERROR] Action '{action_name}' failed after {max_attempts} attempts. Error: {e}")
                raise e
            log_scheduler(f"[WARNING] Action '{action_name}' failed (attempt {attempt}/{max_attempts}). Retrying in {delay}s... Error: {e}")
            time.sleep(delay)
            delay *= 2

# Limit tracking helpers
def get_daily_sent_count():
    today = time.strftime("%Y-%m-%d")
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today:
                    return data.get("count", 0)
        except Exception:
            pass
    return 0

def increment_daily_sent_count():
    today = time.strftime("%Y-%m-%d")
    count = get_daily_sent_count() + 1
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump({"date": today, "count": count}, f)
    except Exception as e:
        log_scheduler(f"[WARNING] Failed to write to tracker file: {e}")
    return count

def find_email_in_text(text):
    if not text:
        return None
    emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', text)
    for email in emails:
        if not any(x in email.lower() for x in ["noreply", "no-reply", "donotreply", "support@", "privacy@", "info@"]):
            return email
    return emails[0] if emails else None

def extract_subject_and_body(email_text):
    lines = email_text.strip().split("\n")
    subject = "Application for Data Analyst Position"
    body_lines = []
    subject_found = False
    
    for line in lines:
        if not subject_found and line.lower().startswith("subject:"):
            subject = line[len("subject:"):].strip()
            subject_found = True
        else:
            body_lines.append(line)
            
    body = "\n".join(body_lines).strip()
    return subject, body

def convert_docx_to_pdf(docx_path, pdf_path):
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        log_scheduler(f"[SUCCESS] Converted {docx_path} to {pdf_path} using docx2pdf.")
        return True
    except Exception as e:
        log_scheduler(f"[WARNING] Failed to convert docx to pdf using docx2pdf: {e}. Trying raw win32com...")
        
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(docx_path)
        # Format 17 is for PDF
        doc.SaveAs(pdf_path, FileFormat=17)
        doc.Close()
        word.Quit()
        log_scheduler(f"[SUCCESS] Converted {docx_path} to {pdf_path} using Word COM.")
        return True
    except Exception as e:
        log_scheduler(f"[ERROR] Failed to convert docx to pdf using Word COM: {e}.")
        
    return False

def send_email_via_smtp(subject, body, recipient_email):
    global stats
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    
    if not smtp_email or not smtp_password:
        log_scheduler("[ERROR] SMTP credentials not set in .env. Skipping email sending.")
        return False
        
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = smtp_email
        msg["To"] = recipient_email
        
        # Attach body
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        dir_path = os.path.dirname(os.path.abspath(__file__))
        
        # Look for PDF resume first
        pdf_path = os.path.join(dir_path, "my_resume.pdf")
        docx_path = os.path.join(dir_path, "my_resume.docx")
        
        resume_path = None
        if os.path.exists(pdf_path):
            resume_path = pdf_path
        elif os.path.exists(docx_path):
            log_scheduler("[INFO] PDF resume not found. Attempting to convert my_resume.docx to PDF...")
            success = convert_docx_to_pdf(docx_path, pdf_path)
            if success and os.path.exists(pdf_path):
                resume_path = pdf_path
            else:
                log_scheduler("[WARNING] DOCX to PDF conversion failed. Falling back to original DOCX.")
                resume_path = docx_path
                
        if resume_path:
            filename = os.path.basename(resume_path)
            try:
                with open(resume_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}",
                )
                msg.attach(part)
                log_scheduler(f"[INFO] Attached resume: {filename} to email.")
            except Exception as att_err:
                log_scheduler(f"[WARNING] Failed to attach resume: {att_err}")
        else:
            log_scheduler(f"[WARNING] Resume file (my_resume.pdf or my_resume.docx) not found in {dir_path}. Sending without attachment.")
            
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=120)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, [recipient_email], msg.as_string())
        server.quit()
        
        log_scheduler(f"[SUCCESS] SMTP Email successfully sent to: {recipient_email}")
        stats["emails_sent"] += 1
        return True
    except Exception as smtp_err:
        log_scheduler(f"[ERROR] SMTP sending failed to {recipient_email}: {smtp_err}")
        return False

# Helper functions from scrape_linkedin_jobs.py
def safe_extract_any(locator, selectors, attribute=None, default=""):
    for selector in selectors:
        try:
            el = locator.locator(selector).first
            if el.count() > 0:
                if attribute:
                    val = el.get_attribute(attribute)
                    if val:
                        return val.strip()
                else:
                    val = el.inner_text()
                    if val:
                        return val.strip()
        except Exception:
            pass
    return default

def is_valid_title(title, keyword):
    title_lower = title.lower()
    keyword_lower = keyword.lower()
    words = [w.strip() for w in keyword_lower.replace("or", "").replace("and", "").split() if len(w.strip()) > 1]
    
    exclude_title_words = ["senior", "lead", "sr", "principal", "manager", "head", "architect", "expert", "specialist"]
    for word in exclude_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
            return False
            
    if not words:
        return True
        
    return any(w in title_lower for w in words)

def is_fresher_friendly(title, description, criteria_exp):
    title_lower = title.lower()
    desc_lower = description.lower()
    crit_lower = criteria_exp.lower()
    
    exclude_title_words = ["senior", "lead", "sr", "principal", "manager", "head", "architect", "expert", "specialist"]
    for word in exclude_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
            return False
            
    if "mid-senior" in crit_lower or "director" in crit_lower or "executive" in crit_lower:
        return False
        
    fresher_signals = [
        r'\bfreshers?\b', 
        r'\b0\s*-\s*1\s*(?:years?|yrs?)\b', 
        r'\b0\s*(?:years?|yrs?)\b', 
        r'\bno\s+experience\s+required\b', 
        r'\bentry\s*level\b'
    ]
    for signal in fresher_signals:
        if re.search(signal, desc_lower):
            return True
            
    exp_patterns = [
        r'\b(?:2|3|4|5|6|7|8|9|10)\+?\s*(?:to|-)\s*\d+\s*(?:years?|yrs?)\b', 
        r'\b(?:2|3|4|5|6|7|8|9|10)\+\s*(?:years?|yrs?)\b',                  
        r'\b(?:minimum|min|at least|required)\s+of?\s*(?:2|3|4|5|6|7|8|9|10)\s*(?:years?|yrs?)\b', 
        r'\b(?:2|3|4|5|6|7|8|9|10)\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b', 
    ]
    
    for pattern in exp_patterns:
        if re.search(pattern, desc_lower):
            return False
            
    return True

def extract_skills(description):
    desc_lower = description.lower()
    skills_map = {
        "SQL": [r'\bsql\b', r'\bpostgresql\b', r'\bmysql\b', r'\bsql server\b', r'\bsnowflake\b', r'\bbigquery\b'],
        "Excel": [r'\bexcel\b', r'\bspreadsheet\s*s?\b', r'\bgoogle sheets\b'],
        "Python": [r'\bpython\b'],
        "R": [r'\br\b', r'\br-programming\b'],
        "Power BI": [r'\bpower\s*bi\b', r'\bpowerbi\b'],
        "Tableau": [r'\btableau\b'],
        "Statistics": [r'\bstatistics\b', r'\bstatistical\b'],
        "VBA": [r'\bvba\b', r'\bmacros\b'],
        "SAS": [r'\bsas\b'],
        "Alteryx": [r'\balteryx\b'],
        "Qlik": [r'\bqlik\b', r'\bqlikview\b', r'\bqliksense\b'],
        "ETL": [r'\betl\b', r'\bdata pipeline\b'],
        "Reporting": [r'\breporting\b', r'\breports\b'],
        "Data Visualization": [r'\bvisualization\b', r'\bdashboards?\b']
    }
    
    found_skills = []
    for skill, patterns in skills_map.items():
        for pattern in patterns:
            if re.search(pattern, desc_lower):
                found_skills.append(skill)
                break
                
    return ", ".join(found_skills) if found_skills else "Not Mentioned"

def extract_salary(description):
    desc_lower = description.lower()
    salary_patterns = [
        r'\b\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?|lcs?|cr|crores?|k|thousand|inr|rs\.?| rupees?)\b',
        r'\b\d+\s*lpa\b',
        r'\b(?:rs\.?|inr|rupees?)\s*\d+(?:\.\d+)?\s*(?:lakhs?|lpa|k)?\b'
    ]
    
    for pattern in salary_patterns:
        match = re.search(pattern, desc_lower)
        if match:
            return match.group(0).upper()
            
    return "Not Mentioned"

def extract_website(description):
    match = re.search(r'\bhttps?://(?:www\.)?([a-zA-Z0-9-]+)\.[a-z]{2,}(?:\S*)', description)
    if match:
        url = match.group(0)
        if not any(domain in url.lower() for domain in ["linkedin.com", "google.com", "microsoft.com", "youtube.com"]):
            return url
    return "Not Mentioned"

def check_captcha(page):
    url_lower = page.url.lower()
    if "checkpoint/challenge" in url_lower or "captcha" in url_lower or page.locator("text='Security verification'").count() > 0 or page.locator("text='Please solve the puzzle'").count() > 0:
        log_scheduler("[ALERT] CAPTCHA or Security Verification page loaded. Captcha handler is limited in headless environment!")

def is_linkedin_logged_in(page):
    """Check karo ki LinkedIn pe actually logged in hain ya nahi — DOM elements se."""
    try:
        # Profile nav icon ya feed page ka actual element check karo
        logged_in_selectors = [
            "div.global-nav__me",          # Profile/me icon in nav
            "img.global-nav__me-photo",    # Profile photo
            "a[href*='/feed/']"             # Feed link in nav
        ]
        for sel in logged_in_selectors:
            if page.locator(sel).first.count() > 0:
                return True
        # Agar login page pe hain toh logged out
        if "login" in page.url or "authwall" in page.url or "signup" in page.url:
            return False
        return False
    except Exception:
        return False

def login_to_linkedin(page, email, password):
    log_scheduler("[INFO] Starting LinkedIn login process...")
    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_session.json")

    # Pehle check karo: session file se already logged in hain?
    if os.path.exists(session_path):
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=25000)
            page.wait_for_load_state("networkidle", timeout=15000)
            if is_linkedin_logged_in(page):
                log_scheduler("[SUCCESS] Session valid hai. LinkedIn login skip kar rahe hain.")
                return
            else:
                log_scheduler("[INFO] Session expired ya invalid hai. Purana session delete karke fresh login karenge...")
                try:
                    os.remove(session_path)
                except Exception:
                    pass
        except Exception as e:
            log_scheduler(f"[INFO] Session check fail hua: {e}. Fresh login karenge...")
            try:
                os.remove(session_path)
            except Exception:
                pass
    
    # Fresh login karo
    try:
        def goto_login():
            page.goto("https://www.linkedin.com/login", timeout=60000)
            page.wait_for_load_state("networkidle")
        
        retry_action(goto_login, "Navigate to LinkedIn login page", max_attempts=1)
        check_captcha(page)
        
        # Fill email
        username_sel = "input#username"
        page.wait_for_selector(username_sel, state="visible", timeout=10000)
        page.locator(username_sel).fill(email)
        
        # Fill password
        password_sel = "input#password"
        page.wait_for_selector(password_sel, state="visible", timeout=10000)
        page.locator(password_sel).fill(password)
        
        # Sign in click with navigation expect
        submit_sel = "button[type='submit']"
        page.wait_for_selector(submit_sel, state="visible", timeout=10000)
        
        def click_submit():
            with page.expect_navigation(timeout=60000):
                page.locator(submit_sel).click()
            page.wait_for_load_state("networkidle")
            
        retry_action(click_submit, "Submit LinkedIn login form", max_attempts=1)
        check_captcha(page)
        
        # Login verify karo DOM se
        page.wait_for_timeout(2000)
        if is_linkedin_logged_in(page):
            log_scheduler("[SUCCESS] LinkedIn pe successfully login ho gaye!")
            page.context.storage_state(path=session_path)
            log_scheduler(f"[INFO] Naya session save kar diya: {session_path}")
        elif "checkpoint" in page.url:
            log_scheduler(f"[WARNING] LinkedIn ne security check maanga. URL: {page.url}")
            check_captcha(page)
            page.context.storage_state(path=session_path)
        else:
            log_scheduler(f"[WARNING] Login ke baad bhi logged-in elements nahi mile. URL: {page.url}")
            page.context.storage_state(path=session_path)
    except Exception as login_err:
        log_scheduler(f"[ERROR] LinkedIn login fail hua: {login_err}")

# Playwright LinkedIn Scraper core
def scrape_linkedin_jobs(cities=None, keyword="Data Analyst", use_login=False) -> list:
    import urllib.parse
    global stats
    all_jobs = []
    target_job_count = 15  # Limit per city for better performance

    if not cities:
        cities = ["Jaipur", "Noida", "Delhi", "Gurgaon"]

    city_mappings = {
        "Delhi": "Delhi, India",
        "Noida": "Noida, Uttar Pradesh, India",
        "Gurgaon": "Gurgaon, Haryana, India",
        "Gurugram": "Gurgaon, Haryana, India",
        "Jaipur": "Jaipur, Rajasthan, India"
    }

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_session.json")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        if os.path.exists(session_path):
            context_args["storage_state"] = session_path
            log_scheduler("[INFO] Loading existing LinkedIn session for scraper...")
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Log in if credentials available and requested
        linkedin_email = os.environ.get("LINKEDIN_EMAIL")
        linkedin_password = os.environ.get("LINKEDIN_PASSWORD")
        if use_login and linkedin_email and linkedin_password:
            login_to_linkedin(page, linkedin_email, linkedin_password)

        for city in cities:
            city_clean = city.strip()
            seen_companies = set()  # Har city ke liye fresh duplicate check
            city_query = city_mappings.get(city_clean, f"{city_clean}, India")
            url_keyword = urllib.parse.quote(keyword)
            url_location = urllib.parse.quote(city_query)
            search_url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location={url_location}&distance=25&sortBy=DD&f_TPR=r86400"

            log_scheduler(f"\n{'='*60}")
            log_scheduler(f"[CITY {cities.index(city)+1}/{len(cities)}] Scraping: {city_clean} | Keyword: '{keyword}'")
            log_scheduler(f"{'='*60}")
            log_scheduler(f"[URL] {search_url}")
            
            def goto_search():
                page.goto(search_url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
            try:
                retry_action(goto_search, f"Navigate to Search URL for {city_clean}")
                page.wait_for_timeout(5000)
            except Exception as e:
                log_scheduler(f"[ERROR] Failed to load search page for {city_clean}: {e}")
                continue

            # Fallback check if 0 jobs found with 24h filter
            job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
            if job_cards.count() == 0 and "f_TPR=r86400" in search_url:
                fallback_url = search_url.replace("&f_TPR=r86400", "")
                log_scheduler(f"[INFO] 0 jobs found with 24h filter for {city_clean}. Retrying with fallback URL: {fallback_url}")
                try:
                    page.goto(fallback_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(5000)
                except Exception as fe:
                    log_scheduler(f"[ERROR] Failed to load fallback search page for {city_clean}: {fe}")

            # Scroll to load job cards
            last_count = 0
            no_change_iterations = 0
            while True:
                try:
                    page.evaluate("""
                        document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"]').forEach(el => el.remove());
                        document.body.style.overflow = 'auto';
                    """)
                except:
                    pass

                job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
                count = job_cards.count()
                if count >= target_job_count:
                    break
                if count == last_count:
                    no_change_iterations += 1
                    log_scheduler(f"[SCROLL] {city_clean}: {count} cards loaded (no change #{no_change_iterations})...")
                    if no_change_iterations > 6:
                        break
                else:
                    no_change_iterations = 0
                    last_count = count

                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                except:
                    pass
                page.wait_for_timeout(random.randint(1500, 2000))

                see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
                if see_more_btn.count() > 0 and see_more_btn.is_visible():
                    try:
                        btn_sel = "button.infinite-scroller__show-more-button" if page.locator("button.infinite-scroller__show-more-button").count() > 0 else "button:has-text('See more jobs')"
                        page.wait_for_selector(btn_sel, state="visible", timeout=10000)
                        see_more_btn.click(force=True, timeout=3000)
                        page.wait_for_timeout(2000)
                    except:
                        pass

            job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
            card_count = min(job_cards.count(), target_job_count * 2)
            log_scheduler(f"[FOUND] {job_cards.count()} job cards for {city_clean}. Processing top {card_count}...")
            city_saved = 0
            city_skipped = 0

            for i in range(card_count):
                card = job_cards.nth(i)
                try:
                    job_title = safe_extract_any(card, ["h3.base-search-card__title", "h3.job-search-card__title", ".base-search-card__title", "h3"])
                    company_name = safe_extract_any(card, ["h4.base-search-card__subtitle", "a.hidden-nested-link", ".base-search-card__subtitle", "h4"])
                    location_str = safe_extract_any(card, ["span.job-search-card__location", ".job-search-card__location", "span"])
                    job_url = safe_extract_any(card, ["a.base-card__full-link", "a.job-search-card__link", "a"], attribute="href")

                    if not job_url or not job_title or not company_name:
                        city_skipped += 1
                        continue

                    clean_url = job_url.split("?")[0]

                    if not is_valid_title(job_title, keyword):
                        log_scheduler(f"  [{i+1}/{card_count}] SKIP (title mismatch): '{job_title}'")
                        city_skipped += 1
                        continue

                    comp_key = company_name.strip().lower()
                    if comp_key in seen_companies:
                        log_scheduler(f"  [{i+1}/{card_count}] SKIP (duplicate company): {company_name}")
                        city_skipped += 1
                        continue

                    # Details extraction with retry
                    def extract_card_details():
                        card.scroll_into_view_if_needed()
                        page.wait_for_timeout(300)
                        card.wait_for(state="visible", timeout=5000)
                        card.click(force=True, timeout=5000)
                        
                        desc_el = page.locator("div.show-more-less-html__markup, .description__text").first
                        try:
                            desc_el.wait_for(state="visible", timeout=3000)
                        except:
                            pass
                        page.wait_for_timeout(800)

                        show_more_desc = page.locator("button.show-more-less-html__button, button:has-text('Show more'), button:has-text('See more')").first
                        if show_more_desc.count() > 0 and show_more_desc.is_visible():
                            try:
                                sm_sel = "button.show-more-less-html__button" if page.locator("button.show-more-less-html__button").count() > 0 else "button:has-text('Show more')"
                                page.wait_for_selector(sm_sel, state="visible", timeout=5000)
                                show_more_desc.click(force=True, timeout=2000)
                                page.wait_for_timeout(400)
                            except:
                                pass

                        description = "Not Mentioned"
                        if desc_el.count() > 0:
                            description = desc_el.inner_text().strip()
                        return description

                    log_scheduler(f"  [{i+1}/{card_count}] Processing: '{job_title}' @ {company_name}...")
                    try:
                        description = retry_action(extract_card_details, f"Extract details for {job_title} at {company_name}")
                    except Exception as card_err:
                        log_scheduler(f"  [{i+1}/{card_count}] WARNING: Skipping '{job_title}' — {card_err}")
                        city_skipped += 1
                        continue

                    criteria_items = page.locator("li.description__job-criteria-item")
                    criteria_count = criteria_items.count()
                    criteria_dict = {}
                    for j in range(criteria_count):
                        item = criteria_items.nth(j)
                        header_el = item.locator("h3.description__job-criteria-subheader").first
                        value_el = item.locator("span.description__job-criteria-text").first
                        if header_el.count() > 0 and value_el.count() > 0:
                            header = header_el.inner_text().strip().replace(":", "")
                            val = value_el.inner_text().strip()
                            criteria_dict[header] = val

                    criteria_exp = criteria_dict.get("Seniority level", "Entry level")
                    company_size = criteria_dict.get("Employment type", "Not Mentioned")
                    industry = criteria_dict.get("Industries", "Not Mentioned")

                    if not is_fresher_friendly(job_title, description, criteria_exp):
                        log_scheduler(f"  [{i+1}/{card_count}] SKIP (not fresher friendly): '{job_title}' — Seniority: {criteria_exp}")
                        city_skipped += 1
                        continue

                    skills = extract_skills(description)
                    salary = extract_salary(description)
                    website = extract_website(description)

                    posted_date = safe_extract_any(card, ["time.job-search-card__listdate", "time.job-search-card__listdate--new", "time.base-search-card__listdate", "time"])

                    job_data = {
                        "Company Name": company_name.strip(),
                        "City / Location": city_clean,
                        "Job Title": job_title.strip(),
                        "Experience Required": "0-1 Years",
                        "Required Skills": skills,
                        "Salary Range": salary,
                        "Job Posting Link / URL": clean_url,
                        "Source Platform": "LinkedIn",
                        "Posting Date": posted_date.strip(),
                        "Company Website": website,
                        "Company Size / Industry": f"{company_size} | {industry}" if company_size != "Not Mentioned" else industry,
                        "Search Keyword Used": keyword,
                        "Application Status": "Not Applied"
                    }

                    all_jobs.append(job_data)
                    seen_companies.add(comp_key)
                    stats["jobs_scraped"] += 1
                    city_saved += 1
                    log_scheduler(f"  [{i+1}/{card_count}] ✔ SAVED [{city_saved}]: '{job_title}' @ {company_name} | Skills: {skills}")

                except Exception as card_e:
                    logger.error(f"Error extracting card details: {card_e}")
                    city_skipped += 1

            log_scheduler(f"[CITY DONE] {city_clean}: {city_saved} jobs saved, {city_skipped} skipped. Total so far: {len(all_jobs)}")

        browser.close()
        log_scheduler(f"\n{'='*60}")
        log_scheduler(f"[SCRAPING COMPLETE] Total {len(all_jobs)} jobs scraped across {len(cities)} cities.")
        log_scheduler(f"{'='*60}\n")

    return all_jobs

# OpenRouter / Gemini Email request helper
def generate_cold_email(api_key, company_name, job_title, job_description) -> Optional[str]:
    global stats
    api_key = api_key.strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/shashankjain843",
        "X-Title": "Cold Email Generator"
    }

    system_prompt = (
        "Tu ek professional cold email writer hai. Email short, direct, no fluff, 5-6 lines ka ho. "
        "Candidate ke resume se sirf wahi skills/projects mention karo jo job description se match karte hain. "
        "Generic buzzwords mat use karo. Write the email in English. "
        "Do not use placeholders like [Company Name], [Job Title], [Your Name], or any brackets. "
        "Always replace them with the actual names provided. "
        "Always address the email to 'Dear Hiring Team,' or 'Dear [Company Name] Hiring Team,' instead of 'Dear Hiring Manager,' or 'Dear Recruiter,'. "
        "The response must start directly with 'Subject: [Subject Line]' followed by the email body. "
        "Do not write any introductory or concluding conversation text, just start with Subject:.\n"
        "CRITICAL: Do NOT include the candidate's name (Shashank Jain) in the subject line. Keep it professional. "
        "CRITICAL: Do NOT write any email signature or sign-off at the end (like 'Best regards', 'Sincerely', or your name). "
        "Just end the email text with a concluding sentence. A signature will be appended automatically."
    )

    exp_details = f"Data Analyst Intern at {RESUME_DATA['Experience'][0]['Company']} ({RESUME_DATA['Experience'][0]['Details']})"
    projects_list = []
    for idx, p in enumerate(RESUME_DATA['Projects'], 1):
        projects_list.append(f"{idx}. {p['Name']} (Technologies: {', '.join(p['Technologies'])})")
    projects_str = "\n  ".join(projects_list)

    user_prompt = f"""
Candidate Resume:
- Name: {RESUME_DATA['Name']}
- Target Role: {RESUME_DATA['Role']}
- Contact: Phone: {RESUME_DATA['Contact']['Phone']}, LinkedIn: {RESUME_DATA['Contact']['LinkedIn']}, GitHub: {RESUME_DATA['Contact']['GitHub']}
- Skills: {', '.join(RESUME_DATA['Skills'])}
- Experience: {exp_details}
- Projects:
  {projects_str}

Job Listing details:
- Company Name: {company_name}
- Job Title: {job_title}
- Job Description/Required Skills: {job_description}

Write a personalized cold email from {RESUME_DATA['Name']} to the hiring team at {company_name} for the '{job_title}' position. Match relevant skills and projects from his resume. Make it short (5-6 lines), professional, and direct. Address the email with 'Dear Hiring Team,'. Start with the Subject line.
Do NOT include candidate's name in the subject line. Do NOT write any sign-off or signature block.
"""

    if api_key.startswith("sk-or-"):
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        models = [
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-20b:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "google/gemma-4-31b-it:free",
            "qwen/qwen3-coder:free"
        ]
        log_scheduler(f"[API ROUTE] Routing via OpenRouter API...")
    else:
        api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        models = [
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-pro",
            "gemini-pro-latest"
        ]
        log_scheduler(f"[API ROUTE] Routing directly to Google Gemini API...")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    for model_id in models:
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800  # Crucial to bypass budget checks
        }
        
        attempts = 0
        max_attempts = 3
        delay = 4
        
        while attempts < max_attempts:
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=25)
                
                # Check for 402 budget exhaustion and immediately try next model
                if response.status_code == 402:
                    log_scheduler(f"[WARNING] API 402 (Insufficient Credits / Daily Free Limit reached) on '{model_id}'. Trying next model...")
                    break
                    
                # Check for 429 rate/quota limits and retry with backoff
                if response.status_code == 429:
                    attempts += 1
                    log_scheduler(f"[INFO] API rate limit reached on '{model_id}'. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                    
                if response.status_code == 404:
                    logger.warning(f"Model '{model_id}' returned 404. Trying next model...")
                    break
                    
                response.raise_for_status()
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    stats["emails_generated"] += 1
                    email_text = data["choices"][0]["message"]["content"].strip()
                    # Post-process to ensure "Dear Hiring Team" greeting
                    email_text = re.sub(r'Dear\s+Hiring\s+Manager\b', 'Dear Hiring Team', email_text, flags=re.IGNORECASE)
                    email_text = re.sub(r'Dear\s+Recruiter\b', 'Dear Hiring Team', email_text, flags=re.IGNORECASE)
                    
                    # Ensure programmatic signature is appended at the very end
                    signature = (
                        "\n\nBest regards,\n"
                        "Shashank Jain\n"
                        "+91-7878927128\n"
                        "linkedin.com/in/shashankjain\n"
                        "github.com/shashankjain843"
                    )
                    email_text += signature
                    
                    log_scheduler(f"[INFO] Email generated using model: {model_id}")
                    return email_text
            except Exception as e:
                attempts += 1
                if attempts >= max_attempts:
                    logger.warning(f"Model '{model_id}' failed: {e}. Trying next model...")
                    break
                log_scheduler(f"[WARNING] API request failed on '{model_id}': {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2

    logger.error("API failed: All models exhausted or rate-limited.")
    return None



# Scheduled worker pipeline
def run_scheduled_pipeline():
    log_scheduler("--- STARTING SCHEDULED RUN ---")
    
    # 1. Scrape
    try:
        log_scheduler("Running scheduled job scraper...")
        jobs = scrape_linkedin_jobs()
        
        headers = [
            "Company Name", "City / Location", "Job Title", "Experience Required",
            "Required Skills", "Salary Range", "Job Posting Link / URL",
            "Source Platform", "Posting Date", "Company Website", "Company Size / Industry"
        ]
        
        with open(JOBS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for job in jobs:
                writer.writerow(job)
                
        log_scheduler(f"Successfully scraped {len(jobs)} jobs and updated {JOBS_CSV}.")
        
        # 2. Email generation and SMTP sending
        if jobs:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                log_scheduler("[ERROR] GEMINI_API_KEY or OPENROUTER_API_KEY env variable is missing. Scheduled email generation skipped.")
                return
                
            log_scheduler(f"Running scheduled email generator for {len(jobs)} jobs...")
            success_count = 0
            emails_list = []
            
            for idx, job in enumerate(jobs):
                email_content = generate_cold_email(
                    api_key=api_key,
                    company_name=job["Company Name"],
                    job_title=job["Job Title"],
                    job_description=job["Required Skills"]
                )
                
                if email_content:
                    recipient = find_email_in_text(job["Required Skills"])
                    email_entry = {
                        "Company": job["Company Name"],
                        "Job Title": job["Job Title"],
                        "Generated Email": email_content,
                        "Job URL": job["Job Posting Link / URL"],
                        "Recipient Email": recipient or "Not Found",
                        "Send Status": "Not Sent"
                    }
                    
                    emails_list.append(email_entry)
                    save_emails_atomically(emails_list)
                    success_count += 1
                    
                    if recipient:
                        daily_sent = get_daily_sent_count()
                        if daily_sent >= MAX_DAILY_EMAILS:
                            log_scheduler(f"[LIMIT REACHED] Daily sending limit of {MAX_DAILY_EMAILS} reached. Skipping further sends.")
                        else:
                            subject, body = extract_subject_and_body(email_content)
                            sent_ok = send_email_via_smtp(subject, body, recipient)
                            if sent_ok:
                                email_entry["Send Status"] = "Sent Successfully"
                                save_emails_atomically(emails_list)
                                new_count = increment_daily_sent_count()
                                log_scheduler(f"Daily email count updated to: {new_count}/{MAX_DAILY_EMAILS}")
                                
                                if idx < len(jobs) - 1 and new_count < MAX_DAILY_EMAILS:
                                    delay = random.randint(30, 60)
                                    log_scheduler(f"Waiting {delay}s between SMTP sends...")
                                    time.sleep(delay)
                    
                else:
                    log_scheduler(f"Skipped email generation for {job['Company Name']}")
                    
                # Delay to prevent API rate limits
                time.sleep(2.5)
                
            log_scheduler(f"Successfully generated {success_count} emails and updated database.")
        else:
            log_scheduler("No jobs scraped. Email generation skipped.")
            
    except Exception as e:
        log_scheduler(f"[CRITICAL ERROR] Scheduled run failed: {str(e)}")
        
    log_scheduler("--- SCHEDULED RUN COMPLETED ---")

# APScheduler Startup
scheduler = BackgroundScheduler()
# Avoid duplicate trigger runs in debug reloader
if not os.environ.get("WERKZEUG_RUN_MAIN") and os.environ.get("FLASK_ENV") != "development":
    scheduler.add_job(func=run_scheduled_pipeline, trigger="interval", hours=SCRAPE_INTERVAL_HOURS)
    scheduler.start()
    log_scheduler(f"APScheduler registered background task to run every {SCRAPE_INTERVAL_HOURS} hours.")

# Flask HTTP Routes
@app.route("/")
def home():
    jobs = []
    if os.path.exists(JOBS_JSON):
        try:
            with open(JOBS_JSON, "r", encoding="utf-8") as f:
                jobs = json.load(f)
                jobs_count = len(jobs)
        except:
            pass
    elif os.path.exists(JOBS_CSV):
        try:
            with open(JOBS_CSV, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                jobs = list(reader)
                jobs_count = len(jobs)
        except:
            pass
            
    emails = []
    emails_count = 0
    if os.path.exists(EMAILS_JSON):
        try:
            with open(EMAILS_JSON, "r", encoding="utf-8") as f:
                emails = json.load(f)
                emails_count = len(emails)
        except:
            pass
    elif os.path.exists(EMAILS_CSV):
        try:
            with open(EMAILS_CSV, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                emails = list(reader)
                emails_count = len(emails)
        except:
            pass
            
    scheduler_logs = ""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                scheduler_logs = "".join(f.readlines()[-30:])
        except:
            pass
            
    return render_template(
        "index.html",
        jobs=jobs,
        emails=emails,
        jobs_count=jobs_count,
        emails_count=emails_count,
        scheduler_logs=scheduler_logs,
        scrape_interval=SCRAPE_INTERVAL_HOURS,
        current_keyword="Data Analyst",
        current_cities="Jaipur, Noida, Delhi, Gurgaon",
        scraper_running=scraper_running,
        apply_running=apply_running
    )

@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    global scraper_running
    
    keyword = "Data Analyst"
    cities_str = "Jaipur, Noida, Delhi, Gurgaon"
    
    use_login = False
    if request.method == "POST":
        keyword = request.form.get("keyword", "Data Analyst").strip()
        cities_str = request.form.get("cities", "Jaipur, Noida, Delhi, Gurgaon").strip()
        use_login = request.form.get("use_login") == "on"
    else:
        keyword = request.args.get("keyword", "Data Analyst").strip()
        cities_str = request.args.get("cities", "Jaipur, Noida, Delhi, Gurgaon").strip()
        use_login = request.args.get("use_login") == "1"
        
    cities = [c.strip() for c in cities_str.split(",") if c.strip()]
    
    if request.method == "POST" or request.args.get("trigger") == "1":
        with scraper_lock:
            if scraper_running:
                return redirect(url_for("home"))
            scraper_running = True
            
        def scrape_worker(cities_list, keyword_str, login_flag):
            global scraper_running
            try:
                log_scheduler(f"Triggering manual LinkedIn scrape via background thread for keyword '{keyword_str}' (use_login={login_flag}) in cities: {cities_list}...")
                new_jobs = scrape_linkedin_jobs(cities=cities_list, keyword=keyword_str, use_login=login_flag)
                
                headers = [
                    "Company Name", "City / Location", "Job Title", "Experience Required",
                    "Required Skills", "Salary Range", "Job Posting Link / URL",
                    "Source Platform", "Posting Date", "Company Website", "Company Size / Industry",
                    "Search Keyword Used", "Application Status"
                ]
                
                # Load existing jobs
                existing_jobs = []
                if os.path.exists(JOBS_JSON):
                    try:
                        with open(JOBS_JSON, "r", encoding="utf-8") as f:
                            existing_jobs = json.load(f)
                    except:
                        pass
                elif os.path.exists(JOBS_CSV):
                    try:
                        with open(JOBS_CSV, "r", encoding="utf-8-sig") as f:
                            existing_jobs = list(csv.DictReader(f))
                    except:
                        pass
                
                combined = existing_jobs + new_jobs
                seen_urls = set()
                unique_jobs = []
                for j in combined:
                    if "Application Status" not in j or not j["Application Status"]:
                        j["Application Status"] = "Not Applied"
                    if "Search Keyword Used" not in j or not j["Search Keyword Used"]:
                        j["Search Keyword Used"] = keyword_str
                    
                    url = j.get("Job Posting Link / URL", "").split("?")[0].rstrip("/")
                    if url:
                        if url not in seen_urls:
                            seen_urls.add(url)
                            unique_jobs.append(j)
                    else:
                        key = (j.get("Job Title", "").strip().lower(), j.get("Company Name", "").strip().lower())
                        if key not in seen_urls:
                            seen_urls.add(key)
                            unique_jobs.append(j)
                            
                # Save to JSON
                with open(JOBS_JSON, "w", encoding="utf-8") as f:
                    json.dump(unique_jobs, f, indent=4, ensure_ascii=False)
                    
                # Save to CSV
                with open(JOBS_CSV, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    for j in unique_jobs:
                        row = {h: j.get(h, "") for h in headers}
                        writer.writerow(row)
                log_scheduler(f"[SUCCESS] Background scraper complete. Found {len(new_jobs)} new jobs. Total unique jobs in database: {len(unique_jobs)}")
                
                with scraper_lock:
                    scraper_running = False


                # --- AUTO: Scraping ke baad seedha cold email generate karo ---
                api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
                if api_key and new_jobs:
                    log_scheduler(f"[AUTO EMAIL] Scraping complete. {len(new_jobs)} naye jobs ke liye cold emails generate karna shuru...")
                    try:
                        # Load existing emails JSON
                        all_emails_data = []
                        if os.path.exists(EMAILS_JSON):
                            try:
                                with open(EMAILS_JSON, "r", encoding="utf-8") as f:
                                    all_emails_data = json.load(f)
                            except Exception:
                                all_emails_data = []

                        # If JSON is empty but CSV exists, try reading CSV
                        if not all_emails_data and os.path.exists(EMAILS_CSV):
                            try:
                                with open(EMAILS_CSV, mode="r", newline="", encoding="utf-8-sig") as ef:
                                    all_emails_data = list(csv.DictReader(ef))
                            except Exception:
                                pass

                        already_generated_urls = set()
                        for e in all_emails_data:
                            url = (e.get("Job URL") or e.get("Job Posting Link / URL") or "").split("?")[0].rstrip("/")
                            if url:
                                already_generated_urls.add(url)

                        email_success = 0
                        for idx, job in enumerate(new_jobs):
                            job_url_key = (job.get("Job Posting Link / URL") or "").split("?")[0].rstrip("/")
                            if job_url_key and job_url_key in already_generated_urls:
                                continue

                            log_scheduler(f"[AUTO EMAIL] [{idx+1}/{len(new_jobs)}] Generating for '{job.get('Job Title')}' @ {job.get('Company Name')}...")
                            email_content = generate_cold_email(
                                api_key=api_key,
                                company_name=job.get("Company Name", ""),
                                job_title=job.get("Job Title", ""),
                                job_description=job.get("Required Skills", "")
                            )

                            if email_content:
                                recipient = find_email_in_text(job.get("Required Skills", ""))
                                all_emails_data.append({
                                    "Company": job.get("Company Name"),
                                    "Job Title": job.get("Job Title"),
                                    "Generated Email": email_content,
                                    "Job URL": job.get("Job Posting Link / URL", ""),
                                    "Recipient Email": recipient or "Not Found",
                                    "Send Status": "Not Sent"
                                })
                                # Atomic save at each step to prevent losing progress
                                save_emails_atomically(all_emails_data)
                                already_generated_urls.add(job_url_key)
                                email_success += 1
                                log_scheduler(f"[AUTO EMAIL] [{idx+1}/{len(new_jobs)}] ✔ Email ready")
                            else:
                                log_scheduler(f"[AUTO EMAIL] [{idx+1}/{len(new_jobs)}] ✗ Failed")

                            time.sleep(3.0)  # API rate limit avoid karo


                        log_scheduler(f"[AUTO EMAIL] {email_success} naye cold emails generate ho gaye aur save ho gaye.")
                    except Exception as email_err:
                        log_scheduler(f"[AUTO EMAIL ERROR] Email generation fail hua: {email_err}")
                elif not api_key:
                    log_scheduler("[AUTO EMAIL] GEMINI_API_KEY or OPENROUTER_API_KEY nahi mila. Cold email generation skip.")

            except Exception as e:
                log_scheduler(f"[ERROR] Background scraper failed: {e}")
                logger.exception("Background scrape failed")
            finally:
                with scraper_lock:
                    scraper_running = False
                    
        import threading
        threading.Thread(target=scrape_worker, args=(cities, keyword, use_login)).start()
        
    return redirect(url_for("home"))

@app.route("/scraper-status")
def scraper_status():
    global scraper_running
    return jsonify({"running": scraper_running})

@app.route("/email-status")
def email_status():
    global email_running
    return jsonify({"running": email_running})

@app.route("/generate-emails", methods=["GET", "POST"])
def generate_emails_route():
    global email_running

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY or OPENROUTER_API_KEY not set"}), 500

    if request.method == "POST" or request.args.get("trigger") == "1":
        with email_lock:
            if email_running:
                log_scheduler("[EMAIL GEN] Already running, skipping duplicate trigger.")
                return redirect(url_for("home"))
            email_running = True

        def email_worker():
            global email_running
            try:
                # Load jobs from JSON (more reliable than CSV)
                jobs = []
                if os.path.exists(JOBS_JSON):
                    try:
                        with open(JOBS_JSON, "r", encoding="utf-8") as f:
                            jobs = json.load(f)
                    except Exception:
                        pass
                if not jobs and os.path.exists(JOBS_CSV):
                    try:
                        with open(JOBS_CSV, mode="r", newline="", encoding="utf-8-sig") as f:
                            jobs = list(csv.DictReader(f))
                    except Exception:
                        pass

                if not jobs:
                    log_scheduler("[EMAIL GEN] No jobs found. Please run scraper first.")
                    return

                # Load existing emails data
                all_emails_data = []
                if os.path.exists(EMAILS_JSON):
                    try:
                        with open(EMAILS_JSON, "r", encoding="utf-8") as f:
                            all_emails_data = json.load(f)
                    except Exception:
                        all_emails_data = []

                if not all_emails_data and os.path.exists(EMAILS_CSV):
                    try:
                        with open(EMAILS_CSV, mode="r", newline="", encoding="utf-8-sig") as ef:
                            all_emails_data = list(csv.DictReader(ef))
                    except Exception:
                        pass

                # Load already-generated job URLs to avoid duplicates
                already_generated_urls = set()
                for e in all_emails_data:
                    url = (e.get("Job URL") or "").split("?")[0].rstrip("/")
                    if url:
                        already_generated_urls.add(url)

                pending = [j for j in jobs if (j.get("Job Posting Link / URL") or "").split("?")[0].rstrip("/") not in already_generated_urls]
                log_scheduler(f"[EMAIL GEN] {len(jobs)} total jobs | {len(already_generated_urls)} already done | {len(pending)} to generate now")

                if not pending:
                    log_scheduler("[EMAIL GEN] Saare jobs ke liye emails already generate ho chuki hain.")
                    return

                success_count = 0
                for idx, job in enumerate(pending):
                    comp  = job.get("Company Name", "")
                    title = job.get("Job Title", "")
                    skills = job.get("Required Skills", "")
                    desc  = job.get("Job Description", skills)  # use full description if available
                    url   = job.get("Job Posting Link / URL", "")

                    log_scheduler(f"[EMAIL GEN] [{idx+1}/{len(pending)}] Generating for '{title}' @ {comp}...")
                    email_content = generate_cold_email(api_key, comp, title, desc or skills)

                    if email_content:
                        recipient = find_email_in_text(skills)
                        all_emails_data.append({
                            "Company": comp,
                            "Job Title": title,
                            "Generated Email": email_content,
                            "Job URL": url,
                            "Recipient Email": recipient or "Not Found",
                            "Send Status": "Not Sent"
                        })
                        # Save atomically at each step to prevent losing progress
                        save_emails_atomically(all_emails_data)
                        already_generated_urls.add(url.split("?")[0].rstrip("/"))
                        success_count += 1
                        log_scheduler(f"[EMAIL GEN] [{idx+1}/{len(pending)}] ✔ Email ready for {comp}")
                    else:
                        log_scheduler(f"[EMAIL GEN] [{idx+1}/{len(pending)}] ✗ Failed for {comp}")

                    time.sleep(3.0)  # rate limit


                log_scheduler(f"[EMAIL GEN] Complete! {success_count}/{len(pending)} emails generated. Total saved: {len(all_emails_data)}")

            except Exception as e:
                log_scheduler(f"[EMAIL GEN ERROR] {e}")
                logger.exception("Email generation worker failed")
            finally:
                with email_lock:
                    email_running = False

        threading.Thread(target=email_worker, daemon=True).start()
        return redirect(url_for("home"))


    # GET — just load existing emails
    emails = []
    error = None
    if os.path.exists(EMAILS_JSON):
        try:
            with open(EMAILS_JSON, mode="r", encoding="utf-8") as f:
                emails = json.load(f)
        except Exception as e:
            error = f"Failed to load emails: {e}"
    elif os.path.exists(EMAILS_CSV):
        try:
            with open(EMAILS_CSV, mode="r", newline="", encoding="utf-8-sig") as f:
                emails = list(csv.DictReader(f))
        except Exception as e:
            error = f"Failed to load emails CSV: {e}"

    return render_template("index.html", emails=emails, email_error=error, emails_count=len(emails), apply_running=apply_running, email_running=email_running)

def update_email_send_status(job_url, email_address, status):
    normalized_url = job_url.split("?")[0].rstrip("/")
    
    # Load existing emails
    emails = []
    if os.path.exists(EMAILS_JSON):
        try:
            with open(EMAILS_JSON, "r", encoding="utf-8") as f:
                emails = json.load(f)
        except Exception:
            pass
            
    if not emails and os.path.exists(EMAILS_CSV):
        try:
            with open(EMAILS_CSV, "r", newline="", encoding="utf-8-sig") as f:
                emails = list(csv.DictReader(f))
        except Exception:
            pass

    updated = False
    for email in emails:
        url = (email.get("Job URL") or email.get("Job Posting Link / URL") or "").split("?")[0].rstrip("/")
        if url and url == normalized_url:
            email["Recipient Email"] = email_address
            email["Send Status"] = status
            updated = True
            
    if updated:
        save_emails_atomically(emails)


@app.route("/send-email", methods=["POST"])
def send_email_route():
    recipient_email = request.form.get("recipient_email", "").strip()
    company = request.form.get("company", "").strip()
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    job_url = request.form.get("job_url", "").strip()
    
    if not recipient_email or "@" not in recipient_email:
        return render_template("index.html", email_error="Please provide a valid recipient email.", emails=[])
        
    if not subject or not body:
        return render_template("index.html", email_error="Email subject or body cannot be empty.", emails=[])
        
    sent_ok = send_email_via_smtp(subject, body, recipient_email)
    if sent_ok:
        update_email_send_status(job_url, recipient_email, "Sent Successfully")
        log_scheduler(f"Successfully sent cold email to {company} HR: {recipient_email}")
    else:
        update_email_send_status(job_url, recipient_email, "Send Failed")
        log_scheduler(f"[ERROR] Failed to send cold email to {company} HR: {recipient_email}")
        
    return redirect(url_for("home"))

from apply_helper import auto_apply_to_job, auto_apply_batch, update_job_status_in_files

@app.route("/apply", methods=["POST"])
def apply_job_route():
    job_url = request.form.get("job_url", "").strip()
    company = request.form.get("company", "Unknown").strip()
    title = request.form.get("title", "Unknown").strip()
    
    if job_url:
        try:
            update_job_status_in_files(job_url, "Applying...")
            
            # Execute in a thread or inline. Since this is Flask local, running inline is OK, 
            # but a background thread prevents blocking the page load.
            def apply_thread():
                try:
                    status = auto_apply_to_job(job_url, company, title)
                    update_job_status_in_files(job_url, status)
                except Exception as e:
                    logger.error(f"Error in apply helper: {e}")
                    update_job_status_in_files(job_url, "Failed")
            
            import threading
            threading.Thread(target=apply_thread).start()
            
        except Exception as e:
            logger.error(f"Failed to start apply worker: {e}")
            update_job_status_in_files(job_url, "Failed")
            
    return redirect(url_for("home"))

@app.route("/auto-apply-all", methods=["POST"])
def auto_apply_all_route():
    global apply_running
    with apply_thread_lock:
        if apply_running:
            log_scheduler("[AUTO-APPLY ALL] Already running. Skipping.")
            return redirect(url_for("home"))
        apply_running = True

    def auto_apply_worker():
        global apply_running
        try:
            # Load all jobs — prefer JSON (has more fields)
            jobs_list = []
            if os.path.exists(JOBS_JSON):
                try:
                    with open(JOBS_JSON, "r", encoding="utf-8") as f:
                        jobs_list = json.load(f)
                except Exception:
                    pass
            if not jobs_list and os.path.exists(JOBS_CSV):
                with open(JOBS_CSV, "r", encoding="utf-8-sig") as f:
                    jobs_list = list(csv.DictReader(f))

            # Sirf "Not Applied" jobs filter karo
            to_apply = [
                j for j in jobs_list
                if not j.get("Application Status", "").strip()
                or j.get("Application Status", "").strip() in ["Not Applied", ""]
            ]

            log_scheduler(f"[AUTO-APPLY ALL] {len(to_apply)} jobs pending. Processing first 5 using single browser session...")

            if not to_apply:
                log_scheduler("[AUTO-APPLY ALL] No pending jobs to apply.")
                return

            # Mark all as "Applying..." before starting
            for job in to_apply[:5]:
                url = job.get("Job Posting Link / URL") or job.get("Job URL", "")
                if url:
                    update_job_status_in_files(url, "Applying...")

            # Single browser session for all 5 jobs
            results = auto_apply_batch(to_apply, max_jobs=5)

            for job_url, status in results:
                if job_url:
                    update_job_status_in_files(job_url, status)
                    log_scheduler(f"[AUTO-APPLY ALL] {job_url.split('/')[-1][:30]} → {status}")

            applied = sum(1 for _, s in results if s == "Applied")
            log_scheduler(f"[AUTO-APPLY ALL] Done. Applied: {applied}/{len(results)}")

        except Exception as e:
            log_scheduler(f"[AUTO-APPLY ALL] Worker error: {e}")
            logger.exception("Auto apply all failed")
        finally:
            with apply_thread_lock:
                apply_running = False

    threading.Thread(target=auto_apply_worker, daemon=True).start()
    return redirect(url_for("home"))


@app.route("/apply-status")
def apply_status():
    global apply_running
    return jsonify({"running": apply_running})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
