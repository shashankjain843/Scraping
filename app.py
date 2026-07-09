import os
import csv
import time
import random
import re
import sys
import logging
import datetime
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from playwright.sync_api import sync_playwright
from apscheduler.schedulers.background import BackgroundScheduler

from typing import Optional, List
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
JOBS_CSV = "linkedin_python_jobs_jaipur.csv"
EMAILS_CSV = "generated_cold_emails.csv"
LOG_FILE = "scheduler_log.txt"

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

def is_valid_python_title(title):
    title_lower = title.lower()
    return "python" in title_lower or "django" in title_lower or "flask" in title_lower or "fastapi" in title_lower or "backend" in title_lower

def is_fresher_friendly(title, description, criteria_exp):
    title_lower = title.lower()
    desc_lower = description.lower()
    crit_lower = criteria_exp.lower()
    
    # 1. Exclude seniority keywords in title
    exclude_title_words = ["senior", "lead", "sr", "principal", "manager", "head", "architect", "expert", "specialist"]
    for word in exclude_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
            return False
            
    # 2. Check criteria if present
    if "mid-senior" in crit_lower or "director" in crit_lower or "executive" in crit_lower:
        return False
        
    # 3. Check for strong fresher signals to override exclusions
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
            
    # 4. Check description for experience requirements of 2 or more years
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

# Playwright LinkedIn Scraper core
def scrape_linkedin_jobs() -> list:
    all_jobs = []
    seen_companies = set()
    target_job_count = 30 # Kept at 30 to run reliably within web timeouts on Render

    with sync_playwright() as p:
        # headless=True is mandatory for Render (no GUI)
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Scrape jobs in Jaipur
        city_name = "Jaipur"
        city_query = "Jaipur, Rajasthan, India"
        url_keyword = "Python"
        url_location = city_query.replace(" ", "%20").replace(",", "%2C")
        search_url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location={url_location}&distance=25"

        page.goto(search_url, timeout=60000)
        page.wait_for_timeout(5000)

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
                if no_change_iterations > 8:
                    break
            else:
                no_change_iterations = 0
                last_count = count

            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            page.wait_for_timeout(random.randint(1500, 2000))

            see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
            if see_more_btn.count() > 0 and see_more_btn.is_visible():
                try:
                    see_more_btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(2000)
                except:
                    pass

        # Extract info
        job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
        card_count = min(job_cards.count(), target_job_count * 2)

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

                if not is_valid_python_title(job_title):
                    continue

                comp_key = company_name.strip().lower()
                if comp_key in seen_companies:
                    continue

                # Load job details
                card.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                card.click(force=True, timeout=5000)
                page.wait_for_timeout(2000)

                show_more_desc = page.locator("button.show-more-less-html__button, button:has-text('Show more'), button:has-text('See more')").first
                if show_more_desc.count() > 0 and show_more_desc.is_visible():
                    try:
                        show_more_desc.click(force=True, timeout=2000)
                        page.wait_for_timeout(500)
                    except:
                        pass

                description = "Not Mentioned"
                desc_el = page.locator("div.show-more-less-html__markup, .description__text").first
                if desc_el.count() > 0:
                    description = desc_el.inner_text().strip()

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
                    "City / Location": city_name,
                    "Job Title": job_title.strip(),
                    "Experience Required": "0-1 Years",
                    "Required Skills": skills,
                    "Salary Range": salary,
                    "Job Posting Link / URL": clean_url,
                    "Source Platform": "LinkedIn",
                    "Posting Date": posted_date.strip(),
                    "Company Website": website,
                    "Company Size / Industry": f"{company_size} | {industry}" if company_size != "Not Mentioned" else industry
                }

                all_jobs.append(job_data)
                seen_companies.add(comp_key)

            except Exception as card_e:
                logger.error(f"Error extracting card details: {card_e}")

        browser.close()

    return all_jobs

# OpenRouter Email request helper
def generate_cold_email(api_key, company_name, job_title, job_description) -> Optional[str]:
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
        "Do not write any introductory or concluding conversation text, just start with Subject:."
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
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"OpenRouter API failed: {e}")
    return None

