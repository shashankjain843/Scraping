import os
import csv
import json
import time
from playwright.sync_api import sync_playwright

SESSION_FILE = "linkedin_session.json"

def get_absolute_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def load_resume_data():
    try:
        from generate_cold_emails import RESUME_DATA
        if RESUME_DATA:
            return RESUME_DATA
    except:
        pass
    
    return {
        "Name": "Shashank Jain",
        "Contact": {
            "Phone": "+91-7878927128",
            "Email": "shashankjain@example.com"
        }
    }

def auto_apply_to_job(job_url, company_name, job_title):
    """
    Automates/Semi-automates the application to a specific job.
    Returns status: 'Applied', 'Failed', or 'Manual Action Required'
    """
    print(f"\n[AUTO-APPLY] Starting application process for {job_title} at {company_name}...")
    
    resume_data = load_resume_data()
    phone_number = resume_data.get("Contact", {}).get("Phone", "")

    status = "Failed"

    with sync_playwright() as p:
        # Launch browser in non-headless mode so the user can interact / login
        print("[AUTO-APPLY] Launching Chrome in non-headless mode...")
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        
        # Load session state if it exists
        session_path = get_absolute_path(SESSION_FILE)
        if os.path.exists(session_path):
            print("[AUTO-APPLY] Loading existing LinkedIn session...")
            try:
                context = browser.new_context(storage_state=session_path, no_viewport=True)
            except Exception as e:
                print(f"[AUTO-APPLY] Error loading session file: {e}. Starting clean context...")
                context = browser.new_context(no_viewport=True)
        else:
            print("[AUTO-APPLY] No existing session found. Starting new session...")
            context = browser.new_context(no_viewport=True)
            
        page = context.new_page()
        
        # Check login state
        page.goto("https://www.linkedin.com/feed/", timeout=45000)
        page.wait_for_timeout(3000)
        
        if "login" in page.url or "signin" in page.url or page.locator("a:has-text('Sign in')").count() > 0:
            print("[AUTO-APPLY] [REQUIRED] Please log in to LinkedIn in the opened browser window.")
            print("[AUTO-APPLY] Waiting for login completion...")
            # Wait up to 2 minutes for user to complete login manually
            logged_in = False
            for _ in range(24):
                page.wait_for_timeout(5000)
                if "feed" in page.url or "messaging" in page.url or page.locator("a[data-global-header-item='linkedin-home']").count() > 0:
                    print("[AUTO-APPLY] Login detected! Saving session...")
                    page.wait_for_timeout(3000)
                    context.storage_state(path=session_path)
                    logged_in = True
                    break
            if not logged_in:
                print("[AUTO-APPLY] Timeout waiting for login. Closing browser...")
                browser.close()
                return "Failed (Login Required)"

        # Navigate to the job listing page
        print(f"[AUTO-APPLY] Navigating to job: {job_url}")
        try:
            page.goto(job_url, timeout=45000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[AUTO-APPLY] Error loading job url: {e}")
            browser.close()
            return "Failed (URL Load Error)"

        # Check for Easy Apply button
        easy_apply_selectors = [
            "button.jobs-apply-button",
            "button:has-text('Easy Apply')",
            "button:has-text('Apply now')"
        ]
        
        apply_btn = None
        for selector in easy_apply_selectors:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                apply_btn = btn
                break
                
        if not apply_btn:
            print("[AUTO-APPLY] No Easy Apply button found. Job might require external application.")
            page.wait_for_timeout(5000)
            browser.close()
            return "Failed (No Easy Apply)"

        print("[AUTO-APPLY] Clicking Easy Apply button...")
        apply_btn.click()
        page.wait_for_timeout(3000)

        # Iterate through Easy Apply wizard screens
        steps_completed = 0
        max_steps = 12
        status = "Failed"

        while steps_completed < max_steps:
            # Fill standard contact fields if they appear on screen
            try:
                phone_input = page.locator("input[id*='phoneNumber'], input[id*='phone']").first
                if phone_input.count() > 0 and phone_input.is_visible() and not phone_input.input_value():
                    phone_input.fill(phone_number)
                    print("[AUTO-APPLY] Filled phone number.")
            except Exception as e:
                print(f"[AUTO-APPLY] Phone fill warning: {e}")
                
            # If resume upload is requested
            try:
                resume_input = page.locator("input[type='file'][id*='resume']").first
                if resume_input.count() > 0 and resume_input.is_visible():
                    docx_resume = get_absolute_path("my_resume.docx")
                    if os.path.exists(docx_resume):
                        resume_input.set_input_files(docx_resume)
                        print("[AUTO-APPLY] Uploaded my_resume.docx.")
            except Exception as e:
                print(f"[AUTO-APPLY] Resume upload warning: {e}")

            # Smart Auto-fill for Radio Buttons
            try:
                radio_groups = page.locator("fieldset[data-test-form-builder-fieldset]")
                for r_idx in range(radio_groups.count()):
                    group = radio_groups.nth(r_idx)
                    checked = group.locator("input[type='radio']:checked")
                    if checked.count() == 0:
                        yes_radio = group.locator("label:has-text('Yes'), label:has-text('yes'), input[value='Yes'], input[value='yes']").first
                        if yes_radio.count() > 0 and yes_radio.is_visible():
                            yes_radio.click()
                            print("[AUTO-APPLY] Auto-selected 'Yes' for radio group.")
                        else:
                            first_radio = group.locator("input[type='radio']").first
                            if first_radio.count() > 0 and first_radio.is_visible():
                                first_radio.click()
                                print("[AUTO-APPLY] Auto-selected first option for radio group.")
            except Exception as e:
                print(f"[AUTO-APPLY] Radio buttons auto-fill warning: {e}")

            # Smart Auto-fill for Select Dropdowns
            try:
                selects = page.locator("select")
                for s_idx in range(selects.count()):
                    sel = selects.nth(s_idx)
                    if sel.is_visible() and not sel.input_value():
                        options = sel.locator("option")
                        for o_idx in range(1, options.count()):
                            val = options.nth(o_idx).get_attribute("value")
                            if val:
                                sel.select_option(val)
                                print(f"[AUTO-APPLY] Selected option '{val}' for dropdown.")
                                break
            except Exception as e:
                print(f"[AUTO-APPLY] Select dropdowns auto-fill warning: {e}")

            # Smart Auto-fill for Text/Textarea Questions
            try:
                text_inputs = page.locator("input[type='text'], textarea")
                for t_idx in range(text_inputs.count()):
                    inp = text_inputs.nth(t_idx)
                    if inp.is_visible() and not inp.input_value():
                        id_attr = inp.get_attribute("id") or ""
                        label_text = ""
                        if id_attr:
                            label_el = page.locator(f"label[for='{id_attr}']").first
                            if label_el.count() > 0:
                                label_text = label_el.inner_text().lower()
                        
                        parent_fieldset = inp.locator("xpath=ancestor::fieldset").first
                        if parent_fieldset.count() > 0:
                            legend = parent_fieldset.locator("legend").first
                            if legend.count() > 0:
                                label_text += " " + legend.inner_text().lower()

                        if any(x in label_text for x in ["experience", "years", "how many"]):
                            inp.fill("1")
                            print("[AUTO-APPLY] Filled experience question with '1'.")
                        else:
                            inp.fill("1")
                            print("[AUTO-APPLY] Filled empty field with '1'.")
            except Exception as e:
                print(f"[AUTO-APPLY] Text fields auto-fill warning: {e}")

            page.wait_for_timeout(1500)

            # Look for the primary action button
            action_btn = page.locator("footer button.artdeco-button--primary, .jobs-easy-apply-modal__footer-container button.artdeco-button--primary, button.artdeco-button--primary").first
            
            if action_btn.count() == 0 or not action_btn.is_visible():
                # Check if we are on the Success/Done screen
                done_btn = page.locator("button:has-text('Done'), button:has-text('Dismiss'), .artdeco-modal__dismiss").first
                if done_btn.count() > 0 and done_btn.is_visible():
                    print("[AUTO-APPLY] Application completed successfully!")
                    done_btn.click()
                    status = "Applied"
                    break
                else:
                    print("[AUTO-APPLY] No action button found. Breaking...")
                    status = "Manual Action Required"
                    break

            # Check if button is enabled
            is_disabled = action_btn.get_attribute("aria-disabled") == "true" or not action_btn.is_enabled()
            if is_disabled:
                print("[AUTO-APPLY] Required fields need your input. Please fill them in the browser window...")
                # Wait for user to fill and button to become enabled (up to 20 seconds)
                button_enabled = False
                for _ in range(10):
                    page.wait_for_timeout(2000)
                    is_disabled = action_btn.get_attribute("aria-disabled") == "true" or not action_btn.is_enabled()
                    if not is_disabled:
                        button_enabled = True
                        break
                if not button_enabled:
                    print("[AUTO-APPLY] Form is still incomplete. Leaving browser open for manual finish.")
                    # Keep browser open for 60 seconds so user can finish manually
                    for _ in range(12):
                        page.wait_for_timeout(5000)
                        post_submit = page.locator("button:has-text('Done'), h3:has-text('Success'), h3:has-text('Applied')").first
                        if post_submit.count() > 0 and post_submit.is_visible():
                            print("[AUTO-APPLY] Detected successful manual submission!")
                            status = "Applied"
                            break
                    else:
                        status = "Manual Action Required"
                    break

            # If button is enabled, click it
            btn_text = action_btn.inner_text().strip().lower()
            print(f"[AUTO-APPLY] Clicking action button: '{action_btn.inner_text().strip()}'")
            
            if "submit" in btn_text:
                action_btn.click()
                page.wait_for_timeout(5000)
                # Check for success message or Done button
                post_submit = page.locator("button:has-text('Done'), button:has-text('Dismiss'), h3:has-text('Success'), h3:has-text('Applied')").first
                if post_submit.count() > 0:
                    status = "Applied"
                else:
                    status = "Applied"
                break
            else:
                action_btn.click()
                steps_completed += 1
                page.wait_for_timeout(2500)

        browser.close()
    return status

def update_job_status_in_files(job_url, new_status):
    """
    Updates the 'Application Status' column for the matching job URL in all CSV and JSON files.
    """
    normalized_target_url = job_url.split("?")[0].rstrip("/")
    dir_path = os.path.dirname(os.path.abspath(__file__))
    
    # Gather all potential target files
    targets = []
    try:
        for file in os.listdir(dir_path):
            if file.startswith("linkedin_") and (file.endswith(".csv") or file.endswith(".json")):
                targets.append(os.path.join(dir_path, file))
    except Exception as e:
        print(f"[STATUS UPDATE] Directory scan warning: {e}")

    for target in targets:
        if not os.path.exists(target):
            continue
            
        try:
            if target.endswith(".json"):
                with open(target, "r", encoding="utf-8") as f:
                    jobs = json.load(f)
                
                updated = False
                for job in jobs:
                    url = job.get("Job Posting Link / URL", "") or job.get("Job URL", "") or job.get("Job Posting Link", "")
                    if url:
                        clean_url = url.split("?")[0].rstrip("/")
                        if clean_url == normalized_target_url:
                            job["Application Status"] = new_status
                            updated = True
                
                if updated:
                    with open(target, "w", encoding="utf-8") as f:
                        json.dump(jobs, f, indent=4, ensure_ascii=False)
                    print(f"[STATUS UPDATE] JSON file '{os.path.basename(target)}' updated with status '{new_status}'")
            
            elif target.endswith(".csv"):
                rows = []
                headers = []
                with open(target, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames
                    if not headers:
                        continue
                    if "Application Status" not in headers:
                        headers = list(headers) + ["Application Status"]
                    rows = list(reader)
                    
                updated = False
                for row in rows:
                    url = row.get("Job Posting Link / URL", "") or row.get("Job URL", "") or row.get("Job Posting Link", "")
                    if url:
                        clean_url = url.split("?")[0].rstrip("/")
                        if clean_url == normalized_target_url:
                            row["Application Status"] = new_status
                            updated = True
                        
                if updated:
                    with open(target, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        for row in rows:
                            writer.writerow(row)
                    print(f"[STATUS UPDATE] CSV file '{os.path.basename(target)}' updated with status '{new_status}'")
        except Exception as e:
            print(f"[STATUS UPDATE] Error updating file {target}: {e}")
