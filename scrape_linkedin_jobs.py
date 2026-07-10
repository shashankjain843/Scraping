import csv
import json
import time
import os
import random
import re
import sys
import urllib.parse
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeError in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Constants
HEADERS = [
    "Company Name",
    "City / Location",
    "Job Title",
    "Experience Required",
    "Required Skills",
    "Salary Range",
    "Job Posting Link / URL",
    "Source Platform",
    "Posting Date",
    "Company Website",
    "Company Size / Industry",
    "Job Description",
    "Job Type",
    "Search Keyword Used"
]

MERGED_CSV = "linkedin_fresher_data_analyst_jobs_merged.csv"
MERGED_JSON = "linkedin_fresher_data_analyst_jobs_merged.json"

KEYWORDS = [
    "Data Analyst",
    "Business Analyst",
    "Data Analytics",
    "Junior Data Analyst",
    "SQL Analyst",
    "Reporting Analyst"
]

LOCATIONS = [
    "Jaipur",
    "Noida",
    "Delhi",
    "Gurugram"
]

# Statistics tracking
stats = {
    "jobs_scraped": 0,
    "emails_generated": 0,
    "emails_sent": 0
}

def log_to_file(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}\n"
    print(formatted_msg.strip())
    try:
        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(formatted_msg)
    except Exception as e:
        print(f"[ERROR] Failed to write to log file logs.txt: {e}")

def retry_action(action_fn, action_name, max_attempts=3, initial_delay=2):
    attempt = 0
    delay = initial_delay
    while attempt < max_attempts:
        try:
            return action_fn()
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                log_to_file(f"Action '{action_name}' failed after {max_attempts} attempts. Error: {e}")
                raise e
            log_to_file(f"Action '{action_name}' failed (attempt {attempt}/{max_attempts}). Retrying in {delay}s... Error: {e}")
            time.sleep(delay)
            delay *= 2

def get_file_paths(location):
    loc_lower = location.lower().replace(" ", "_")
    if loc_lower == "gurugram" or loc_lower == "gurgaon":
        loc_lower = "gurgaon"
    csv_path = f"linkedin_fresher_data_analyst_jobs_{loc_lower}.csv"
    json_path = f"linkedin_fresher_data_analyst_jobs_{loc_lower}.json"
    return csv_path, json_path

def migrate_csv_headers(csv_path, new_headers):
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return
        
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        if not rows:
            return
            
        existing_headers = rows[0]
        needs_migration = False
        for h in new_headers:
            if h not in existing_headers:
                needs_migration = True
                break
                
        if needs_migration:
            log_to_file(f"[INFO] Migrating CSV headers for {csv_path} to support new fields...")
            header_map = {h: idx for idx, h in enumerate(existing_headers)}
            
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(new_headers)
                
                for old_row in rows[1:]:
                    new_row = []
                    for h in new_headers:
                        if h in header_map and header_map[h] < len(old_row):
                            new_row.append(old_row[header_map[h]])
                        else:
                            new_row.append("")
                    writer.writerow(new_row)
            log_to_file(f"[INFO] Migration of {csv_path} complete.")
    except Exception as e:
        log_to_file(f"[ERROR] Failed migrating CSV headers for {csv_path}: {e}")

def normalize_url(url):
    """Strip query params so ?trackingId=... variants are treated as the same job."""
    if url:
        return url.strip().split("?")[0].rstrip("/")
    return ""

def load_all_existing_urls():
    seen = set()
    files = [MERGED_CSV]
    for loc in LOCATIONS:
        csv_path, _ = get_file_paths(loc)
        files.append(csv_path)

    # Also load from JSON files for maximum coverage
    for loc in LOCATIONS:
        _, json_path = get_file_paths(loc)
        if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for job in data:
                        url = normalize_url(job.get("Job Posting Link / URL", ""))
                        if url:
                            seen.add(url)
            except Exception as e:
                log_to_file(f"[WARNING] Could not read JSON for dedup check {json_path}: {e}")
        
    for path in files:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = normalize_url(row.get("Job Posting Link / URL", ""))
                        if url:
                            seen.add(url)
            except Exception as e:
                log_to_file(f"[WARNING] Could not read existing URLs from {path}: {e}")
    log_to_file(f"[INFO] Loaded {len(seen)} unique existing job URLs for deduplication.")
    return seen

