import csv
import time
import os
import random
import json
import re
import sys
from playwright.sync_api import sync_playwright

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeError in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def safe_extract_any(locator, selectors, attribute=None, default=""):
    """
    Safely tries multiple CSS selectors to extract text or attribute content
    from a locator card to ensure robustness against page changes.
    """
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

def is_valid_title(title):
    title_lower = title.lower()
    # Job title must contain "data analyst" or "data analytics"
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
    # Search for patterns like "4-6 LPA", "300,000 - 500,000 INR", etc.
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
    # Regex to find domain names in description (excluding common domains like linkedin.com, google.com)
    match = re.search(r'\bhttps?://(?:www\.)?([a-zA-Z0-9-]+)\.[a-z]{2,}(?:\S*)', description)
    if match:
        url = match.group(0)
        # Exclude common domains
        if not any(domain in url.lower() for domain in ["linkedin.com", "google.com", "microsoft.com", "youtube.com"]):
            return url
    return "Not Mentioned"

def scrape_linkedin_freshers():
    cities = [
        {"name": "Delhi", "query": "Delhi, India"},
        {"name": "Noida", "query": "Noida, Uttar Pradesh, India"},
        {"name": "Gurgaon", "query": "Gurgaon, Haryana, India"},
        {"name": "Jaipur", "query": "Jaipur, Rajasthan, India"}
    ]
    
    all_jobs = []
    seen_companies = set()
    
    target_job_count = 1000  # Load up to 1000 job cards per city to search for freshers
    
    with sync_playwright() as p:
        # Launch headed browser to mimic real user interaction and bypass bot detection
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
        
        for city in cities:
            city_name = city["name"]
            city_query = city["query"]
            print(f"\n==================================================")
            print(f"SCRAPING CITY: {city_name} ({city_query})")
            print(f"==================================================")
            
            # Search both "Data Analyst" and "Data Analytics" using OR operator
            url_keyword = "%28%22Data%20Analyst%22%20OR%20%22Data%20Analytics%22%29"
            url_location = city_query.replace(" ", "%20").replace(",", "%2C")
            
            # Search without f_E parameter to scan all postings (including those not tagged with experience level by the poster)
            # distance=25 represents 25 miles (~40 km range).
            search_url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location={url_location}&distance=25"
            print(f"Navigating to: {search_url}")
            
            try:
                page.goto(search_url, timeout=60000)
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Error loading page for {city_name}: {e}")
                continue
                
            # Scroll down to load cards
            print("Scrolling to load job cards...")
            last_count = 0
            no_change_iterations = 0
            
            while True:
                # Remove overlay modals programmatically
                try:
                    page.evaluate("""
                        document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"]').forEach(el => el.remove());
                        document.body.style.overflow = 'auto';
                        if (document.body.classList.contains('modal-open')) {
                            document.body.classList.remove('modal-open');
                        }
                    """)
                except Exception:
                    pass
                    
                job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
                count = job_cards.count()
                print(f"[{city_name}] Found {count} job cards loaded.")
                
                if count >= target_job_count:
                    break
                    
                if count == last_count:
                    no_change_iterations += 1
                    if no_change_iterations > 12:
                        print("No more new jobs loading.")
                        break
                else:
                    no_change_iterations = 0
                    last_count = count
                    
                # Scroll to bottom to trigger dynamic loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(random.randint(1500, 2500))
                
                # Click "See more jobs" if it appears
                see_more_btn = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
                if see_more_btn.count() > 0 and see_more_btn.is_visible():
                    try:
                        see_more_btn.click(force=True, timeout=5000)
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass
            
            # Refresh card list and iterate
            job_cards = page.locator("div.base-card, .job-search-card, li.jobs-search-results__list-item")
            card_count = min(job_cards.count(), target_job_count * 2)
            print(f"Scraping up to {card_count} loaded cards for {city_name}...")
            
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
                    
                    # Apply Title Filter
                    if not is_valid_title(job_title):
                        continue
                        
                    # Apply Company Deduplication (keep the most recent posting per company)
                    comp_key = company_name.strip().lower()
                    if comp_key in seen_companies:
                        continue
                        
                    # Click card to load details
                    try:
                        page.evaluate("""
                            document.querySelectorAll('.modal__overlay, .modal, .top-level-modal-container, [class*="modal"]').forEach(el => el.remove());
                            document.body.style.overflow = 'auto';
                        """)
                        card.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        card.click(force=True, timeout=5000)
                        page.wait_for_timeout(random.randint(2000, 3000))
                    except Exception as e:
                        print(f"Error loading details for card {i+1}: {e}")
                        continue
                        
                    # Expand description
                    show_more_desc = page.locator("button.show-more-less-html__button, button:has-text('Show more'), button:has-text('See more')").first
                    if show_more_desc.count() > 0 and show_more_desc.is_visible():
                        try:
                            show_more_desc.click(force=True, timeout=3000)
                            page.wait_for_timeout(500)
                        except Exception:
                            pass
                            
                    # Extract description text
                    description = "Not Mentioned"
                    desc_el = page.locator("div.show-more-less-html__markup, .description__text").first
                    if desc_el.count() > 0:
                        description = desc_el.inner_text().strip()
                        
                    # Extract criteria
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
                    
                    # Apply Fresher-Friendly Filter (0-1 years exp)
                    if not is_fresher_friendly(job_title, description, criteria_exp):
                        continue
                        
                    # Extract skills
                    skills = extract_skills(description)
                    
                    # Extract salary
                    salary = extract_salary(description)
                    
                    # Extract website
                    website = extract_website(description)
                    
                    # Posted Date
                    posted_date = safe_extract_any(card, ["time.job-search-card__listdate", "time.job-search-card__listdate--new", "time.base-search-card__listdate", "time"])
                    posted_date_attr = safe_extract_any(card, ["time"], attribute="datetime")
                    if posted_date_attr:
                        posted_date = f"{posted_date} ({posted_date_attr})"
                        
                    # Add to list
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
                    print(f"[{city_name}] Scraped Fresher Job: {job_title} at {company_name}")
                    
                except Exception as e:
                    print(f"Error processing card {i+1}: {e}")
                    
            print(f"Completed scraping {city_name}. Total companies found: {city_jobs_scraped}")
            
        browser.close()
        
    # Sort results city-wise: Delhi (1st), Noida (2nd), Gurgaon (3rd), Jaipur (4th)
    city_priority = {"Delhi": 0, "Noida": 1, "Gurgaon": 2, "Jaipur": 3}
    all_jobs.sort(key=lambda x: city_priority.get(x["City / Location"], 4))
    
    # Save files per city
    headers = [
        "Company Name", "City / Location", "Job Title", "Experience Required",
        "Required Skills", "Salary Range", "Job Posting Link / URL",
        "Source Platform", "Posting Date", "Company Website", "Company Size / Industry"
    ]
    
    print(f"\n==================================================")
    print(f"FINAL SCRAPING SUMMARY")
    print(f"==================================================")
    
    for c in ["Delhi", "Noida", "Gurgaon", "Jaipur"]:
        city_jobs = [job for job in all_jobs if job["City / Location"] == c]
        cnt = len(city_jobs)
        print(f"Total fresher Data Analyst companies found in {c}: {cnt}")
        
        c_lower = c.lower().replace(" ", "_")
        csv_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.csv"
        json_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.json"
        excel_file = f"linkedin_fresher_data_analyst_jobs_{c_lower}.xls"
        
        # 1. Save CSV
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for job in city_jobs:
                writer.writerow(job)
                
        # 2. Save JSON
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(city_jobs, f, indent=4, ensure_ascii=False)
            
        # 3. Save Excel (Excel-compatible XML format)
        xml_header = f"""<?xml version="1.0" encoding="utf-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-excel"
 xmlns:o="urn:schemas-microsoft-excel:office"
 xmlns:x="urn:schemas-microsoft-excel:excel"
 xmlns:ss="urn:schemas-microsoft-excel:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Worksheet ss:Name="Fresher Jobs - {c}">
  <Table>
"""
        xml_footer = """  </Table>
 </Worksheet>
</Workbook>
"""
        with open(excel_file, "w", encoding="utf-8") as f:
            f.write(xml_header)
            f.write("   <Row>\n")
            for h in headers:
                h_esc = h.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
                f.write(f'    <Cell><Data ss:Type="String">{h_esc}</Data></Cell>\n')
            f.write("   </Row>\n")
            
            for job in city_jobs:
                f.write("   <Row>\n")
                for h in headers:
                    val = job.get(h, "")
                    if val is None:
                        val = ""
                    val_esc = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
                    f.write(f'    <Cell><Data ss:Type="String">{val_esc}</Data></Cell>\n')
                f.write("   </Row>\n")
            f.write(xml_footer)
            
        print(f"Saved {c} files successfully: {csv_file}, {json_file}, {excel_file}")

    # Save merged files containing all cities
    merged_csv_file = "linkedin_fresher_data_analyst_jobs_merged.csv"
    merged_json_file = "linkedin_fresher_data_analyst_jobs_merged.json"
    merged_excel_file = "linkedin_fresher_data_analyst_jobs_merged.xls"
    
    print(f"\n==================================================")
    print(f"SAVING MERGED DATASETS (ALL CITIES)")
    print(f"==================================================")
    
    # 1. Save Merged CSV
    with open(merged_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for job in all_jobs:
            writer.writerow(job)
            
    # 2. Save Merged JSON
    with open(merged_json_file, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=4, ensure_ascii=False)
        
    # 3. Save Merged Excel
    xml_header_merged = """<?xml version="1.0" encoding="utf-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-excel"
 xmlns:o="urn:schemas-microsoft-excel:office"
 xmlns:x="urn:schemas-microsoft-excel:excel"
 xmlns:ss="urn:schemas-microsoft-excel:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Worksheet ss:Name="Merged Fresher Jobs">
  <Table>
"""
    xml_footer_merged = """  </Table>
 </Worksheet>
</Workbook>
"""
    with open(merged_excel_file, "w", encoding="utf-8") as f:
        f.write(xml_header_merged)
        f.write("   <Row>\n")
        for h in headers:
            h_esc = h.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            f.write(f'    <Cell><Data ss:Type="String">{h_esc}</Data></Cell>\n')
        f.write("   </Row>\n")
        
        for job in all_jobs:
            f.write("   <Row>\n")
            for h in headers:
                val = job.get(h, "")
                if val is None:
                    val = ""
                val_esc = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
                f.write(f'    <Cell><Data ss:Type="String">{val_esc}</Data></Cell>\n')
            f.write("   </Row>\n")
        f.write(xml_footer_merged)
        
    print(f"Saved merged files successfully:")
    print(f"- CSV: {merged_csv_file}")
    print(f"- JSON: {merged_json_file}")
    print(f"- Excel: {merged_excel_file}")
    print(f"Total merged records: {len(all_jobs)}")

if __name__ == "__main__":
    scrape_linkedin_freshers()
