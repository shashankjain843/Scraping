import csv
import json
import time
import os
import random
import re
import sys
import urllib.parse
from playwright.sync_api import sync_playwright

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
            print(f"[INFO] Migrating CSV headers for {csv_path} to support new fields...")
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
            print(f"[INFO] Migration of {csv_path} complete.")
    except Exception as e:
        print(f"[ERROR] Failed migrating CSV headers for {csv_path}: {e}")

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
                print(f"[WARNING] Could not read JSON for dedup check {json_path}: {e}")
        
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
                print(f"[WARNING] Could not read existing URLs from {path}: {e}")
    print(f"[INFO] Loaded {len(seen)} unique existing job URLs for deduplication.")
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
        print(f"[ERROR] Failed writing job to CSV {csv_path}: {e}")

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
        print(f"[ERROR] Failed writing job to JSON {json_path}: {e}")

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

def scrape_job_details_fallback(context, job_url):
    print(f"Fallback: loading job URL directly to scrape details: {job_url}")
    try:
        new_page = context.new_page()
        new_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        new_page.goto(job_url, timeout=30000)
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
        print(f"Fallback scraping failed for {job_url}: {e}")
        try:
            new_page.close()
        except Exception:
            pass
        return "Not Mentioned", "Not Mentioned", "Not Mentioned", "Not Mentioned"

def scrape_search_results(page, context, keyword, location, seen_urls):
    jobs_collected = 0
    max_jobs_per_combo = 100
    last_count = 0
    no_change_iterations = 0
    
    print("Scrolling to load job cards...")
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
                print("No more new jobs loading.")
                break
        else:
            no_change_iterations = 0
            last_count = count
            
        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        page.wait_for_timeout(random.randint(3000, 6000))
        check_captcha(page)
        
        see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
        if see_more_btn.count() > 0 and see_more_btn.is_visible():
            try:
                see_more_btn.click(force=True, timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
                
    job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
    card_count = min(job_cards.count(), max_jobs_per_combo)
    print(f"Finished scrolling. Loaded {job_cards.count()} job cards. Starting extraction for up to {card_count} jobs...")
    
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
                
            try:
                card.click(force=True, timeout=5000)
                page.wait_for_timeout(random.randint(2000, 3000))
            except Exception:
                pass
                
            check_captcha(page)
            
            try:
                show_more_selectors = [
                    "button.show-more-less-html__button",
                    "button:has-text('Show more')",
                    "button:has-text('See more')"
                ]
                show_more_btn = None
                for sm_sel in show_more_selectors:
                    btn = page.locator(sm_sel).first
                    if btn.count() > 0 and btn.is_visible():
                        show_more_btn = btn
                        break
                if show_more_btn:
                    show_more_btn.click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
            except Exception:
                pass
                
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
            
            print(f"[SCRAPED: {keyword} in {location}] {jobs_collected} jobs found -> '{job_title}' at '{company_name}'")
            
        except Exception as card_err:
            print(f"[WARNING] Error processing job card {idx}: {card_err}")

def main():
    print("="*60)
    print("LINKEDIN GUEST JOBS SCRAPER INITIALIZING (NO LOGIN)")
    print("="*60)
    
    # Migrate CSV headers for all output files to support new columns
    files_to_migrate = [MERGED_CSV]
    for loc in LOCATIONS:
        csv_path, _ = get_file_paths(loc)
        files_to_migrate.append(csv_path)
    for path in files_to_migrate:
        migrate_csv_headers(path, HEADERS)
        
    seen_urls = load_all_existing_urls()
    
    with sync_playwright() as p:
        print("Launching Chromium browser (headless=False)...")
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        for keyword in KEYWORDS:
            for location in LOCATIONS:
                print("\n" + "-"*50)
                print(f"Scraping: '{keyword}' in '{location}'")
                print("-"*50)
                
                try:
                    page.goto("https://www.linkedin.com/jobs/", timeout=60000)
                    page.wait_for_timeout(random.randint(2000, 3000))
                    check_captcha(page)
                    
                    search_success = False
                    try:
                        keyword_input = page.locator("input[name='keywords'], input[aria-label='Search job titles or companies']").first
                        location_input = page.locator("input[name='location'], input[aria-label='Location']").first
                        
                        if keyword_input.count() > 0 and location_input.count() > 0:
                            keyword_input.click()
                            page.keyboard.press("Control+A")
                            page.keyboard.press("Backspace")
                            keyword_input.fill(keyword)
                            page.wait_for_timeout(500)
                            
                            location_input.click()
                            page.keyboard.press("Control+A")
                            page.keyboard.press("Backspace")
                            location_input.fill(location)
                            page.wait_for_timeout(500)
                            
                            search_btn = page.locator("button.search-button, button[type='submit']").first
                            if search_btn.count() > 0:
                                search_btn.click()
                            else:
                                page.keyboard.press("Enter")
                                
                            search_success = True
                            print("Search triggered via guest input fields.")
                            page.wait_for_timeout(random.randint(4000, 6000))
                    except Exception as search_err:
                        print(f"Could not search using guest input fields: {search_err}. Falling back to direct URL...")
                        
                    if not search_success or "search" not in page.url.lower():
                        encoded_keyword = urllib.parse.quote(keyword)
                        encoded_location = urllib.parse.quote(location)
                        search_url = f"https://www.linkedin.com/jobs/search?keywords={encoded_keyword}&location={encoded_location}"
                        print(f"Navigating directly to search URL: {search_url}")
                        page.goto(search_url, timeout=60000)
                        page.wait_for_timeout(random.randint(4000, 6000))
                        
                    check_captcha(page)
                    scrape_search_results(page, context, keyword, location, seen_urls)
                    
                except Exception as combo_err:
                    print(f"[ERROR] Failed combination '{keyword}' in '{location}': {combo_err}")
                    
        browser.close()
        print("\n" + "="*60)
        print("LINKEDIN JOBS SCRAPER RUN COMPLETED SUCCESSFULLY!")
        print("="*60)

if __name__ == "__main__":
    main()
