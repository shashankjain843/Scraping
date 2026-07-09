import os
import sys
import json
import uuid
import asyncio
import logging
import datetime
import threading
import csv
import requests
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query as FastAPIQuery
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

# Reconfigure stdout for UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_api")

app = FastAPI(title="LinkedIn Jobs & Cold Email API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
tasks_db: Dict[str, Dict[str, Any]] = {}

DEFAULT_RESUME_DATA = {
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

DEFAULT_CONFIG = {
    "resume_data": DEFAULT_RESUME_DATA,
    "api_key": "",
    "model_name": "openai/gpt-4o-mini"
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG
    
    # Try importing API key from .env if present
    env_api_key = ""
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        env_api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        except:
            pass
            
    config = DEFAULT_CONFIG.copy()
    config["api_key"] = env_api_key
    save_config(config)
    return config

def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

class TaskTracker:
    def __init__(self, task_id: str, task_type: str):
        self.task_id = task_id
        self.task_type = task_type
        self.status = "running"
        self.progress = 0.0
        self.progress_text = "Task initialized..."
        self.logs = []
        self.output_file = None
        self.error = None
        self.created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_db()

    def add_log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        self._update_db()
        logger.info(f"[{self.task_id}] {message}")

    def update_progress(self, progress: float, text: str):
        self.progress = round(progress, 1)
        self.progress_text = text
        self._update_db()

    def complete(self, output_file: Optional[str] = None):
        self.status = "completed"
        self.progress = 100.0
        self.progress_text = "Task finished successfully!"
        self.output_file = output_file
        self.add_log("✅ Task completed successfully.")
        self._update_db()

    def fail(self, error_msg: str):
        self.status = "failed"
        self.error = error_msg
        self.progress_text = "Task failed."
        self.add_log(f"❌ Task failed: {error_msg}")
        self._update_db()

    def _update_db(self):
        tasks_db[self.task_id] = {
            "task_id": self.task_id,
            "type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "progress_text": self.progress_text,
            "logs": self.logs,
            "output_file": self.output_file,
            "error": self.error,
            "created_at": self.created_at
        }

# XML spreadsheet output helper
def write_excel_xml(filepath, data_list, headers, sheet_name):
    xml_header = f"""<?xml version="1.0" encoding="utf-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-excel"
 xmlns:o="urn:schemas-microsoft-excel:office"
 xmlns:x="urn:schemas-microsoft-excel:excel"
 xmlns:ss="urn:schemas-microsoft-excel:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Worksheet ss:Name="{sheet_name}">
  <Table>
"""
    xml_footer = """  </Table>
 </Worksheet>
</Workbook>
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(xml_header)
        f.write("   <Row>\n")
        for h in headers:
            h_esc = h.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            f.write(f'    <Cell><Data ss:Type="String">{h_esc}</Data></Cell>\n')
        f.write("   </Row>\n")
        
        for job in data_list:
            f.write("   <Row>\n")
            for h in headers:
                val = job.get(h, "")
                if val is None:
                    val = ""
                val_esc = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
                f.write(f'    <Cell><Data ss:Type="String">{val_esc}</Data></Cell>\n')
            f.write("   </Row>\n")
        f.write(xml_footer)

# OpenRouter Email request helper
def generate_cold_email_custom(api_key, company_name, job_title, job_description, resume_data, model_name):
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

    exp_details = ""
    if resume_data.get("Experience") and len(resume_data["Experience"]) > 0:
        exp = resume_data["Experience"][0]
        exp_details = f"Data Analyst Intern at {exp.get('Company')} ({exp.get('Details')})"
        
    projects_list = []
    for idx, p in enumerate(resume_data.get("Projects", []), 1):
        projects_list.append(f"{idx}. {p.get('Name')} (Technologies: {', '.join(p.get('Technologies', []))})")
    projects_str = "\n  ".join(projects_list)

    user_prompt = f"""
Candidate Resume:
- Name: {resume_data.get('Name')}
- Target Role: {resume_data.get('Role')}
- Contact: Phone: {resume_data.get('Contact', {}).get('Phone')}, LinkedIn: {resume_data.get('Contact', {}).get('LinkedIn')}, GitHub: {resume_data.get('Contact', {}).get('GitHub')}
- Skills: {', '.join(resume_data.get('Skills', []))}
- Experience: {exp_details}
- Projects:
  {projects_str}

Job Listing details:
- Company Name: {company_name}
- Job Title: {job_title}
- Job Description/Required Skills: {job_description}

Write a personalized cold email from {resume_data.get('Name')} to the recruiter or hiring manager at {company_name} for the '{job_title}' position. Match relevant skills and projects from his resume. Make it short (5-6 lines), professional, and direct. Start with the Subject line.
"""

    payload = {
        "model": model_name,
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
        logger.error(f"API call failed: {e}")
    return None

# Task Workers (Threads)
def job_scraper_worker(task_id: str, cities_list: List[Dict[str, str]], target_job_count: int, headless: bool):
    tracker = TaskTracker(task_id, "job_scraper")
    tracker.add_log("Starting LinkedIn Scraper pipeline...")
    
    import random
    from playwright.sync_api import sync_playwright
    from scrape_linkedin_jobs import (
        safe_extract_any,
        is_valid_title,
        is_fresher_friendly,
        extract_skills,
        extract_salary,
        extract_website
    )

    all_jobs = []
    seen_companies = set()
    total_cities = len(cities_list)

    try:
        with sync_playwright() as p:
            tracker.add_log(f"Launching Playwright Chromium (headless={headless})...")
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            for c_idx, city in enumerate(cities_list):
                city_name = city["name"]
                city_query = city["query"]
                
                tracker.update_progress((c_idx / total_cities) * 100, f"Scanning {city_name}...")
                tracker.add_log(f"Scraping city: {city_name} ({city_query})")

                url_keyword = "%28%22Data%20Analyst%22%20OR%20%22Data%20Analytics%22%29"
                url_location = city_query.replace(" ", "%20").replace(",", "%2C")
                search_url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location={url_location}&distance=25"

                tracker.add_log(f"Navigating to {city_name} job boards...")
                try:
                    page.goto(search_url, timeout=60000)
                    page.wait_for_timeout(5000)
                except Exception as e:
                    tracker.add_log(f"Error loading search results for {city_name}: {str(e)}")
                    continue

                # Scrolling logic
                tracker.add_log("Scrolling to load job cards...")
                last_count = 0
                no_change_iterations = 0

                while True:
                    # Clear overlay popups
                    try:
                        page.evaluate("""
                            document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"]').forEach(el => el.remove());
                            document.body.style.overflow = 'auto';
                            if (document.body.classList.contains('modal-open')) {
                                document.body.classList.remove('modal-open');
                            }
                        """)
                    except:
                        pass

                    job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
                    count = job_cards.count()
                    tracker.add_log(f"[{city_name}] Loaded {count} job cards.")

                    if count >= target_job_count:
                        break
                    if count == last_count:
                        no_change_iterations += 1
                        if no_change_iterations > 12:
                            tracker.add_log("No more new jobs loading.")
                            break
                    else:
                        no_change_iterations = 0
                        last_count = count

                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    page.wait_for_timeout(random.randint(1500, 2500))

                    see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
                    if see_more_btn.count() > 0 and see_more_btn.is_visible():
                        try:
                            see_more_btn.click(force=True, timeout=5000)
                            page.wait_for_timeout(2000)
                        except:
                            pass

                # Extract details
                job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
                card_count = min(job_cards.count(), target_job_count * 2)
                tracker.add_log(f"Processing details for {card_count} job postings...")

                city_jobs_scraped = 0
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

                        if not is_valid_title(job_title):
                            continue

                        comp_key = company_name.strip().lower()
                        if comp_key in seen_companies:
                            continue

                        # Click job card
                        page.evaluate("""
                            document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"]').forEach(el => el.remove());
                            document.body.style.overflow = 'auto';
                        """)
                        card.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        card.click(force=True, timeout=5000)
                        page.wait_for_timeout(random.randint(2000, 3000))

                        # Expand description
                        show_more_desc = page.locator("button.show-more-less-html__button, button:has-text('Show more'), button:has-text('See more')").first
                        if show_more_desc.count() > 0 and show_more_desc.is_visible():
                            try:
                                show_more_desc.click(force=True, timeout=3000)
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
                        posted_date_attr = safe_extract_any(card, ["time"], attribute="datetime")
                        if posted_date_attr:
                            posted_date = f"{posted_date} ({posted_date_attr})"

                        job_data = {
                            "Company Name": company_name,
                            "City / Location": city_name,
                            "Job Title": job_title,
                            "Experience Required": "0-1 Years",
                            "Required Skills": skills,
                            "Salary Range": salary,
                            "Job Posting Link / URL": clean_url,
                            "Source Platform": "LinkedIn",
                            "Posting Date": posted_date,
                            "Company Website": website,
                            "Company Size / Industry": f"{company_size} | {industry}" if company_size != "Not Mentioned" else industry
                        }

                        all_jobs.append(job_data)
                        seen_companies.add(comp_key)
                        city_jobs_scraped += 1
                        tracker.add_log(f"[{city_name}] Scraped Job: {job_title} at {company_name}")

                    except Exception as card_e:
                        tracker.add_log(f"Error processing card {i+1}: {str(card_e)}")

                tracker.add_log(f"Finished city {city_name}. Scraped {city_jobs_scraped} jobs.")

            browser.close()

        # Sort and Save
        city_priority = {"Delhi": 0, "Noida": 1, "Gurgaon": 2, "Jaipur": 3}
        all_jobs.sort(key=lambda x: city_priority.get(x["City / Location"], 4))

        headers = [
            "Company Name", "City / Location", "Job Title", "Experience Required",
            "Required Skills", "Salary Range", "Job Posting Link / URL",
            "Source Platform", "Posting Date", "Company Website", "Company Size / Industry"
        ]

        # Save individual cities
        for c in ["Delhi", "Noida", "Gurgaon", "Jaipur"]:
            city_jobs = [job for job in all_jobs if job["City / Location"] == c]
            c_lower = c.lower().replace(" ", "_")
            
            json_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.json"
            csv_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.csv"
            xls_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.xls"
            
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(city_jobs, f, indent=4, ensure_ascii=False)
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for j in city_jobs:
                    writer.writerow(j)
            write_excel_xml(xls_file, city_jobs, headers, f"Fresher Jobs - {c}")

        # Save merged (Append & Deduplicate with existing jobs)
        merged_json = "linkedin_fresher_data_analyst_jobs_merged.json"
        merged_csv = "linkedin_fresher_data_analyst_jobs_merged.csv"
        merged_xls = "linkedin_fresher_data_analyst_jobs_merged.xls"

        existing_jobs = []
        if os.path.exists(merged_json):
            try:
                with open(merged_json, "r", encoding="utf-8") as f:
                    existing_jobs = json.load(f)
                tracker.add_log(f"Loaded {len(existing_jobs)} existing jobs from merged file.")
            except Exception as e:
                tracker.add_log(f"Warning: Failed to load existing merged jobs ({e}). Starting fresh.")

        # Combine old and new scraped jobs
        combined_jobs = existing_jobs + all_jobs

        # Deduplicate based on Job URL or (Job Title + Company Name)
        seen_urls = set()
        seen_titles_companies = set()
        unique_jobs = []

        for job in combined_jobs:
            url = job.get("Job Posting Link / URL", "").strip()
            title = job.get("Job Title", "").strip().lower()
            company = job.get("Company Name", "").strip().lower()
            title_comp = f"{title}|||{company}"

            if url:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_jobs.append(job)
            else:
                if title_comp not in seen_titles_companies:
                    seen_titles_companies.add(title_comp)
                    unique_jobs.append(job)

        # Sort combined unique jobs by city priority
        unique_jobs.sort(key=lambda x: city_priority.get(x["City / Location"], 4))

        # Write deduplicated combined list back to merged files
        with open(merged_json, "w", encoding="utf-8") as f:
            json.dump(unique_jobs, f, indent=4, ensure_ascii=False)
        
        with open(merged_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for j in unique_jobs:
                writer.writerow(j)
                
        write_excel_xml(merged_xls, unique_jobs, headers, "Merged Fresher Jobs")

        tracker.complete(merged_json)
        tracker.add_log(f"Scrape completed. Total accumulated unique jobs: {len(unique_jobs)} (New added: {len(all_jobs)}).")

    except Exception as err:
        tracker.fail(str(err))

def email_generator_worker(task_id: str, api_key: str, model_name: str, resume_data: dict, input_csv_path: str):
    tracker = TaskTracker(task_id, "email_generator")
    tracker.add_log("Starting Cold Email Generator background pipeline...")

    if not os.path.exists(input_csv_path):
        tracker.fail(f"CSV file '{input_csv_path}' not found. Please run job scraper first.")
        return

    jobs = []
    try:
        with open(input_csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            def find_col(possible_names):
                for name in possible_names:
                    for header in headers:
                        if name.lower() == header.lower().strip():
                            return header
                return None
            
            company_col = find_col(["Company Name", "Company", "company_name", "company"])
            title_col = find_col(["Job Title", "Title", "job_title", "title"])
            skills_col = find_col(["Required Skills", "Job Description", "skills", "description", "required_skills"])
            url_col = find_col(["Job Posting Link / URL", "Job URL", "url", "link", "job_url", "posting_url"])

            if not company_col or not title_col:
                tracker.fail("Failed to parse headers from jobs CSV.")
                return

            for row in reader:
                comp = (row.get(company_col) or "").strip()
                title = (row.get(title_col) or "").strip()
                skills = (row.get(skills_col) or "").strip()
                url = (row.get(url_col) or "").strip()
                if comp and title:
                    jobs.append({"company": comp, "title": title, "skills": skills, "url": url})
    except Exception as e:
        tracker.fail(f"Error reading jobs CSV: {str(e)}")
        return

    if not jobs:
        tracker.fail("No jobs found in the source CSV.")
        return

    tracker.add_log(f"Found {len(jobs)} jobs. Preparing API queries...")
    output_csv = "generated_cold_emails.csv"
    output_json = "generated_cold_emails.json"

    emails_data = []
    success_count = 0
    total_jobs = len(jobs)

    try:
        with open(output_csv, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerow(["Company", "Job Title", "Generated Email", "Job URL"])

            for idx, job in enumerate(jobs):
                comp = job["company"]
                title = job["title"]
                
                tracker.update_progress((idx / total_jobs) * 100, f"Generating {idx+1}/{total_jobs}: {title} at {comp}")
                tracker.add_log(f"Generating email for {title} at {comp}...")
                
                email_content = generate_cold_email_custom(
                    api_key=api_key,
                    company_name=comp,
                    job_title=title,
                    job_description=job["skills"],
                    resume_data=resume_data,
                    model_name=model_name
                )
                
                if email_content:
                    writer.writerow([comp, title, email_content, job["url"]])
                    out_f.flush()
                    success_count += 1
                    
                    # Split subject and body from the output
                    subject = "Inquiry"
                    body = email_content
                    if email_content.lower().startswith("subject:"):
                        lines = email_content.split("\n", 1)
                        subject = lines[0].replace("Subject:", "").replace("subject:", "").strip()
                        if len(lines) > 1:
                            body = lines[1].strip()
                            
                    emails_data.append({
                        "company": comp,
                        "title": title,
                        "subject": subject,
                        "body": body,
                        "url": job["url"]
                    })
                    tracker.add_log(f"  [SUCCESS] Email generated.")
                else:
                    tracker.add_log(f"  [FAILED] API call failed for {comp}.")

                # Rate limiting delay
                if idx < total_jobs - 1:
                    import time
                    time.sleep(2.0)

        # Save JSON output as well
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(emails_data, f, indent=4, ensure_ascii=False)

        tracker.complete(output_json)
        tracker.add_log(f"Completed! Successfully generated {success_count} emails.")

    except Exception as err:
        tracker.fail(str(err))

# 24-Hour Pipeline Scheduler
from apscheduler.schedulers.background import BackgroundScheduler

def run_scheduled_pipeline():
    """
    24-hour pipeline job: Scrapes jobs first, then generates cold emails.
    """
    logger.info("⏰ Starting scheduled 24-hour scraping and email generation pipeline...")
    
    # 1. Scrape jobs
    task_id_scrape = f"sched_scrape_{str(uuid.uuid4())[:4]}"
    cities_list = [
        {"name": "Delhi", "query": "Delhi, India"},
        {"name": "Noida", "query": "Noida, Uttar Pradesh, India"},
        {"name": "Gurgaon", "query": "Gurgaon, Haryana, India"},
        {"name": "Jaipur", "query": "Jaipur, Rajasthan, India"}
    ]
    
    try:
        # Scrape with headless=True, limit=30 (stable limit for scheduled tasks)
        job_scraper_worker(task_id_scrape, cities_list, target_job_count=30, headless=True)
    except Exception as e:
        logger.error(f"Scheduled scraping failed: {e}")
        return

    # 2. Check if jobs CSV was generated successfully
    jobs_csv = "linkedin_fresher_data_analyst_jobs_merged.csv"
    if os.path.exists(jobs_csv):
        # 3. Generate cold emails
        config = load_config()
        api_key = config.get("api_key")
        model_name = config.get("model_name", "openai/gpt-4o-mini")
        resume_data = config.get("resume_data")
        
        if api_key and resume_data:
            task_id_email = f"sched_email_{str(uuid.uuid4())[:4]}"
            try:
                email_generator_worker(task_id_email, api_key, model_name, resume_data, jobs_csv)
                logger.info("✅ Scheduled pipeline completed successfully.")
            except Exception as e:
                logger.error(f"Scheduled email generation failed: {e}")
        else:
            logger.error("Scheduled email generation skipped: OpenRouter API key or Resume Data is missing in config.")
    else:
        logger.error("Scheduled email generation skipped: Scraped jobs file not found.")

@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()
    # Runs the pipeline every 24 hours
    scheduler.add_job(run_scheduled_pipeline, "interval", hours=24)
    scheduler.start()
    logger.info("📅 APScheduler background task registered to run every 24 hours.")

# HTTP App Controllers
@app.get("/api/config")
async def get_config_endpoint():
    return load_config()

@app.post("/api/config")
async def save_config_endpoint(payload: dict):
    config = load_config()
    
    if "resume_data" in payload:
        config["resume_data"] = payload["resume_data"]
    if "api_key" in payload:
        config["api_key"] = payload["api_key"]
    if "model_name" in payload:
        config["model_name"] = payload["model_name"]
        
    save_config(config)
    return {"message": "Configuration saved successfully."}

@app.post("/api/scrape")
async def start_scraping_endpoint(payload: dict):
    cities_input = payload.get("cities", ["Delhi", "Noida", "Gurgaon", "Jaipur"])
    limit = int(payload.get("limit", 100))
    headless = bool(payload.get("headless", True))
    
    city_mappings = {
        "Delhi": {"name": "Delhi", "query": "Delhi, India"},
        "Noida": {"name": "Noida", "query": "Noida, Uttar Pradesh, India"},
        "Gurgaon": {"name": "Gurgaon", "query": "Gurgaon, Haryana, India"},
        "Jaipur": {"name": "Jaipur", "query": "Jaipur, Rajasthan, India"}
    }
    
    cities_list = []
    for city_name in cities_input:
        if city_name in city_mappings:
            cities_list.append(city_mappings[city_name])
            
    if not cities_list:
        raise HTTPException(status_code=400, detail="No valid cities specified.")
        
    task_id = str(uuid.uuid4())[:8]
    
    # Run in a background thread to prevent blocking the event loop
    t = threading.Thread(target=job_scraper_worker, args=(task_id, cities_list, limit, headless))
    t.start()
    
    return {"task_id": task_id, "message": "Job scraping started."}

@app.post("/api/generate")
async def start_generation_endpoint():
    config = load_config()
    api_key = config["api_key"]
    model_name = config["model_name"]
    resume_data = config["resume_data"]
    
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter API Key is missing. Please save it in the settings first.")
        
    jobs_csv = "linkedin_fresher_data_analyst_jobs_merged.csv"
    if not os.path.exists(jobs_csv):
        raise HTTPException(status_code=400, detail="Merged jobs CSV file not found. Please run the job scraper first.")
        
    task_id = str(uuid.uuid4())[:8]
    
    t = threading.Thread(target=email_generator_worker, args=(task_id, api_key, model_name, resume_data, jobs_csv))
    t.start()
    
    return {"task_id": task_id, "message": "Cold email generation started."}

@app.get("/api/tasks")
async def list_tasks_endpoint():
    return list(tasks_db.values())

@app.get("/api/tasks/{task_id}")
async def get_task_status_endpoint(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

@app.get("/api/jobs")
async def get_jobs_endpoint():
    merged_json = "linkedin_fresher_data_analyst_jobs_merged.json"
    if not os.path.exists(merged_json):
        return []
    try:
        with open(merged_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

@app.get("/api/emails")
async def get_emails_endpoint():
    merged_json = "generated_cold_emails.json"
    if not os.path.exists(merged_json):
        return []
    try:
        with open(merged_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

@app.get("/api/files")
async def list_files_endpoint():
    files = []
    root_dir = os.getcwd()
    for f in os.listdir(root_dir):
        if os.path.isfile(f) and (f.endswith(".csv") or f.endswith(".json") or f.endswith(".xls") or f.endswith(".xlsx")):
            if f in ["config.json", "package.json"]:
                continue
            stat = os.stat(f)
            files.append({
                "name": f,
                "size": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files

@app.get("/api/files/download")
async def download_file_endpoint(filename: str):
    filepath = os.path.join(os.getcwd(), filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, filename=filename)

@app.delete("/api/files/delete")
async def delete_file_endpoint(filename: str):
    filepath = os.path.join(os.getcwd(), filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        os.remove(filepath)
        return {"message": f"Successfully deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.getcwd(), "templates", "index.html")
    if not os.path.exists(template_path):
        return HTMLResponse("<h1>Templates directory index.html missing! Please create it.</h1>", status_code=500)
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
