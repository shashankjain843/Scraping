import os
import csv
import json
import time
import sys
import random
import re
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeError in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configurations & Limits
MODEL_NAME = "gemini-2.5-flash-lite"
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# Free tier limits
LIMIT_RPM = 15
LIMIT_RPD = 1000
LIMIT_TPM = 250000

# Safety thresholds
SAFETY_RPD_THRESHOLD = 950  # Stop processing at 950 to avoid hitting the hard 1000 daily limit
SAFETY_DELAY_SECONDS = 5.0   # 15 RPM = 4s min delay, using 5s for extra safety

# Persistent state and log files
STATE_FILE = "gemini_email_state.json"
LOG_CSV_FILE = "gemini_email_log.csv"
OUTPUT_CSV_FILE = "generated_linkedin_emails.csv"
OUTPUT_JSON_FILE = "generated_linkedin_emails.json"

# Candidate Resume Data Fallback
RESUME_DATA_FALLBACK = {
    "Name": "Shashank Jain",
    "Role": "Data Analyst",
    "Skills": [
        "Python", "SQL", "Pandas", "Numpy", "Data Cleaning", "Exploratory Data Analysis (EDA)", "Insight Generation",
        "Power BI", "Tableau", "PostgreSQL", "MongoDB", "FastAPI", "LangChain", "RAG", "Git", "JupyterNotebook", "VS Code", "SDLC",
        "Communication", "Problem Solving", "Teamwork", "Adaptability"
    ],
    "Experience": [
        {
            "Role": "Data Analyst Intern",
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

# Load the actual resume if possible, otherwise use fallback
RESUME_DATA = RESUME_DATA_FALLBACK
RESUME_FILE = "my_resume.docx"

if os.path.exists(RESUME_FILE):
    try:
        from docx import Document
        doc = Document(RESUME_FILE)
        raw_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        if raw_text.strip():
            # Fallback is fine, but we have parsed values
            pass
    except Exception as e:
        pass


def get_pacific_date():
    """Returns the current date in America/Los_Angeles (Pacific Time) timezone.
    Google API resets free tier quotas daily at midnight Pacific Time."""
    utc_now = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        pacific_now = utc_now.astimezone(ZoneInfo("America/Los_Angeles"))
    except Exception:
        # Fallback to America/Los_Angeles offset (UTC-7 for daylight saving, UTC-8 for standard)
        # 2026-07-16 is in summer, so PDT (UTC-7) is active.
        pacific_now = utc_now.astimezone(timezone(timedelta(hours=-7)))
    return pacific_now.strftime("%Y-%m-%d")


def log_message(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def load_state():
    """Loads the application state from JSON."""
    today_pt = get_pacific_date()
    default_state = {
        "daily_date": today_pt,
        "daily_count": 0,
        "pending_queue": [],
        "processed_leads": []
    }
    
    if not os.path.exists(STATE_FILE):
        return default_state
        
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        # Reset counter if a new Pacific Time day has started
        if state.get("daily_date") != today_pt:
            log_message(f"Naya din shuru ho gaya hai (Pacific Time: {today_pt}). Daily limit counter reset kiya ja raha hai.")
            state["daily_date"] = today_pt
            state["daily_count"] = 0
            save_state(state)
            
        return state
    except Exception as e:
        log_message(f"Error loading state file: {e}. Fallback to default state.", "WARNING")
        return default_state


def save_state(state):
    """Saves the application state to JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        log_message(f"Error saving state file: {e}", "ERROR")


def append_to_log_csv(name, profile_link, status, reason):
    """Logs the result of each api request to a CSV log file."""
    file_exists = os.path.exists(LOG_CSV_FILE)
    try:
        with open(LOG_CSV_FILE, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Name", "LinkedIn Profile", "Status", "Reason / Error Message"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name,
                profile_link,
                status,
                reason
            ])
    except Exception as e:
        log_message(f"Failed to write to log CSV: {e}", "ERROR")


def save_generated_email(name, profile_link, email_content):
    """Saves successfully generated emails to structured CSV and JSON outputs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save to CSV
    csv_exists = os.path.exists(OUTPUT_CSV_FILE)
    try:
        with open(OUTPUT_CSV_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not csv_exists:
                writer.writerow(["Name", "LinkedIn Profile", "Generated Email Content", "Status", "Timestamp"])
            writer.writerow([name, profile_link, email_content, "Generated", timestamp])
    except Exception as e:
        log_message(f"Error writing to output CSV: {e}", "ERROR")

    # Save to JSON
    json_data = []
    if os.path.exists(OUTPUT_JSON_FILE):
        try:
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception:
            json_data = []
            
    json_data.append({
        "name": name,
        "linkedin_profile": profile_link,
        "generated_email": email_content,
        "status": "Generated",
        "timestamp": timestamp
    })
    
    try:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4)
    except Exception as e:
        log_message(f"Error writing to output JSON: {e}", "ERROR")


def call_gemini_api(api_key, system_prompt, user_prompt):
    """Makes a direct REST call to Gemini 2.5 Flash-Lite API.
    Returns (status, result_or_reason)
    Status values: 
      - "SUCCESS": Text generated successfully.
      - "RPM_LIMIT_EXCEEDED": Hits RPM limit (429).
      - "DAILY_LIMIT_EXCEEDED": Hits daily quota (429).
      - "API_KEY_SERVICE_BLOCKED": API key is blocked.
      - "UNAUTHORIZED": General auth issue (e.g. invalid key).
      - "ERROR": Other errors.
    """
    url = API_URL_TEMPLATE.format(model=MODEL_NAME, key=api_key)
    
    # Constructing payloads for Generative Language API
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_prompt}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "temperature": 0.7
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            resp_data = response.json()
            try:
                generated_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return "SUCCESS", generated_text
            except (KeyError, IndexError) as parse_err:
                return "ERROR", f"Failed to parse API response structure: {parse_err}. Response was: {resp_data}"
                
        elif response.status_code == 429:
            err_json = {}
            try:
                err_json = response.json()
            except Exception:
                pass
                
            err_msg = err_json.get("error", {}).get("message", "").lower()
            
            # Check error message to classify RPM vs RPD limits
            if "quota" in err_msg or "daily" in err_msg or "per day" in err_msg or "quota group" in err_msg:
                return "DAILY_LIMIT_EXCEEDED", "Daily API quota exhausted."
            else:
                return "RPM_LIMIT_EXCEEDED", "RPM/TPM limit hit."
                
        elif response.status_code in [400, 401, 403]:
            err_json = {}
            try:
                err_json = response.json()
            except Exception:
                pass
            
            err_msg = err_json.get("error", {}).get("message", "")
            err_reason = ""
            try:
                err_reason = err_json["error"]["details"][0]["reason"]
            except (KeyError, IndexError):
                pass
                
            if err_reason == "API_KEY_SERVICE_BLOCKED" or "service_blocked" in err_msg.lower():
                return "API_KEY_SERVICE_BLOCKED", f"API key service blocked: {err_msg}"
            elif "not valid" in err_msg.lower() or "key" in err_msg.lower():
                return "UNAUTHORIZED", f"Invalid API key: {err_msg}"
            else:
                return "UNAUTHORIZED", f"Auth error ({response.status_code}): {err_msg}"
                
        else:
            return "ERROR", f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.RequestException as req_err:
        return "ERROR", f"Network connection error: {req_err}"


def generate_sample_csv():
    """Generates a sample contacts CSV file to get started."""
    sample_file = "linkedin_contacts.csv"
    with open(sample_file, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "LinkedIn Profile", "Company", "Job Title", "Job Description"])
        writer.writerow([
            "Rohan Sharma", 
            "https://linkedin.com/in/rohansharma", 
            "Fintech Solutions", 
            "Junior Data Analyst", 
            "Looking for a candidate with Python, SQL, and data cleaning experience. Power BI is a plus."
        ])
        writer.writerow([
            "Priya Patel", 
            "https://linkedin.com/in/priyapatel", 
            "Health Analytics Corp", 
            "Associate Data Specialist", 
            "Skills required: Pandas, PostgreSQL, Streamlit, and basic machine learning modeling."
        ])
        writer.writerow([
            "Amit Kumar", 
            "https://linkedin.com/in/amitkumar", 
            "TechLogistics Ltd", 
            "Data Analyst Intern", 
            "Internship role requiring ETL pipeline experience, SQL queries, and cohort analysis."
        ])
    log_message(f"Ek sample file '{sample_file}' create kar di gayi hai. Isko edit karke apne contacts daalein.")


def safe_input(prompt, default=""):
    """Reads input from console, handles EOFError gracefully by returning the default value."""
    try:
        val = input(prompt)
        return val if val.strip() else default
    except EOFError:
        log_message(f"\n[INFO] Non-interactive mode/EOF detected. Using default: '{default}'")
        return default


def map_csv_headers(headers):
    """Maps custom columns in a CSV to standard contact fields."""
    headers_clean = [h.strip().lower() for h in headers]
    
    # Map fields
    mapping = {}
    
    # Find name
    for opt in ["name", "contact name", "recruiter", "full name", "contact_name", "recruiter_name", "first name"]:
        if opt in headers_clean:
            mapping["name"] = headers[headers_clean.index(opt)]
            break
            
    # Find profile link
    for opt in ["linkedin profile", "profile link", "linkedin url", "profile_link", "linkedin_profile", "url", "job url", "posting_url", "link"]:
        if opt in headers_clean:
            mapping["profile_link"] = headers[headers_clean.index(opt)]
            break
            
    # Find company
    for opt in ["company name", "company", "company_name", "organisation", "organization"]:
        if opt in headers_clean:
            mapping["company"] = headers[headers_clean.index(opt)]
            break
            
    # Find job title
    for opt in ["job title", "title", "job_title", "role"]:
        if opt in headers_clean:
            mapping["job_title"] = headers[headers_clean.index(opt)]
            break
            
    # Find job description
    for opt in ["required skills", "job description", "skills", "description", "required_skills", "job_description", "summary"]:
        if opt in headers_clean:
            mapping["job_description"] = headers[headers_clean.index(opt)]
            break
            
    return mapping


def load_input_file(filepath):
    """Loads contacts from a CSV or JSON file."""
    leads = []
    
    if filepath.endswith(".csv"):
        try:
            with open(filepath, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if not headers:
                    log_message("CSV file is empty!", "ERROR")
                    return []
                    
                mapping = map_csv_headers(headers)
                
                # Check for critical columns (we need at least company or job title to make an email)
                if "company" not in mapping or "job_title" not in mapping:
                    log_message("Could not map critical columns 'Company' or 'Job Title' in CSV headers.", "ERROR")
                    return []
                
                has_name_col = "name" in mapping
                if not has_name_col:
                    log_message("Name column not found in CSV headers. Using 'Hiring Team' as fallback.", "WARNING")
                    
                for row in reader:
                    name_val = row.get(mapping["name"], "").strip() if has_name_col else "Hiring Team"
                    profile_val = row.get(mapping.get("profile_link", ""), "").strip()
                    company_val = row.get(mapping.get("company", ""), "Unknown Company").strip()
                    title_val = row.get(mapping.get("job_title", ""), "Data Analyst").strip()
                    desc_val = row.get(mapping.get("job_description", ""), "").strip()
                    
                    if company_val and title_val:
                        leads.append({
                            "name": name_val or "Hiring Team",
                            "linkedin_profile": profile_val or "Not Available",
                            "company": company_val,
                            "job_title": title_val,
                            "job_description": desc_val
                        })
        except Exception as e:
            log_message(f"Error reading CSV file: {e}", "ERROR")
            
    elif filepath.endswith(".json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                for item in data:
                    name_val = item.get("name") or item.get("Name") or "Hiring Team"
                    profile_val = item.get("linkedin_profile") or item.get("LinkedIn Profile") or item.get("linkedin_url") or item.get("profile_link")
                    company_val = item.get("company") or item.get("Company") or "Unknown Company"
                    title_val = item.get("job_title") or item.get("Job Title") or "Data Analyst"
                    desc_val = item.get("job_description") or item.get("Job Description") or item.get("required_skills") or item.get("skills") or ""
                    
                    if company_val and title_val:
                        leads.append({
                            "name": name_val.strip(),
                            "linkedin_profile": (profile_val or "Not Available").strip(),
                            "company": company_val.strip(),
                            "job_title": title_val.strip(),
                            "job_description": desc_val.strip()
                        })
        except Exception as e:
            log_message(f"Error reading JSON file: {e}", "ERROR")
            
    return leads


def main():
    log_message("="*60)
    log_message("GEMINI 2.5 FLASH-LITE LINKEDIN EMAIL GENERATOR (FREE TIER)")
    log_message("="*60)

    # API Key check
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log_message("GEMINI_API_KEY environment variable missing!", "ERROR")
        log_message("Please add GEMINI_API_KEY to your .env file or export it in your shell environment.", "ERROR")
        sys.exit(1)

    # Load persistent state
    state = load_state()
    
    # Check if we should resume pending leads
    resume_mode = False
    if state["pending_queue"]:
        log_message(f"Found {len(state['pending_queue'])} contacts in the pending queue from last session.")
        choice = safe_input("Do you want to resume processing from where you left off? (Y/n): ", "y").strip().lower()
        if choice in ["", "y", "yes"]:
            resume_mode = True
            
    if not resume_mode:
        # Load from file
        default_file = "linkedin_contacts.csv"
        # Check if the jobs CSV exists and suggest it if no contacts CSV
        if not os.path.exists(default_file) and os.path.exists("linkedin_fresher_data_analyst_jobs_merged.csv"):
            default_file = "linkedin_fresher_data_analyst_jobs_merged.csv"
            
        filepath = safe_input(f"Enter the path to input CSV or JSON (default: {default_file}): ", default_file).strip()
        if not filepath:
            filepath = default_file
            
        if not os.path.exists(filepath):
            log_message(f"File '{filepath}' not found!", "ERROR")
            gen_sample = safe_input("Do you want to generate a sample contacts CSV file to start? (Y/n): ", "y").strip().lower()
            if gen_sample in ["", "y", "yes"]:
                generate_sample_csv()
            sys.exit(0)
            
        leads = load_input_file(filepath)
        if not leads:
            log_message(f"No valid contacts parsed from file '{filepath}'. Exiting.", "ERROR")
            sys.exit(1)
            
        log_message(f"Successfully loaded {len(leads)} contacts from '{filepath}'.")
        
        # Reset queue in state
        state["pending_queue"] = leads
        # Ask to clear processed log for this run
        clear_processed = safe_input("Clear processed leads history in state? (y/N): ", "n").strip().lower()
        if clear_processed == "y":
            state["processed_leads"] = []
            
        save_state(state)

    # Main Processing loop
    total_leads = len(state["pending_queue"])
    success_count = 0
    failed_count = 0
    
    log_message(f"Starting processing. Total leads in queue: {total_leads}")
    
    last_request_time = 0
    
    while state["pending_queue"]:
        # 1. Check Daily usage limit (Safety check)
        if state["daily_count"] >= SAFETY_RPD_THRESHOLD:
            log_message("="*60, "WARNING")
            log_message(f"Daily usage threshold ({SAFETY_RPD_THRESHOLD}/{LIMIT_RPD}) reached.", "WARNING")
            log_message("Daily free quota is near exhaustion. Stopping processing to prevent hard error lockout.", "WARNING")
            log_message("Daily free quota reset Pacific Time midnight ko hoga (India mein dopahar ~12:30/1:30 PM).", "WARNING")
            log_message("="*60, "WARNING")
            break
            
        # Get lead
        lead = state["pending_queue"][0]
        name = lead["name"]
        profile = lead["linkedin_profile"]
        company = lead["company"]
        title = lead["job_title"]
        desc = lead["job_description"]
        
        log_message(f"Processing Lead: {name} | Title: {title} | Company: {company}")
        
        # 2. Rate Limiting Safety Delay (Sequential execution)
        elapsed = time.time() - last_request_time
        if elapsed < SAFETY_DELAY_SECONDS:
            sleep_time = SAFETY_DELAY_SECONDS - elapsed
            # Add a small sub-second jitter
            sleep_time += random.uniform(0.1, 0.5)
            log_message(f"Sleeping {sleep_time:.2f} seconds to protect RPM limit...")
            time.sleep(sleep_time)
            
        # 3. Setup Prompts
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
- Company Name: {company}
- Job Title: {title}
- Job Description/Required Skills: {desc}

Write a personalized cold email from {RESUME_DATA['Name']} to the hiring team at {company} for the '{title}' position. Match relevant skills and projects from his resume. Make it short (5-6 lines), professional, and direct. Address the email with 'Dear Hiring Team,'. Start with the Subject line.
Do NOT include candidate's name in the subject line. Do NOT write any sign-off or signature block.
"""
        
        # 4. Make API Call with Retry Logic
        last_request_time = time.time()
        
        status = "SUCCESS"
        result_text = ""
        api_error_type = None
        
        # Retry mechanism for RPM/TPM limits (Max 5 attempts)
        max_retries = 5
        retry_delays = [2, 4, 8, 16, 32]
        
        for attempt in range(max_retries + 1):
            # API Call
            api_status, api_result = call_gemini_api(api_key, system_prompt, user_prompt)
            state["daily_count"] += 1  # Increment daily count for tracking (even fails represent requests made)
            save_state(state)
            
            if api_status == "SUCCESS":
                status = "SUCCESS"
                result_text = api_result
                break
                
            elif api_status == "RPM_LIMIT_EXCEEDED":
                api_error_type = "RPM_LIMIT_EXCEEDED"
                if attempt < max_retries:
                    delay = retry_delays[attempt] + random.uniform(0.1, 0.9)
                    log_message(f"RPM/TPM limit hit. Retry attempt {attempt+1}/{max_retries} in {delay:.2f}s...", "WARNING")
                    time.sleep(delay)
                    last_request_time = time.time()
                    continue
                else:
                    status = "FAILED"
                    result_text = "RPM rate limit retries exhausted."
                    break
                    
            elif api_status == "DAILY_LIMIT_EXCEEDED":
                api_error_type = "DAILY_LIMIT_EXCEEDED"
                status = "PAUSED"
                result_text = "Daily limit hit during call."
                break
                
            elif api_status in ["API_KEY_SERVICE_BLOCKED", "UNAUTHORIZED"]:
                api_error_type = api_status
                status = "CRITICAL_AUTH_ERROR"
                result_text = api_result
                break
                
            else: # general ERROR
                status = "FAILED"
                result_text = api_result
                break
                
        # 5. Handle Call Results
        if status == "SUCCESS":
            success_count += 1
            log_message(f"[SUCCESS] Cold email generated for {name}.")
            
            # Save generated outputs
            save_generated_email(name, profile, result_text)
            
            # Log to CSV logs
            append_to_log_csv(name, profile, "SUCCESS", "Generated Successfully")
            
            # Move from pending queue to processed
            state["pending_queue"].pop(0)
            state["processed_leads"].append({
                "name": name,
                "linkedin_profile": profile,
                "company": company,
                "job_title": title,
                "status": "success",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_state(state)
            
        elif api_error_type == "DAILY_LIMIT_EXCEEDED":
            log_message("="*60, "WARNING")
            log_message("Daily free quota khatam ho gaya!", "WARNING")
            log_message("Agla reset midnight Pacific Time (India mein dopahar ~12:30/1:30 PM) ko hoga.", "WARNING")
            log_message("Processing pause ki ja rahi hai. Pending leads queue mein saved hain.", "WARNING")
            log_message("="*60, "WARNING")
            append_to_log_csv(name, profile, "PAUSED", "Daily Quota limit reached.")
            break
            
        elif status == "CRITICAL_AUTH_ERROR":
            log_message("="*60, "ERROR")
            log_message("CRITICAL AUTHENTICATION ERROR DETECTED!", "ERROR")
            log_message(result_text, "ERROR")
            log_message("Script immediate terminate ho raha hai. State is preserved.", "ERROR")
            log_message("="*60, "ERROR")
            append_to_log_csv(name, profile, "CRITICAL_AUTH_ERROR", result_text)
            break
            
        else: # FAILED (other errors or RPM retries exhausted)
            failed_count += 1
            log_message(f"[FAILED] Failed to generate email for {name}: {result_text}", "ERROR")
            append_to_log_csv(name, profile, "FAILED", result_text)
            
            # Remove from pending queue since it's a structural or request error, not a rate limit block
            state["pending_queue"].pop(0)
            state["processed_leads"].append({
                "name": name,
                "linkedin_profile": profile,
                "company": company,
                "job_title": title,
                "status": "failed",
                "reason": result_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_state(state)
            
        # 6. Display Live Counter
        remaining_leads = len(state["pending_queue"])
        log_message(f"Live counter: {success_count} emails generated / {remaining_leads} pending / {failed_count} failed / Aaj ki daily limit: {state['daily_count']}/1000 used")
        print("-" * 50)

    # Finished run summary
    log_message("="*60)
    log_message("RUN SUMMARY")
    log_message(f"Success Generations: {success_count}")
    log_message(f"Failed Generations: {failed_count}")
    log_message(f"Pending Leads remaining in queue: {len(state['pending_queue'])}")
    log_message(f"Today's Daily Usage: {state['daily_count']}/1000 requests used (Pacific date: {state['daily_date']})")
    log_message("="*60)


if __name__ == "__main__":
    main()
