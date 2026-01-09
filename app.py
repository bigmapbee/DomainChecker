import streamlit as st
import subprocess
import requests
import time
import pandas as pd
import shutil

# --- CONFIGURATION ---
st.set_page_config(page_title="Domain Checker", page_icon="🌐")

# --- FUNCTIONS ---
def check_domain_system(domain):
    """
    Uses the system 'whois' command exactly like the Bash script.
    """
    domain = domain.strip()
    if not domain:
        return None

    result = {
        "Domain": domain,
        "Registration": "Unknown",
        "Web Status": "N/A",
    }

    # 1. Run System WHOIS (Exact same logic as your Bash script)
    # We look for these specific "not found" phrases
    not_found_patterns = [
        "No match for", "NOT FOUND", "Not Registered", 
        "No Data Found", "Status: free", "No entries found"
    ]
    
    is_registered = True
    
    try:
        # Run the actual terminal command
        # check=False ensures it doesn't crash Python if whois returns an error code
        proc = subprocess.run(["whois", domain], capture_output=True, text=True)
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
            
    except FileNotFoundError:
        st.error("Error: 'whois' command not found. Are you on Mac/Linux?")
        return None

    # 2. Check HTTP (Web Status) - Only if registered
    if is_registered:
        try:
            # We use a proper User-Agent so servers don't block the script
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; DomainChecker/1.0)'}
            url = f"http://{domain}"
            
            # This is the Python equivalent of 'curl -I -L'
            response = requests.head(url, headers=headers, timeout=2, allow_redirects=True)
            
            if 200 <= response.status_code < 400:
                result["Web Status"] = f"ACTIVE ({response.status_code})"
            elif response.status_code >= 400:
                result["Web Status"] = f"ERROR ({response.status_code})"
        except requests.RequestException:
             # If HEAD fails, try GET once just in case (some servers block HEAD)
            try:
                response = requests.get(url, headers=headers, timeout=2)
                if 200 <= response.status_code < 400:
                    result["Web Status"] = f"ACTIVE ({response.status_code})"
                else:
                    result["Web Status"] = f"ERROR ({response.status_code})"
            except:
                result["Web Status"] = "OFFLINE"
    
    return result

# --- APP UI ---
st.title("🌐 Bulk Domain Checker By Bill")
st.write("Using system `whois` for maximum accuracy.")

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

# Run Button
if st.button("Check Domains") and domains_to_check:
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    table_placeholder = st.empty()
    
    clean_list = [d.strip() for d in domains_to_check if d.strip()]
    total = len(clean_list)

    for i, domain in enumerate(clean_list):
        status_text.text(f"Checking: {domain}...")
        
        data = check_domain_system(domain)
        if data:
            results.append(data)
        
        progress_bar.progress((i + 1) / total)
        
        # Real-time Table Update
        df = pd.DataFrame(results)
        
        def color_registration(val):
            color = 'green' if val == 'REGISTERED' else 'red'
            return f'color: {color}; font-weight: bold'

        if not df.empty:
            styled_df = df.style.map(color_registration, subset=['Registration'])
            table_placeholder.dataframe(styled_df, use_container_width=True)
        
        time.sleep(0.5)

    status_text.text("✅ Check Complete!")
    
    if results:
        df_final = pd.DataFrame(results)
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "domain_results.csv", "text/csv")
