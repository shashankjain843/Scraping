import os
import csv
import time
import json
import sys
import requests

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeError in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configurations
# You can change the model name below (e.g. "google/gemini-2.5-flash", "meta-llama/llama-3-8b-instruct", etc.)
MODEL_NAME = "openai/gpt-4o-mini"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Resume Data (Hardcoded as specified)
RESUME_DATA = {
    "Name": "Shashank Jain",
    "Role": "Data Analyst",
    "Skills": ["Python", "SQL", "Pandas", "NumPy", "Power BI", "Tableau", "PostgreSQL", "MongoDB", "FastAPI", "LangChain", "RAG", "EDA"],
    "Experience": [
        {
            "Role": "Data Analyst Intern",
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

def get_api_key():
    """Retrieve the API key from the environment variable or .env file."""
    # Check if .env file exists and read from it if variable not already set
    if not os.environ.get("OPENROUTER_API_KEY") and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        if len(parts) == 2 and parts[0].strip() == "OPENROUTER_API_KEY":
                            os.environ["OPENROUTER_API_KEY"] = parts[1].strip().strip('"').strip("'")
                            break
        except Exception:
            pass

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("\n[ERROR] OPENROUTER_API_KEY environment variable is not set!")
        print("Please set it in your terminal before running this script.")
        print("Example (PowerShell): $env:OPENROUTER_API_KEY=\"your-key-here\"")
        print("Example (CMD):        set OPENROUTER_API_KEY=your-key-here")
        print("Example (Bash):       export OPENROUTER_API_KEY=\"your-key-here\"\n")
        # Ask user directly as a fallback to make it easy to use
        api_key = input("Alternatively, paste your OpenRouter API Key here (or press Enter to exit): ").strip()
        if not api_key:
            sys.exit(1)
    return api_key

def generate_cold_email(api_key, company_name, job_title, job_description):
    """
    Call the OpenRouter API to generate a personalized cold email.
    Matches skills/projects from the resume and ensures no placeholders are present.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/shashankjain843",  # Optional rank header
        "X-Title": "Cold Email Generator"
    }

    # Custom instructions for the model
    system_prompt = (
        "Tu ek professional cold email writer hai. Email short, direct, no fluff, 5-6 lines ka ho. "
        "Candidate ke resume se sirf wahi skills/projects mention karo jo job description se match karte hain. "
        "Generic buzzwords mat use karo. Write the email in English. "
        "Do not use placeholders like [Company Name], [Job Title], [Your Name], or any brackets. "
        "Always replace them with the actual names provided. "
        "The response must start directly with 'Subject: [Subject Line]' followed by the email body. "
        "Do not write any introductory or concluding conversation text, just start with Subject:."
    )

    user_prompt = f"""
Candidate Resume:
- Name: {RESUME_DATA['Name']}
- Target Role: {RESUME_DATA['Role']}
- Contact: Phone: {RESUME_DATA['Contact']['Phone']}, LinkedIn: {RESUME_DATA['Contact']['LinkedIn']}, GitHub: {RESUME_DATA['Contact']['GitHub']}
- Skills: {', '.join(RESUME_DATA['Skills'])}
- Experience: Data Analyst Intern at {RESUME_DATA['Experience'][0]['Company']} ({RESUME_DATA['Experience'][0]['Details']})
- Projects:
  1. {RESUME_DATA['Projects'][0]['Name']} (Technologies: {', '.join(RESUME_DATA['Projects'][0]['Technologies'])})
  2. {RESUME_DATA['Projects'][1]['Name']} (Technologies: {', '.join(RESUME_DATA['Projects'][1]['Technologies'])})

Job Listing details:
- Company Name: {company_name}
- Job Title: {job_title}
- Job Description/Required Skills: {job_description}

Write a personalized cold email from {RESUME_DATA['Name']} to the recruiter or hiring manager at {company_name} for the '{job_title}' position. Match relevant skills and projects from his resume. Make it short (5-6 lines), professional, and direct. Start with the Subject line.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"  [ERROR] Invalid API response format: {data}")
            return None
    except Exception as e:
        print(f"  [ERROR] API call failed: {e}")
        return None

def run_mode_a(api_key):
    """Mode A: Standalone (Manual input)"""
    print("\n--- MODE A: Standalone (Manual Cold Email Generator) ---")
    company_name = input("Enter Company Name: ").strip()
    job_title = input("Enter Job Title: ").strip()

    print("\nEnter Job Description / Required Skills.")
    print("Options:")
    print("1. Paste/type text directly (Press Enter, then type 'DONE' on a new line and press Enter to finish)")
    print("2. Type 'FILE:<filepath>' to read the description from a text file (e.g. FILE:desc.txt)")
    
    lines = []
    first_input = input("Input choice or first line: ").strip()
    
    if first_input.upper().startswith("FILE:"):
        file_path = first_input[5:].strip()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                job_desc = f.read().strip()
            print(f"Successfully read job description from: {file_path}")
        except Exception as e:
            print(f"[ERROR] Could not read file: {e}. Please enter description manually.")
            return
    else:
        if first_input != "DONE":
            lines.append(first_input)
        while True:
            line = input()
            if line.strip() == "DONE":
                break
            lines.append(line)
        job_desc = "\n".join(lines)

    if not company_name or not job_title or not job_desc:
        print("[ERROR] Company Name, Job Title, and Job Description cannot be empty!")
        return

    print("\nGenerating email using OpenRouter API...")
    email_text = generate_cold_email(api_key, company_name, job_title, job_desc)
    
    if email_text:
        print("\n" + "="*50)
        print("GENERATED COLD EMAIL:")
        print("="*50)
        print(email_text)
        print("="*50)
        
        # Save to text file
        out_filename = "cold_email_output.txt"
        try:
            with open(out_filename, "w", encoding="utf-8") as f:
                f.write(f"Company: {company_name}\nJob Title: {job_title}\n\n{email_text}\n")
            print(f"\n[SUCCESS] Email successfully saved to: {out_filename}")
        except Exception as e:
            print(f"[WARNING] Failed to save to file: {e}")
    else:
        print("[ERROR] Could not generate cold email.")

def run_mode_b(api_key):
    """Mode B: Scraper Integration (Automatic use from CSV)"""
    print("\n--- MODE B: Scraper Integration (Automatic Cold Email Generator) ---")
    
    # List files in current directory to help user choose
    files = [f for f in os.listdir(".") if f.endswith(".csv")]
    print("\nAvailable CSV files in current directory:")
    for idx, f in enumerate(files, 1):
        print(f" {idx}. {f}")
    
    default_file = "linkedin_fresher_data_analyst_jobs_merged.csv"
    csv_path = input(f"\nEnter the path to the jobs CSV file (default: {default_file}): ").strip()
    if not csv_path:
        csv_path = default_file

    if not os.path.exists(csv_path):
        print(f"[ERROR] File '{csv_path}' does not exist!")
        return

    # Check if the filename contains "naukri" (Skip Naukri.com files as requested)
    if "naukri" in os.path.basename(csv_path).lower():
        print(f"\n[INFO] Skipping file '{csv_path}' because it belongs to Naukri.com (only LinkedIn is processed).")
        return

    print(f"\nReading jobs from: {csv_path}...")
    jobs = []
    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            
            # Map columns dynamically to support different layouts
            headers = reader.fieldnames
            if not headers:
                print("[ERROR] CSV file is empty or has no headers!")
                return
                
            # Helper to find column name matching keys
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
            source_col = find_col(["Source Platform", "source", "Source"])

            if not company_col or not title_col:
                print(f"[ERROR] Could not map key columns. Found columns: {headers}")
                print("Make sure the CSV has at least 'Company Name' and 'Job Title' columns.")
                return

            for row in reader:
                # Double check to skip any Naukri jobs from the platform value
                if source_col:
                    source_val = (row.get(source_col) or "").strip().lower()
                    if "naukri" in source_val:
                        continue # Skip Naukri jobs
                
                comp = (row.get(company_col) or "").strip()
                title = (row.get(title_col) or "").strip()
                skills = (row.get(skills_col) or "Data Analyst skills").strip()
                url = (row.get(url_col) or "Not Available").strip()
                
                if comp and title:
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "skills": skills,
                        "url": url
                    })
    except Exception as e:
        print(f"[ERROR] Failed to read CSV file: {e}")
        return

    if not jobs:
        print("[INFO] No LinkedIn jobs found to process in the CSV.")
        return

    print(f"Found {len(jobs)} LinkedIn job(s) to process.")
    output_file = "generated_cold_emails.csv"
    
    # Check if we should append or overwrite
    mode = "w"
    write_header = True
    if os.path.exists(output_file):
        ans = input(f"Output file '{output_file}' already exists. (A)ppend, (O)verwrite, or (C)ancel? ").strip().upper()
        if ans == "A":
            mode = "a"
            write_header = False
        elif ans == "C":
            print("Operation cancelled.")
            return

    processed_count = 0
    success_count = 0

    # Open file for writing immediately so we write as we go (prevents loss if interrupted)
    try:
        with open(output_file, mode=mode, encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            if write_header:
                writer.writerow(["Company", "Job Title", "Generated Email", "Job URL"])

            for idx, job in enumerate(jobs, 1):
                print(f"\n[{idx}/{len(jobs)}] Processing: {job['title']} at {job['company']}")
                
                email_text = generate_cold_email(api_key, job['company'], job['title'], job['skills'])
                processed_count += 1
                
                if email_text:
                    writer.writerow([job['company'], job['title'], email_text, job['url']])
                    out_f.flush()  # force write to disk
                    success_count += 1
                    print(f"  [SUCCESS] Cold email generated and saved.")
                else:
                    print(f"  [SKIPPED] Failed to generate email for this job.")

                # Delay between calls to respect rate limits
                if idx < len(jobs):
                    delay = 2.5
                    print(f"  Waiting {delay} seconds...")
                    time.sleep(delay)
                    
        print(f"\n[FINISHED] Processed {processed_count} jobs. Successfully generated {success_count} emails.")
        print(f"Results saved to: {output_file}")
    except Exception as e:
        print(f"[ERROR] Failed writing to output file: {e}")

def main():
    print("==================================================")
    print("      AUTOMATIC COLD EMAIL GENERATOR (OPENROUTER) ")
    print("==================================================")
    
    api_key = get_api_key()
    
    print("\nSelect Mode:")
    print("1. Mode A – Standalone (Enter job details manually)")
    print("2. Mode B – Scraper Integration (Process LinkedIn jobs from CSV)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    if choice == "1":
        run_mode_a(api_key)
    elif choice == "2":
        run_mode_b(api_key)
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