def append_job_to_csv(csv_path, job_data, headers):
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(job_data)
    except Exception as e:
        log_to_file(f"[ERROR] Failed writing job to CSV {csv_path}: {e}")

def append_job_to_json(json_path, job_data):
    try:
        jobs = []
        if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    jobs = json.load(f)
                except Exception:
                    jobs = []
        jobs.append(job_data)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log_to_file(f"[ERROR] Failed writing job to JSON {json_path}: {e}")

def safe_extract_any(locator, selectors, attribute=None, default=""):
    if not selectors:
        try:
            if locator.count() > 0:
                if attribute:
                    val = locator.first.get_attribute(attribute)
                    if val:
                        return val.strip()
                else:
                    val = locator.first.inner_text()
                    if val:
                        return val.strip()
        except Exception:
            pass
        return default

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

def check_captcha(page):
    while True:
        url_lower = page.url.lower()
        if "checkpoint/challenge" in url_lower or "captcha" in url_lower or page.locator("text='Security verification'").count() > 0 or page.locator("text='Please solve the puzzle'").count() > 0:
            print("\n" + "="*70)
            print("ALERT: LinkedIn CAPTCHA or Security Verification detected!")
            print("Please solve the verification in the opened browser window.")
            print("After solving it successfully and getting to the normal page, press Enter here to resume...")
            print("="*70 + "\n")
            try:
                import winsound
                winsound.Beep(1000, 1000)
            except Exception:
                print("\a")
            input("Press Enter to resume scraping...")
            page.wait_for_timeout(3000)
        else:
            break

def is_valid_title(title):
    title_lower = title.lower()
    return "data analyst" in title_lower or "data analytics" in title_lower

def is_fresher_friendly(title, description, criteria_exp):
    title_lower = title.lower()
    desc_lower = description.lower()
    crit_lower = criteria_exp.lower()
    
    # 1. Exclude seniority keywords in title (case-insensitive word boundary check)
    exclude_title_words = ["senior", "lead", "sr", "principal", "manager", "head", "architect", "expert", "specialist"]
    for word in exclude_title_words:
        if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
            return False
            
    # 2. Check criteria if present (e.g. "Seniority level: Mid-Senior level")
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
        r'\b(?:2|3|4|5|6|7|8|9|10)\+?\s*(?:to|-)\s*\d+\s*(?:years?|yrs?)\b', # 2-3 years, 2 to 5 years
        r'\b(?:2|3|4|5|6|7|8|9|10)\+\s*(?:years?|yrs?)\b',                  # 2+ years
        r'\b(?:minimum|min|at least|required)\s+of?\s*(?:2|3|4|5|6|7|8|9|10)\s*(?:years?|yrs?)\b', # minimum of 2 years
        r'\b(?:2|3|4|5|6|7|8|9|10)\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b', # 2 years of experience
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

def is_linkedin_logged_in(page):
    """Check karo ki LinkedIn pe actually logged in hain ya nahi — DOM elements se."""
    try:
        logged_in_selectors = [
            "div.global-nav__me",          # Profile/me icon in nav
            "img.global-nav__me-photo",    # Profile photo
            "a[href*='/feed/']"             # Feed link in nav
        ]
        for sel in logged_in_selectors:
            if page.locator(sel).first.count() > 0:
                return True
        if "login" in page.url or "authwall" in page.url or "signup" in page.url:
            return False
        return False
    except Exception:
        return False

def login_to_linkedin(page, email, password):
    log_to_file("[INFO] Starting LinkedIn login process...")
    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_session.json")

    # Pehle check karo: session file se already logged in hain?
    if os.path.exists(session_path):
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=25000)
            page.wait_for_load_state("networkidle", timeout=15000)
            if is_linkedin_logged_in(page):
                log_to_file("[SUCCESS] Session valid hai. LinkedIn login skip kar rahe hain.")
                return
            else:
                log_to_file("[INFO] Session expired ya invalid hai. Purana session delete karke fresh login karenge...")
                try:
                    os.remove(session_path)
                except Exception:
                    pass
        except Exception as e:
            log_to_file(f"[INFO] Session check fail hua: {e}. Fresh login karenge...")
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
            log_to_file("[SUCCESS] LinkedIn pe successfully login ho gaye!")
            page.context.storage_state(path=session_path)
            log_to_file(f"[INFO] Naya session save kar diya: {session_path}")
        elif "checkpoint" in page.url:
            log_to_file(f"[WARNING] LinkedIn ne security check maanga. URL: {page.url}")
            check_captcha(page)
            page.context.storage_state(path=session_path)
        else:
            log_to_file(f"[WARNING] Login ke baad bhi logged-in elements nahi mile. URL: {page.url}")
            page.context.storage_state(path=session_path)
    except Exception as login_err:
        log_to_file(f"[ERROR] LinkedIn login fail hua: {login_err}")
        check_captcha(page)

