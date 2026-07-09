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

# Default Resume Data for Cold Email Generator
RESUME_DATA = {
    "Name": "Shashank Jain",
    "Role": "Data Analyst",
    "Skills": ["Python", "SQL", "Pandas", "NumPy", "Power BI", "Tableau", "PostgreSQL", "MongoDB", "FastAPI", "LangChain", "RAG", "EDA"],
    "Experience": [
        {
            "Company": "Appic Software Development",
            "Details": "Power BI dashboards, 30% reporting effort reduction, EDA on 10,000+ rows"
        }
    ],
    "Projects": [
        {
            "Name": "Sales & Revenue Performance Analysis",
            "Technologies": ["Python", "SQL", "Streamlit", "Holt's forecasting"],
            "Details": "Sales & Revenue Performance Analysis using Python, SQL, Streamlit, Holt's forecasting"
        },
        {
            "Name": "Healthcare Analytics Dashboard",
            "Technologies": ["Python", "Pandas", "PostgreSQL", "XGBoost", "Streamlit"],
            "Details": "Healthcare Analytics Dashboard using Python, Pandas, PostgreSQL, XGBoost, Streamlit"
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
    print(log_entry.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        # Also write to logs.txt
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to log scheduler: {e}")

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
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = smtp_email
        msg["To"] = recipient_email
        
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
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

def login_to_linkedin(page, email, password):
    log_scheduler("[INFO] Starting LinkedIn login process...")
    try:
        def goto_login():
            page.goto("https://www.linkedin.com/login", timeout=60000)
            page.wait_for_load_state("networkidle")
        
        retry_action(goto_login, "Navigate to LinkedIn login page")
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
            
        retry_action(click_submit, "Submit LinkedIn login form")
        check_captcha(page)
        
        if "feed" in page.url or "checkpoint" not in page.url:
            log_scheduler("[SUCCESS] Logged in to LinkedIn successfully.")
        else:
            log_scheduler(f"[WARNING] Login might have requested security check. Current URL: {page.url}")
            check_captcha(page)
    except Exception as login_err:
        log_scheduler(f"[ERROR] Failed to login to LinkedIn: {login_err}")

# Playwright LinkedIn Scraper core
def scrape_linkedin_jobs(cities=None, keyword="Data Analyst") -> list:
    import urllib.parse
    global stats
    all_jobs = []
    seen_companies = set()
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Log in if credentials available
        linkedin_email = os.environ.get("LINKEDIN_EMAIL")
        linkedin_password = os.environ.get("LINKEDIN_PASSWORD")
        if linkedin_email and linkedin_password:
            login_to_linkedin(page, linkedin_email, linkedin_password)

        for city in cities:
            city_clean = city.strip()
            city_query = city_mappings.get(city_clean, f"{city_clean}, India")
            url_keyword = urllib.parse.quote(keyword)
            url_location = urllib.parse.quote(city_query)
            search_url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location={url_location}&distance=25"

            log_scheduler(f"Scraping city: {city_clean} ({city_query}) for keyword '{keyword}'...")
            
            def goto_search():
                page.goto(search_url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
            try:
                retry_action(goto_search, f"Navigate to Search URL for {city_clean}")
                page.wait_for_timeout(5000)
            except Exception as e:
                log_scheduler(f"[ERROR] Failed to load search page for {city_clean}: {e}")
                continue

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

            # Extract info
            job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
            card_count = min(job_cards.count(), target_job_count * 2)
            log_scheduler(f"Found {job_cards.count()} job cards for {city_clean}. Processing top {card_count}...")

            for i in range(card_count):
                card = job_cards.nth(i)
                try:
                    job_title = safe_extract_any(card, ["h3.base-search-card__title", "h3.job-search-card__title", ".base-search-card__title", "h3"])
                    company_name = safe_extract_any(card, ["h4.base-search-card__subtitle", "a.hidden-nested-link", ".base-search-card__subtitle", "h4"])
                    location_str = safe_extract_any(card, ["span.job-search-card__location", ".job-search-card__location", "span"])
                    job_url = safe_extract_any(card, ["a.base-card__full-link", "a.job-search-card__link", "a"], attribute="href")

                    if not job_url or not job_title or not company_name:
                        continue

                    clean_url = job_url.split("?")[0]

                    if not is_valid_title(job_title, keyword):
                        continue

                    comp_key = company_name.strip().lower()
                    if comp_key in seen_companies:
                        continue

                    # Details extraction with retry
                    def extract_card_details():
                        card.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        card.wait_for(state="visible", timeout=10000)
                        card.click(force=True, timeout=5000)
                        page.wait_for_timeout(2000)

                        show_more_desc = page.locator("button.show-more-less-html__button, button:has-text('Show more'), button:has-text('See more')").first
                        if show_more_desc.count() > 0 and show_more_desc.is_visible():
                            try:
                                sm_sel = "button.show-more-less-html__button" if page.locator("button.show-more-less-html__button").count() > 0 else "button:has-text('Show more')"
                                page.wait_for_selector(sm_sel, state="visible", timeout=10000)
                                show_more_desc.click(force=True, timeout=2000)
                                page.wait_for_timeout(500)
                            except:
                                pass

                        description = "Not Mentioned"
                        desc_el = page.locator("div.show-more-less-html__markup, .description__text").first
                        if desc_el.count() > 0:
                            description = desc_el.inner_text().strip()
                        return description

                    try:
                        description = retry_action(extract_card_details, f"Extract details for {job_title} at {company_name}")
                    except Exception as card_err:
                        log_scheduler(f"[WARNING] Skipping card {i} due to details extraction failure: {card_err}")
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

                except Exception as card_e:
                    logger.error(f"Error extracting card details: {card_e}")

        browser.close()

    return all_jobs

# OpenRouter Email request helper
def generate_cold_email(api_key, company_name, job_title, job_description) -> Optional[str]:
    global stats
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
        "The response must start directly with 'Subject: [Subject Line]' followed by the email body. "
        "Do not write any introductory or concluding conversation text, just start with Subject:.\n"
        "CRITICAL: Do NOT use any spam-trigger words or phrases such as 'Free', 'Guaranteed', "
        "'Act now', 'Limited time', 'Click here', 'Risk-free', 'Special offer', 'Click below', or 'Hurry'. "
        "Subject lines should be unique, professional, and personalized to the role and company."
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

Write a personalized cold email from {RESUME_DATA['Name']} to the recruiter or hiring manager at {company_name} for the '{job_title}' position. Match relevant skills and projects from his resume. Make it short (5-6 lines), professional, and direct. Start with the Subject line.
"""

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            stats["emails_generated"] += 1
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"OpenRouter API failed: {e}")
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
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                log_scheduler("[ERROR] OPENROUTER_API_KEY env variable is missing. Scheduled email generation skipped.")
                return
                
            log_scheduler(f"Running scheduled OpenRouter email generator for {len(jobs)} jobs...")
            success_count = 0
            
            with open(EMAILS_CSV, "w", newline="", encoding="utf-8-sig") as out_f:
                writer = csv.writer(out_f)
                writer.writerow(["Company", "Job Title", "Generated Email", "Job URL", "Recipient Email"])
                
                for idx, job in enumerate(jobs):
                    email_content = generate_cold_email(
                        api_key=api_key,
                        company_name=job["Company Name"],
                        job_title=job["Job Title"],
                        job_description=job["Required Skills"]
                    )
                    
                    if email_content:
                        recipient = find_email_in_text(job["Required Skills"])
                        writer.writerow([job["Company Name"], job["Job Title"], email_content, job["Job Posting Link / URL"], recipient or "Not Found"])
                        out_f.flush()
                        success_count += 1
                        
                        if recipient:
                            daily_sent = get_daily_sent_count()
                            if daily_sent >= MAX_DAILY_EMAILS:
                                log_scheduler(f"[LIMIT REACHED] Daily sending limit of {MAX_DAILY_EMAILS} reached. Skipping further sends.")
                                break
                            
                            subject, body = extract_subject_and_body(email_content)
                            sent_ok = send_email_via_smtp(subject, body, recipient)
                            if sent_ok:
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
                    
            log_scheduler(f"Successfully generated {success_count} emails and updated {EMAILS_CSV}.")
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
            with open(JOBS_CSV, "r", encoding="utf-8-sig") as f:
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
            with open(EMAILS_CSV, "r", encoding="utf-8-sig") as f:
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
        current_cities="Jaipur, Noida, Delhi, Gurgaon"
    )

@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    error = None
    jobs = []
    
    keyword = "Data Analyst"
    cities_str = "Jaipur, Noida, Delhi, Gurgaon"
    
    if request.method == "POST":
        keyword = request.form.get("keyword", "Data Analyst").strip()
        cities_str = request.form.get("cities", "Jaipur, Noida, Delhi, Gurgaon").strip()
    else:
        keyword = request.args.get("keyword", "Data Analyst").strip()
        cities_str = request.args.get("cities", "Jaipur, Noida, Delhi, Gurgaon").strip()
        
    cities = [c.strip() for c in cities_str.split(",") if c.strip()]
    
    if request.method == "POST" or request.args.get("trigger") == "1":
        try:
            log_scheduler(f"Triggering manual LinkedIn scrape via Flask route for keyword '{keyword}' in cities: {cities}...")
            new_jobs = scrape_linkedin_jobs(cities=cities, keyword=keyword)
            
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
                    j["Search Keyword Used"] = keyword
                
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
                    
            log_scheduler(f"Scraped and merged. Total unique jobs in database: {len(unique_jobs)}")
            jobs = unique_jobs
            
        except FileNotFoundError as fnf:
            error = str(fnf)
        except ValueError as val_e:
            error = str(val_e)
        except Exception as e:
            error = f"LinkedIn Scraper failed (LinkedIn captcha/block or timeout): {str(e)}"
            logger.exception("Manual scrape failed")
    else:
        if os.path.exists(JOBS_JSON):
            try:
                with open(JOBS_JSON, "r", encoding="utf-8") as f:
                    jobs = json.load(f)
            except:
                pass
        elif os.path.exists(JOBS_CSV):
            try:
                with open(JOBS_CSV, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    jobs = list(reader)
            except Exception as e:
                error = f"Failed to load existing jobs CSV: {e}"
                
    return render_template(
        "index.html",
        jobs=jobs,
        scrape_error=error,
        jobs_count=len(jobs),
        current_keyword=keyword,
        current_cities=cities_str
    )

@app.route("/generate-emails", methods=["GET", "POST"])
def generate_emails_route():
    error = None
    emails = []
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        error = "OPENROUTER_API_KEY environment variable is not set. Please set it in your environment."
        return render_template("index.html", email_error=error)
        
    if request.method == "POST" or request.args.get("trigger") == "1":
        if not os.path.exists(JOBS_CSV):
            error = "No scraped jobs CSV found. Please run the job scraper first."
            return render_template("index.html", email_error=error)
            
        jobs = []
        try:
            with open(JOBS_CSV, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                jobs = list(reader)
        except Exception as e:
            error = f"Failed to read scraped jobs file: {str(e)}"
            return render_template("index.html", email_error=error)
            
        if not jobs:
            error = "Scraped jobs CSV file is empty. Please run the scraper first."
            return render_template("index.html", email_error=error)
            
        success_count = 0
        try:
            with open(EMAILS_CSV, "w", newline="", encoding="utf-8-sig") as out_f:
                writer = csv.writer(out_f)
                writer.writerow(["Company", "Job Title", "Generated Email", "Job URL", "Recipient Email", "Send Status"])
                
                for idx, job in enumerate(jobs):
                    comp = job.get("Company Name")
                    title = job.get("Job Title")
                    skills = job.get("Required Skills", "")
                    url = job.get("Job Posting Link / URL", "")
                    
                    email_content = generate_cold_email(api_key, comp, title, skills)
                    
                    if email_content:
                        recipient = find_email_in_text(skills)
                        writer.writerow([comp, title, email_content, url, recipient or "Not Found", "Not Sent"])
                        out_f.flush()
                        success_count += 1
                        
                        emails.append({
                            "Company": comp,
                            "Job Title": title,
                            "Generated Email": email_content,
                            "Job URL": url,
                            "Recipient Email": recipient or "Not Found",
                            "Send Status": "Not Sent"
                        })
                        
                        # SMTP sending if recipient email found and credentials configured
                        if recipient:
                            daily_sent = get_daily_sent_count()
                            if daily_sent >= MAX_DAILY_EMAILS:
                                log_scheduler(f"[LIMIT REACHED] Daily sending limit of {MAX_DAILY_EMAILS} reached. Saving drafts only.")
                            else:
                                subject, body = extract_subject_and_body(email_content)
                                sent_ok = send_email_via_smtp(subject, body, recipient)
                                if sent_ok:
                                    new_count = increment_daily_sent_count()
                                    log_scheduler(f"Daily email count updated to: {new_count}/{MAX_DAILY_EMAILS}")
                                    
                                    # Wait 30-60 seconds for deliverability before continuing
                                    if idx < len(jobs) - 1 and new_count < MAX_DAILY_EMAILS:
                                        delay = random.randint(30, 60)
                                        log_scheduler(f"Waiting {delay}s before next SMTP send...")
                                        time.sleep(delay)
                        
                    # Delay to prevent API rate limits
                    time.sleep(2.5)
                    
            with open(EMAILS_JSON, "w", encoding="utf-8") as json_f:
                json.dump(emails, json_f, indent=4, ensure_ascii=False)
                    
        except Exception as e:
            error = f"Error generating emails: {str(e)}"
            logger.exception("Email generation failed")
    else:
        if os.path.exists(EMAILS_JSON):
            try:
                with open(EMAILS_JSON, mode="r", encoding="utf-8") as f:
                    emails = json.load(f)
            except Exception as e:
                error = f"Failed to load existing emails JSON: {e}"
        elif os.path.exists(EMAILS_CSV):
            try:
                with open(EMAILS_CSV, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    emails = list(reader)
            except Exception as e:
                error = f"Failed to load existing emails CSV: {e}"
                
    return render_template("index.html", emails=emails, email_error=error, emails_count=len(emails))

def update_email_send_status(job_url, email_address, status):
    normalized_url = job_url.split("?")[0].rstrip("/")
    
    # Update JSON
    if os.path.exists(EMAILS_JSON):
        try:
            with open(EMAILS_JSON, "r", encoding="utf-8") as f:
                emails = json.load(f)
            updated = False
            for email in emails:
                url = email.get("Job URL", "") or email.get("url", "") or email.get("Job Posting Link / URL", "")
                if url and url.split("?")[0].rstrip("/") == normalized_url:
                    email["Recipient Email"] = email_address
                    email["Send Status"] = status
                    updated = True
            if updated:
                with open(EMAILS_JSON, "w", encoding="utf-8") as f:
                    json.dump(emails, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to update email status in JSON: {e}")

    # Update CSV
    if os.path.exists(EMAILS_CSV):
        try:
            rows = []
            headers = []
            with open(EMAILS_CSV, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = list(reader.fieldnames or [])
                if "Recipient Email" not in headers:
                    headers.append("Recipient Email")
                if "Send Status" not in headers:
                    headers.append("Send Status")
                rows = list(reader)
                
            updated = False
            for row in rows:
                url = row.get("Job URL", "") or row.get("Job Posting Link / URL", "")
                if url and url.split("?")[0].rstrip("/") == normalized_url:
                    row["Recipient Email"] = email_address
                    row["Send Status"] = status
                    updated = True
                    
            if updated:
                with open(EMAILS_CSV, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    for r in rows:
                        row_to_write = {h: r.get(h, "") for h in headers}
                        writer.writerow(row_to_write)
        except Exception as e:
            logger.error(f"Failed to update email status in CSV: {e}")

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

from apply_helper import auto_apply_to_job, update_job_status_in_files

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

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
