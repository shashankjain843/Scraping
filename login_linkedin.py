import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

COOKIE_FILE = "www.linkedin.com_cookies.json"

def main():
    print("============================================================")
    print("LINKEDIN LOGIN ASSISTANT FOR SCRAPER (AUTO-DETECT ENABLED)")
    print("============================================================")
    print("1. Ek browser window open hogi. Please LinkedIn login karein.")
    print("2. Login hone ke baad script AUTOMATICALLY detect karke cookies")
    print("   save kar degi aur browser close kar degi.")
    print("============================================================")

    with sync_playwright() as p:
        # Launch browser in headful mode
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Navigating to LinkedIn login page...")
        page.goto("https://www.linkedin.com/login")
        
        print("\nPlease log in now. Monitoring session status...")
        
        logged_in = False
        try:
            while True:
                # If page is closed by user before login, break
                if page.is_closed():
                    break
                
                # Check for UI elements visible ONLY when logged in
                is_logged_in_ui = False
                try:
                    # check for the main global navigation bar or the feed profile identity module
                    if page.locator(".global-nav").is_visible(timeout=500) or page.locator(".feed-identity-module").is_visible(timeout=500):
                        is_logged_in_ui = True
                except:
                    pass
                
                # Check current URL to detect successful login redirect
                current_url = page.url.lower()
                if "feed" in current_url or "mynetwork" in current_url or "messaging" in current_url or "me" in current_url or is_logged_in_ui:
                    print("\n[SUCCESS] Login detected! Capturing active session cookies...")
                    time.sleep(2)  # Wait for cookies to settle
                    cookies = context.cookies()
                    
                    # Save cookies to JSON
                    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, indent=4)
                    print(f"[SUCCESS] Cookies successfully saved to {COOKIE_FILE}!")
                    
                    logged_in = True
                    # Pause 3 seconds so user sees redirect, then close browser
                    time.sleep(3)
                    browser.close()
                    break
                    
                time.sleep(1)
        except Exception as e:
            if not logged_in:
                print(f"[ERROR] Failed to save session cookies: {e}")
            try:
                browser.close()
            except:
                pass

if __name__ == "__main__":
    main()