def scrape_job_details_fallback(context, job_url):
    log_to_file(f"Fallback: loading job URL directly to scrape details: {job_url}")
    new_page = None
    try:
        new_page = context.new_page()
        new_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        def goto_fallback_url():
            new_page.goto(job_url, timeout=30000)
            new_page.wait_for_load_state("networkidle")
            
        retry_action(goto_fallback_url, f"Navigate fallback URL: {job_url}")
        new_page.wait_for_timeout(3000)
        
        check_captcha(new_page)
        
        try:
            show_more_selectors = [
                "button.show-more-less-html__button",
                "button:has-text('Show more')",
                "button:has-text('See more')",
                "button.jobs-description__footer-button"
            ]
            for sm_sel in show_more_selectors:
                btn = new_page.locator(sm_sel).first
                if btn.count() > 0 and btn.is_visible():
                    new_page.wait_for_selector(sm_sel, state="visible", timeout=10000)
                    btn.click(force=True, timeout=2000)
                    new_page.wait_for_timeout(500)
                    break
        except Exception:
            pass
            
        description = "Not Mentioned"
        desc_selectors = [
            "div.show-more-less-html__markup",
            ".description__text",
            "div.jobs-description-content__text",
            "#job-details"
        ]
        for d_sel in desc_selectors:
            el = new_page.locator(d_sel).first
            if el.count() > 0:
                description = el.inner_text().strip()
                if description:
                    break
                    
        # Extract criteria
        job_type = "Not Mentioned"
        exp_level = "Not Mentioned"
        industry = "Not Mentioned"
        criteria_items = new_page.locator("li.description__job-criteria-item")
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
                
        exp_level = criteria_dict.get("Seniority level", "Not Mentioned")
        job_type = criteria_dict.get("Employment type", "Not Mentioned")
        industry = criteria_dict.get("Industries", "Not Mentioned")
        
        new_page.close()
        return description, job_type, exp_level, industry
    except Exception as e:
        log_to_file(f"[WARNING] Fallback scraping failed for {job_url}: {e}")
        if new_page:
            try:
                new_page.close()
            except Exception:
                pass
        return "Not Mentioned", "Not Mentioned", "Not Mentioned", "Not Mentioned"

