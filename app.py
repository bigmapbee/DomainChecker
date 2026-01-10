import streamlit as st
import subprocess
import requests
import time
import pandas as pd
import shutil
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="Domain Checker", page_icon="🌐")

# --- FUNCTIONS ---
def check_domain_system(domain):
    """
    Uses the system 'whois' command with a timeout to prevent hanging.
    """
    domain = domain.strip()
    if not domain:
        return None

    result = {
        "Domain": domain,
        "Registration": "Unknown",
        "Web Status": "N/A",
    }

    # 1. Run System WHOIS
    # We look for these specific "not found" phrases
    not_found_patterns = [
        "No match for", "NOT FOUND", "Not Registered", 
        "No Data Found", "Status: free", "No entries found"
    ]
    
    is_registered = True
    
    try:
        # --- FIX: Timeout added (5 seconds) ---
        # This prevents the app from freezing if the WHOIS server ignores us
        proc = subprocess.run(
            ["whois", domain], 
            capture_output=True, 
            text=True, 
            timeout=5 
        )
        output = proc.stdout + proc.stderr
        
        # Check if any "not found" pattern is in the output
        for pattern in not_found_patterns:
            if pattern.lower() in output.lower():
                is_registered = False
                break
                
        if is_registered:
            result["Registration"] = "REGISTERED"
        else:
            result["Registration"] = "UNREGISTERED"
            
    except subprocess.TimeoutExpired:
        # If the server "tarpits" (ignores) us, we mark it and move on
        result["Registration"] = "TIMEOUT"
        result["Web Status"] = "SKIPPED"
        return result

    except FileNotFoundError:
        st.error("Error: 'whois' command not found. Are you on Mac/Linux?")
        return None

    # 2. Check HTTP (Web Status) - Only if registered
    if is_registered:
        try:
            # Proper User-Agent to look like a browser
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; DomainChecker/1.0)'}
            url = f"http://{domain}"
            
            # Use HEAD first for speed
            response = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
            
            if 200 <= response.status_code < 400:
                result["Web Status"] = f"ACTIVE ({response.status_code})"
            elif response.status_code >= 400:
                result["Web Status"] = f"ERROR ({response.status_code})"
        except requests.RequestException:
            # Fallback to GET if HEAD fails
            try:
                response = requests.get(url, headers=headers, timeout=3)
                if 200 <= response.status_code < 400:
                    result["Web Status"] = f"ACTIVE ({response.status_code})"
                else:
                    result["Web Status"] = f"ERROR ({response.status_code})"
            except:
                result["Web Status"] = "OFFLINE"
    
    return result

# --- APP UI ---
st.title("🌐 Bulk Domain Checker By Bill")
st.write("Using system `whois` with random delays and timeout protection.")

# Check if whois is installed
if not shutil.which("whois"):
    st.error("⚠️ CRITICAL ERROR: The 'whois' command was not found on this system.")
    st.stop()

# Input method
input_method = st.radio("Choose input:", ["Paste Text", "Upload File"])

domains_to_check = []

if input_method == "Paste Text":
    text_input = st.text_area("Paste domains (one per line):", height=150)
    if text_input:
        domains_to_check = text_input.split('\n')

elif input_method == "Upload File":
    uploaded_file = st.file_uploader("Upload .txt file", type="txt")
    if uploaded_file:
        string_data = uploaded_file.getvalue().decode("utf-8")
        domains_to_check = string_data.split('\n')

# Clean the list
clean_list = [d.strip() for d in domains_to_check if d.strip()]

if clean_list:
    st.info(f"Loaded {len(clean_list)} domains ready for checking.")

# Run Button
if st.button("Start Checking"):
    
    # Note on Stopping
    st.caption("ℹ️ To stop the process early, click the **Stop** button in the top-right corner of the browser window.")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    table_placeholder = st.empty()
    
    total = len(clean_list)

    # DataFrame styling function
    def color_registration(val):
        if val == 'REGISTERED':
            return 'color: #28a745; font-weight: bold' # Green
        elif val == 'UNREGISTERED':
            return 'color: #dc3545; font-weight: bold' # Red
        elif val == 'TIMEOUT':
            return 'color: #ffc107; font-weight: bold' # Orange
        return ''

    for i, domain in enumerate(clean_list):
        status_text.text(f"Checking {i+1}/{total}: {domain}...")
        
        # 1. Check the domain
        data = check_domain_system(domain)
        if data:
            results.append(data)
        
        # 2. Update Progress
        progress_bar.progress((i + 1) / total)
        
        # 3. Batch Update Table (Every 3 items to keep UI fast)
        if (i + 1) % 3 == 0 or (i + 1) == total:
            df = pd.DataFrame(results)
            if not df.empty:
                styled_df = df.style.map(color_registration, subset=['Registration'])
                table_placeholder.dataframe(styled_df, use_container_width=True)
        
        # 4. Random Delay Strategy
        # We wait between 1.5 and 3.5 seconds to vary the pattern
        sleep_time = random.uniform(1.5, 3.5)
        time.sleep(sleep_time)

    status_text.text("✅ Check Complete!")
    
    # Final CSV Download
    if results:
        df_final = pd.DataFrame(results)
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "domain_results.csv", "text/csv")