# Scheduler logging helper
def log_scheduler(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to log scheduler: {e}")

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
        
        # 2. Email generation
        if jobs:
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                log_scheduler("[ERROR] OPENROUTER_API_KEY env variable is missing. Scheduled email generation skipped.")
                return
                
            log_scheduler(f"Running scheduled OpenRouter email generator for {len(jobs)} jobs...")
            success_count = 0
            
            with open(EMAILS_CSV, "w", newline="", encoding="utf-8-sig") as out_f:
                writer = csv.writer(out_f)
                writer.writerow(["Company", "Job Title", "Generated Email", "Job URL"])
                
                for idx, job in enumerate(jobs):
                    email_content = generate_cold_email(
                        api_key=api_key,
                        company_name=job["Company Name"],
                        job_title=job["Job Title"],
                        job_description=job["Required Skills"]
                    )
                    
                    if email_content:
                        writer.writerow([job["Company Name"], job["Job Title"], email_content, job["Job Posting Link / URL"]])
                        out_f.flush()
                        success_count += 1
                    
                    # Delay to prevent rate limits
                    time.sleep(2.0)
                    
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
    jobs_count = 0
    if os.path.exists(JOBS_CSV):
        try:
            with open(JOBS_CSV, "r", encoding="utf-8") as f:
                jobs_count = sum(1 for _ in f) - 1 # exclude header
        except:
            pass
            
    emails_count = 0
    if os.path.exists(EMAILS_CSV):
        try:
            with open(EMAILS_CSV, "r", encoding="utf-8") as f:
                emails_count = sum(1 for _ in f) - 1 # exclude header
        except:
            pass
            
    scheduler_logs = ""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                scheduler_logs = "".join(f.readlines()[-30:]) # last 30 log lines
        except:
            pass
            
    return render_template(
        "index.html",
        jobs_count=jobs_count,
        emails_count=emails_count,
        scheduler_logs=scheduler_logs,
        scrape_interval=SCRAPE_INTERVAL_HOURS
    )

@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    error = None
    jobs = []
    
    if request.method == "POST" or request.args.get("trigger") == "1":
        try:
            logger.info("Triggering manual LinkedIn scrape...")
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
            logger.info(f"Scraped {len(jobs)} jobs successfully.")
            
        except FileNotFoundError as fnf:
            error = str(fnf)
        except ValueError as val_e:
            error = str(val_e)
        except Exception as e:
            error = f"LinkedIn Scraper failed (LinkedIn captcha/block or timeout): {str(e)}"
            logger.exception("Manual scrape failed")
    else:
        # Load from existing file if GET request
        if os.path.exists(JOBS_CSV):
            try:
                with open(JOBS_CSV, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    jobs = list(reader)
            except Exception as e:
                error = f"Failed to load existing jobs CSV: {e}"
                
    return render_template("index.html", jobs=jobs, scrape_error=error, jobs_count=len(jobs))

@app.route("/generate-emails", methods=["GET", "POST"])
def generate_emails_route():
    error = None
    emails = []
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        error = "OPENROUTER_API_KEY environment variable is not set. Please set it in your environment or Render dashboard."
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
                writer.writerow(["Company", "Job Title", "Generated Email", "Job URL"])
                
                for idx, job in enumerate(jobs):
                    comp = job.get("Company Name")
                    title = job.get("Job Title")
                    skills = job.get("Required Skills", "")
                    url = job.get("Job Posting Link / URL", "")
                    
                    email_content = generate_cold_email(api_key, comp, title, skills)
                    
                    if email_content:
                        writer.writerow([comp, title, email_content, url])
                        out_f.flush()
                        success_count += 1
                        
                        emails.append({
                            "Company": comp,
                            "Job Title": title,
                            "Generated Email": email_content,
                            "Job URL": url
                        })
                    time.sleep(2.0) # rate limiting delay
                    
        except Exception as e:
            error = f"Error generating emails: {str(e)}"
            logger.exception("Email generation failed")
    else:
        # Load from existing file if GET request
        if os.path.exists(EMAILS_CSV):
            try:
                with open(EMAILS_CSV, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    emails = list(reader)
            except Exception as e:
                error = f"Failed to load existing emails CSV: {e}"
                
    return render_template("index.html", emails=emails, email_error=error, emails_count=len(emails))

if __name__ == "__main__":
    # Local fallback startup
    app.run(host="127.0.0.1", port=8000, debug=True)
