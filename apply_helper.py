import os
import csv
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

SESSION_FILE = "linkedin_session.json"

def get_absolute_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def log(msg):
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [APPLY] {msg}", flush=True)

def is_logged_in(page):
    """DOM elements se check karo ki logged in hain ya nahi."""
    try:
        for sel in ["div.global-nav__me", "img.global-nav__me-photo"]:
            if page.locator(sel).first.count() > 0:
                return True
        if any(x in page.url for x in ["login", "authwall", "signup"]):
            return False
        return False
    except Exception:
        return False

def ensure_login(page, context, session_path):
    """Agar already logged in hain to skip, nahi to wait karo."""
    if is_logged_in(page):
        log("Already logged in. Session valid.")
        return True

    log("Session expired or not found. Navigating to feed to verify...")
    try:
        page.goto("https://www.linkedin.com/feed/", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    if is_logged_in(page):
        log("Session valid after reload.")
        context.storage_state(path=session_path)
        return True

    # Login required — wait for user to login manually (2 minutes)
    log("LOGIN REQUIRED: Please log in to LinkedIn in the browser window that opened.")
    log("Waiting up to 2 minutes for you to complete login...")
    for _ in range(24):
        page.wait_for_timeout(5000)
        if is_logged_in(page):
            log("Login detected! Saving session...")
            context.storage_state(path=session_path)
            return True

    log("Timeout: Login was not completed.")
    return False


def apply_to_single_job(page, job_url, company_name, job_title):
    """
    Ek job pe apply karo using existing page (already logged in).
    Returns: 'Applied', 'Failed (No Easy Apply)', 'Failed', 'Manual Action Required'
    """
    log(f"Navigating to job: {job_title} @ {company_name}")
    log(f"URL: {job_url}")

    try:
        page.goto(job_url, timeout=45000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)
    except Exception as e:
        log(f"ERROR: Could not load job URL — {e}")
        return "Failed (URL Error)"

    # Easy Apply button dhundo
    easy_apply_selectors = [
        "button.jobs-apply-button",
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
    ]
    apply_btn = None
    for sel in easy_apply_selectors:
        btn = page.locator(sel).first
        try:
            if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                apply_btn = btn
                log(f"Easy Apply button found: '{btn.inner_text().strip()}'")
                break
        except Exception:
            pass

    if not apply_btn:
        log("No Easy Apply button found. This job requires external application.")
        return "Failed (No Easy Apply)"

    log("Clicking Easy Apply...")
    apply_btn.click()
    page.wait_for_timeout(3000)

    # Application wizard iterate karo
    phone_number = os.environ.get("LINKEDIN_PHONE", "+91-7878927128")
    steps_completed = 0
    max_steps = 15

    while steps_completed < max_steps:
        page.wait_for_timeout(1500)

        # Phone number fill
        try:
            ph = page.locator("input[id*='phoneNumber'], input[id*='phone']").first
            if ph.count() > 0 and ph.is_visible():
                current_val = ph.input_value()
                if not current_val or current_val.strip() == "":
                    ph.fill(phone_number)
                    log("Filled phone number.")
        except Exception:
            pass

        # Resume upload
        try:
            resume_input = page.locator("input[type='file']").first
            if resume_input.count() > 0:
                pdf_path = get_absolute_path("my_resume.pdf")
                docx_path = get_absolute_path("my_resume.docx")
                if os.path.exists(pdf_path):
                    resume_input.set_input_files(pdf_path)
                    log("Uploaded my_resume.pdf.")
                elif os.path.exists(docx_path):
                    resume_input.set_input_files(docx_path)
                    log("Uploaded my_resume.docx.")
        except Exception:
            pass

        # Radio buttons — 'Yes' prefer karo
        try:
            radio_groups = page.locator("fieldset[data-test-form-builder-fieldset]")
            for r_idx in range(radio_groups.count()):
                group = radio_groups.nth(r_idx)
                if group.locator("input[type='radio']:checked").count() == 0:
                    yes_opt = group.locator("label:has-text('Yes'), input[value='Yes'], input[value='yes']").first
                    if yes_opt.count() > 0 and yes_opt.is_visible():
                        yes_opt.click()
                        log("Auto-selected 'Yes' for radio group.")
                    else:
                        first_r = group.locator("input[type='radio']").first
                        if first_r.count() > 0 and first_r.is_visible():
                            first_r.click()
                            log("Auto-selected first radio option.")
        except Exception:
            pass

        # Select dropdowns
        try:
            selects = page.locator("select")
            for s_idx in range(selects.count()):
                sel_el = selects.nth(s_idx)
                if sel_el.is_visible() and not sel_el.input_value():
                    opts = sel_el.locator("option")
                    for o_idx in range(1, opts.count()):
                        val = opts.nth(o_idx).get_attribute("value")
                        if val:
                            sel_el.select_option(val)
                            log(f"Selected dropdown option: '{val}'")
                            break
        except Exception:
            pass

        # Text inputs — experience/years = '1'
        try:
            text_inputs = page.locator("input[type='text']:visible, textarea:visible")
            for t_idx in range(text_inputs.count()):
                inp = text_inputs.nth(t_idx)
                if inp.is_visible() and not inp.input_value():
                    id_attr = inp.get_attribute("id") or ""
                    label_text = ""
                    if id_attr:
                        lbl = page.locator(f"label[for='{id_attr}']").first
                        if lbl.count() > 0:
                            label_text = lbl.inner_text().lower()
                    inp.fill("1")
                    log(f"Filled empty field (label: '{label_text or 'unknown'}') with '1'.")
        except Exception:
            pass

        # Check for Done/Success screen
        done_btn = page.locator("button:has-text('Done'), button:has-text('Dismiss'), .artdeco-modal__dismiss").first
        if done_btn.count() > 0 and done_btn.is_visible():
            log("Application SUCCESSFUL!")
            try:
                done_btn.click()
            except Exception:
                pass
            return "Applied"

        # Primary action button
        action_btn = page.locator(
            "footer button.artdeco-button--primary, "
            ".jobs-easy-apply-modal__footer-container button.artdeco-button--primary, "
            "button.artdeco-button--primary"
        ).first

        if action_btn.count() == 0 or not action_btn.is_visible():
            log("No action button visible. Breaking wizard loop.")
            return "Manual Action Required"

        is_disabled = (action_btn.get_attribute("aria-disabled") == "true") or (not action_btn.is_enabled())
        if is_disabled:
            log("Button is disabled — waiting for required fields (up to 20s)...")
            enabled = False
            for _ in range(10):
                page.wait_for_timeout(2000)
                is_disabled = (action_btn.get_attribute("aria-disabled") == "true") or (not action_btn.is_enabled())
                if not is_disabled:
                    enabled = True
                    break
            if not enabled:
                log("Form still incomplete. Marking as Manual Action Required.")
                return "Manual Action Required"

        btn_text = action_btn.inner_text().strip().lower()
        log(f"Clicking: '{action_btn.inner_text().strip()}'")
        action_btn.click()
        steps_completed += 1
        page.wait_for_timeout(2500)

        if "submit" in btn_text:
            page.wait_for_timeout(4000)
            log("Submit clicked. Marking as Applied.")
            return "Applied"

    return "Failed (Max Steps)"


def auto_apply_to_job(job_url, company_name, job_title):
    """
    Single-job apply (called from individual Apply button).
    Opens its own browser for this one job.
    """
    log(f"Starting single-job apply: '{job_title}' @ {company_name}")
    session_path = get_absolute_path(SESSION_FILE)
    status = "Failed"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        ctx_args = {"no_viewport": True}
        if os.path.exists(session_path):
            try:
                ctx_args["storage_state"] = session_path
            except Exception:
                pass
        context = browser.new_context(**ctx_args)
        page = context.new_page()

        # Navigate to feed first to check login
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        logged_in = ensure_login(page, context, session_path)
        if not logged_in:
            browser.close()
            return "Failed (Login Required)"

        status = apply_to_single_job(page, job_url, company_name, job_title)
        log(f"Result: {status}")
        browser.close()

    return status


def auto_apply_batch(jobs_list, max_jobs=5):
    """
    Multiple jobs ke liye EK hi browser session use karo.
    Called from auto_apply_all route.
    Returns: list of (job_url, status)
    """
    session_path = get_absolute_path(SESSION_FILE)
    results = []

    log(f"Starting batch apply for {min(len(jobs_list), max_jobs)} jobs using single browser session...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        ctx_args = {"no_viewport": True}
        if os.path.exists(session_path):
            try:
                ctx_args["storage_state"] = session_path
            except Exception:
                pass
        context = browser.new_context(**ctx_args)
        page = context.new_page()

        # Pehle login verify karo
        try:
            page.goto("https://www.linkedin.com/feed/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        logged_in = ensure_login(page, context, session_path)
        if not logged_in:
            browser.close()
            log("Batch apply aborted — login failed.")
            return [(j.get("Job Posting Link / URL", ""), "Failed (Login Required)") for j in jobs_list[:max_jobs]]

        log("Login verified. Starting batch apply loop...")

        for idx, job in enumerate(jobs_list[:max_jobs]):
            job_url = job.get("Job Posting Link / URL") or job.get("Job URL", "")
            company = job.get("Company Name") or job.get("Company", "Unknown")
            title = job.get("Job Title") or job.get("Title", "Unknown")

            if not job_url:
                log(f"[{idx+1}/{max_jobs}] Skipping — no URL found.")
                results.append(("", "Skipped"))
                continue

            log(f"[{idx+1}/{max_jobs}] Applying: '{title}' @ {company}")
            try:
                status = apply_to_single_job(page, job_url, company, title)
            except Exception as e:
                log(f"[{idx+1}/{max_jobs}] Error during apply: {e}")
                status = "Failed"

            log(f"[{idx+1}/{max_jobs}] Result: {status}")
            results.append((job_url, status))

            if idx < max_jobs - 1:
                log("Waiting 5s before next application...")
                time.sleep(5)

        browser.close()
        log(f"Batch apply complete. {len(results)} jobs processed.")

    return results


def update_job_status_in_files(job_url, new_status):
    """
    'Application Status' column update karo CSV aur JSON dono mein.
    """
    normalized_target_url = job_url.split("?")[0].rstrip("/")
    dir_path = os.path.dirname(os.path.abspath(__file__))

    targets = []
    try:
        for file in os.listdir(dir_path):
            if file.startswith("linkedin_") and (file.endswith(".csv") or file.endswith(".json")) and file != "linkedin_session.json":
                targets.append(os.path.join(dir_path, file))
    except Exception as e:
        log(f"Directory scan warning: {e}")

    for target in targets:
        if not os.path.exists(target):
            continue
        try:
            if target.endswith(".json"):
                with open(target, "r", encoding="utf-8") as f:
                    jobs = json.load(f)
                updated = False
                for job in jobs:
                    url = job.get("Job Posting Link / URL", "") or job.get("Job URL", "")
                    if url and url.split("?")[0].rstrip("/") == normalized_target_url:
                        job["Application Status"] = new_status
                        updated = True
                if updated:
                    with open(target, "w", encoding="utf-8") as f:
                        json.dump(jobs, f, indent=4, ensure_ascii=False)
                    log(f"JSON updated: {os.path.basename(target)} → '{new_status}'")

            elif target.endswith(".csv"):
                rows = []
                headers = []
                with open(target, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    headers = list(reader.fieldnames or [])
                    if "Application Status" not in headers:
                        headers.append("Application Status")
                    rows = list(reader)
                updated = False
                for row in rows:
                    url = row.get("Job Posting Link / URL", "") or row.get("Job URL", "")
                    if url and url.split("?")[0].rstrip("/") == normalized_target_url:
                        row["Application Status"] = new_status
                        updated = True
                if updated:
                    with open(target, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        for row in rows:
                            writer.writerow(row)
                    log(f"CSV updated: {os.path.basename(target)} → '{new_status}'")

        except Exception as e:
            log(f"Error updating {target}: {e}")
