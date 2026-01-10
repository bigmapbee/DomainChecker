import streamlit as st
import subprocess
import requests
import pandas as pd
import shutil
import socket
import concurrent.futures

# --- CONFIGURATION ---
st.set_page_config(page_title="Fast Domain Checker", page_icon="⚡")

# --- FUNCTIONS ---
def check_domain_system(domain):
    """
    Checks a single domain. Designed to be thread-safe.
    1. Tries System WHOIS (accurate).
    2. If WHOIS hangs (timeout), falls back to DNS lookup (fast).
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
    # We look for these specific "not found" patterns
    not_found_patterns = [
        "No match for", "NOT FOUND", "Not Registered", 
        "No Data Found", "Status: free", "No entries found"
    ]
    
    is_registered = False 
    
    try:
        # STRICT TIMEOUT: 3 seconds max per domain
        proc = subprocess.run(
            ["whois", domain], 
            capture_output=True, 
            text=True, 
            timeout=3 
        )
        output = proc.stdout + proc.stderr
        
        is_registered = True # Assume registered
        
        for pattern in not_found_patterns:
            if pattern.lower() in output.lower():
                is_registered = False
                break
                
        if is_registered:
            result["Registration"] = "REGISTERED"
        else:
            result["Registration"] = "UNREGISTERED"

    except subprocess.TimeoutExpired:
        # --- FALLBACK: DNS CHECK ---
        try:
            socket.gethostbyname(domain)
            is_registered = True
            result["Registration"] = "REGISTERED (DNS Found)"
        except socket.gaierror:
            is_registered = False
            result["Registration"] = "TIMEOUT / UNKNOWN"
            
    except FileNotFoundError:
        return None

    # 2. Check HTTP (Web Status) - Only if registered
    if is_registered:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; DomainChecker/1.0)'}
            url = f"http://{domain}"
            
            # Very short timeout (2s) to keep threads moving fast
            response = requests.head(url, headers=headers, timeout=2, allow_redirects=True)
            
            if 200 <= response.status_code < 400:
                result["Web Status"] = f"ACTIVE ({response.status_code})"
            elif response.status_code >= 400:
                result["Web Status"] = f"ERROR ({response.status_code})"
        except requests.RequestException:
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
st.title("⚡ Multi-Threaded Domain Checker")
st.write("Checks domains in parallel for maximum speed.")

if not shutil.which("whois"):
    st.error("⚠️ CRITICAL ERROR: 'whois' command not found.")
    st.stop()

# Input
input_method = st.radio("Choose input:", ["Paste Text", "Upload File"], horizontal=True)
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

clean_list = [d.strip() for d in domains_to_check if d.strip()]

if clean_list:
    st.info(f"Loaded {len(clean_list)} domains.")

    # --- SPEED CONTROLS ---
    st.markdown("### 🚀 Speed Settings")
    col1, col2 = st.columns(2)
    with col1:
        # 10 is a safe default. 50 is very fast but risky.
        max_workers = st.slider("Concurrent Threads (Speed)", min_value=1, max_value=50, value=10)
    with col2:
        st.caption("Higher threads = Faster processing but higher risk of WHOIS servers blocking your IP.")

    if st.button("Start Fast Check"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        table_placeholder = st.empty()
        
        total = len(clean_list)
        completed_count = 0

        # Styling
        def color_registration(val):
            if 'REGISTERED' in val: return 'color: #28a745; font-weight: bold'
            elif 'UNREGISTERED' in val: return 'color: #dc3545; font-weight: bold'
            else: return 'color: #ffc107; font-weight: bold'

        # --- PARALLEL EXECUTION ---
        # We use ThreadPoolExecutor to run multiple checks at once
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_domain = {executor.submit(check_domain_system, domain): domain for domain in clean_list}
            
            # Process as they finish
            for future in concurrent.futures.as_completed(future_to_domain):
                data = future.result()
                if data:
                    results.append(data)
                
                completed_count += 1
                progress_bar.progress(completed_count / total)
                status_text.text(f"Processed: {completed_count}/{total}")

                # Update table every 5 items (to save UI resources) or at the end
                if completed_count % 5 == 0 or completed_count == total:
                    df = pd.DataFrame(results)
                    if not df.empty:
                        styled_df = df.style.map(color_registration, subset=['Registration'])
                        table_placeholder.dataframe(styled_df, use_container_width=True)

        status_text.text("✅ All Checks Complete!")
        
        if results:
            df_final = pd.DataFrame(results)
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "domain_results.csv", "text/csv")