def scrape_search_results(page, context, keyword, location, seen_urls):
    global stats
    jobs_collected = 0
    max_jobs_per_combo = 100
    last_count = 0
    no_change_iterations = 0
    
    log_to_file("Scrolling to load job cards...")
    while True:
        try:
            page.evaluate("""
                document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"], [class*="overlay"], [class*="signup"], [class*="login"]').forEach(el => el.remove());
                document.body.style.overflow = 'auto';
                if (document.body.classList.contains('modal-open')) {
                    document.body.classList.remove('modal-open');
                }
            """)
        except Exception:
            pass
            
        job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
        count = job_cards.count()
        
        if count >= max_jobs_per_combo:
            break
            
        if count == last_count:
            no_change_iterations += 1
            if no_change_iterations > 12:
                log_to_file("No more new jobs loading.")
                break
        else:
            no_change_iterations = 0
            last_count = count
            
        try:
            def scroll():
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            retry_action(scroll, "Scroll search page")
        except Exception as scroll_err:
            log_to_file(f"[WARNING] Scroll failed: {scroll_err}. Skipping further scrolling.")
            break

        page.wait_for_timeout(random.randint(3000, 6000))
        check_captcha(page)
        
        see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
        if see_more_btn.count() > 0 and see_more_btn.is_visible():
            try:
                def click_see_more():
                    # Wait for selector of either button variation
                    btn_sel = "button.infinite-scroller__show-more-button" if page.locator("button.infinite-scroller__show-more-button").count() > 0 else "button:has-text('See more jobs')"
                    page.wait_for_selector(btn_sel, state="visible", timeout=10000)
                    see_more_btn.click(force=True, timeout=5000)
                
                retry_action(click_see_more, "Click see more jobs button")
                page.wait_for_timeout(2000)
            except Exception as see_more_err:
                log_to_file(f"[WARNING] Click see more jobs failed: {see_more_err}")
                
    job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
    card_count = min(job_cards.count(), max_jobs_per_combo)
    log_to_file(f"Finished scrolling. Loaded {job_cards.count()} job cards. Starting extraction for up to {card_count} jobs...")
    
    city_csv, city_json = get_file_paths(location)
    
    for idx in range(card_count):
        card = job_cards.nth(idx)
        try:
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            
            job_title = safe_extract_any(card, [
                "h3.base-search-card__title",
                "h3.job-search-card__title",
                ".base-search-card__title",
                "h3"
            ])
            
            company_name = safe_extract_any(card, [
                "h4.base-search-card__subtitle",
                "a.hidden-nested-link",
                ".base-search-card__subtitle",
                "h4"
            ])
            
            job_location = safe_extract_any(card, [
                "span.job-search-card__location",
                ".job-search-card__location",
                "span"
            ])
            
            job_url = safe_extract_any(card, [
                "a.base-card__full-link",
                "a.job-search-card__link",
                "a"
            ], attribute="href")
            
            if not job_title or not company_name or not job_url:
                continue
                
            clean_url = normalize_url(job_url)
            if clean_url.startswith("/"):
                clean_url = normalize_url("https://www.linkedin.com" + clean_url)
                
            if clean_url in seen_urls:
                print(f"  [SKIP - already scraped] {job_title} at {company_name}")
                continue

            # Core extraction process with card clicking
            def extract_details():
                card.wait_for(state="visible", timeout=10000)
                card.click(force=True, timeout=5000)
                
                desc_el = page.locator("div.show-more-less-html__markup, .description__text").first
                try:
                    desc_el.wait_for(state="visible", timeout=3000)
                except:
                    pass
                page.wait_for_timeout(800)
                check_captcha(page)
                
                show_more_selectors = [
                    "button.show-more-less-html__button",
                    "button:has-text('Show more')",
                    "button:has-text('See more')"
                ]
                show_more_btn = None
                chosen_sel = None
                for sm_sel in show_more_selectors:
                    btn = page.locator(sm_sel).first
                    if btn.count() > 0 and btn.is_visible():
                        show_more_btn = btn
                        chosen_sel = sm_sel
                        break
                if show_more_btn:
                    page.wait_for_selector(chosen_sel, state="visible", timeout=10000)
                    show_more_btn.click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
                
                description = "Not Mentioned"
                desc_selectors = [
                    "div.show-more-less-html__markup",
                    ".description__text"
                ]
                for d_sel in desc_selectors:
                    el = page.locator(d_sel).first
                    if el.count() > 0:
                        description = el.inner_text().strip()
                        if description:
                            break
                return description

            try:
                description = retry_action(extract_details, f"Extract details for job: {job_title} at {company_name}")
            except Exception as extract_err:
                log_to_file(f"[WARNING] Skipping job card {idx} ('{job_title}' at '{company_name}') due to persistent errors: {extract_err}")
                continue
                
            job_type = "Not Mentioned"
            exp_level = "Not Mentioned"
            industry = "Not Mentioned"
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
                    
            exp_level = criteria_dict.get("Seniority level", "Not Mentioned")
            job_type = criteria_dict.get("Employment type", "Not Mentioned")
            industry = criteria_dict.get("Industries", "Not Mentioned")
            
            if description == "Not Mentioned" or description == "":
                description, job_type_f, exp_level_f, industry_f = scrape_job_details_fallback(context, clean_url)
                if job_type == "Not Mentioned" and job_type_f != "Not Mentioned":
                    job_type = job_type_f
                if exp_level == "Not Mentioned" and exp_level_f != "Not Mentioned":
                    exp_level = exp_level_f
                if industry == "Not Mentioned" and industry_f != "Not Mentioned":
                    industry = industry_f
            
            posted_date = safe_extract_any(card, [
                "time.job-search-card__listdate",
                "time.job-search-card__listdate--new",
                "time.base-search-card__listdate",
                "time"
            ])
            
            skills = extract_skills(description)
            salary = extract_salary(description)
            website = extract_website(description)
            comp_size_industry = f"{job_type} | {industry}" if job_type != "Not Mentioned" else industry
            
            job_data = {
                "Company Name": company_name.strip(),
                "City / Location": location,
                "Job Title": job_title.strip(),
                "Experience Required": exp_level.strip(),
                "Required Skills": skills,
                "Salary Range": salary,
                "Job Posting Link / URL": clean_url,
                "Source Platform": "LinkedIn",
                "Posting Date": posted_date.strip(),
                "Company Website": website,
                "Company Size / Industry": comp_size_industry.strip(),
                "Job Description": description.strip(),
                "Job Type": job_type.strip(),
                "Search Keyword Used": keyword
            }
            
            # Append to location files
            append_job_to_csv(city_csv, job_data, HEADERS)
            append_job_to_json(city_json, job_data)
            
            # Append to merged files
            append_job_to_csv(MERGED_CSV, job_data, HEADERS)
            append_job_to_json(MERGED_JSON, job_data)
            
            seen_urls.add(normalize_url(clean_url))
            jobs_collected += 1
            stats["jobs_scraped"] += 1
            
            log_to_file(f"[SCRAPED: {keyword} in {location}] {jobs_collected} jobs found -> '{job_title}' at '{company_name}'")
            
        except Exception as card_err:
            log_to_file(f"[WARNING] Skipping job card {idx} due to processing error: {card_err}")

def main():
    log_to_file("="*60)
    log_to_file("LINKEDIN JOBS SCRAPER INITIALIZING")
    log_to_file("="*60)
    
    # Migrate CSV headers for all output files to support new columns
    files_to_migrate = [MERGED_CSV]
    for loc in LOCATIONS:
        csv_path, _ = get_file_paths(loc)
        files_to_migrate.append(csv_path)
    for path in files_to_migrate:
        migrate_csv_headers(path, HEADERS)
        
    seen_urls = load_all_existing_urls()
    
    with sync_playwright() as p:
        log_to_file("Launching Chromium browser (headless=False)...")
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_session.json")
        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        if os.path.exists(session_path):
            context_args["storage_state"] = session_path
            log_to_file("[INFO] Loading existing LinkedIn session for scraper...")
            
        context = browser.new_context(**context_args)
        
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Log in if credentials available
        linkedin_email = os.environ.get("LINKEDIN_EMAIL")
        linkedin_password = os.environ.get("LINKEDIN_PASSWORD")
        if linkedin_email and linkedin_password:
            login_to_linkedin(page, linkedin_email, linkedin_password)
        else:
            log_to_file("[INFO] No LinkedIn credentials found in .env. Running as guest (NO LOGIN).")
        
        for keyword in KEYWORDS:
            for location in LOCATIONS:
                log_to_file("\n" + "-"*50)
                log_to_file(f"Scraping: '{keyword}' in '{location}'")
                log_to_file("-"*50)
                
                try:
                    encoded_keyword = urllib.parse.quote(keyword)
                    encoded_location = urllib.parse.quote(location)
                    search_url = f"https://www.linkedin.com/jobs/search?keywords={encoded_keyword}&location={encoded_location}&sortBy=DD&f_TPR=r86400"
                    log_to_file(f"Navigating directly to search URL: {search_url}")
                    
                    def navigate_direct_search():
                        page.goto(search_url, timeout=60000)
                        page.wait_for_load_state("networkidle")
                        
                    retry_action(navigate_direct_search, "Navigate directly to search URL", max_attempts=2)
                    page.wait_for_timeout(random.randint(4000, 6000))
                    
                    check_captcha(page)
                    
                    # Fallback check if 0 jobs found with 24h filter
                    job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
                    if job_cards.count() == 0 and "f_TPR=r86400" in search_url:
                        fallback_url = search_url.replace("&f_TPR=r86400", "")
                        log_to_file(f"[INFO] 0 jobs found with 24h filter for {location}. Retrying with fallback URL: {fallback_url}")
                        try:
                            page.goto(fallback_url, timeout=60000)
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(random.randint(4000, 6000))
                            check_captcha(page)
                        except Exception as fe:
                            log_to_file(f"[ERROR] Failed to load fallback search page for {location}: {fe}")
                            
                    scrape_search_results(page, context, keyword, location, seen_urls)
                    
                except Exception as combo_err:
                    log_to_file(f"[ERROR] Failed combination '{keyword}' in '{location}': {combo_err}")
                    
        browser.close()
        log_to_file("\n" + "="*60)
        log_to_file(f"LINKEDIN JOBS SCRAPER RUN COMPLETED SUCCESSFULLY! Total jobs scraped: {stats['jobs_scraped']}")
        log_to_file("="*60)

if __name__ == "__main__":
    main()
