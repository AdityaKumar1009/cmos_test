import streamlit as st
import pandas as pd
import os
from io import BytesIO

# --- CONFIGURATION ---
# In deployment, Streamlit Cloud will use st.secrets. 
# On local, it looks for .streamlit/secrets.toml
DESIGN_FILE = "final_evaluation_design_18_users.csv"
RESULTS_DIR = "results"

# Retrieve password from Environment Secrets
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    ADMIN_PASSWORD = "ak2024"  # Local fallback for development

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

st.set_page_config(page_title="TTS Evaluation Portal", layout="wide")

# --- CUSTOM CSS FOR STICKY INSTRUCTIONS ---
st.markdown("""
    <style>
    .instruction-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
        font-family: sans-serif;
        color: black;
    }
    .score-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        color: black;
    }
    .score-table th, .score-table td {
        border-bottom: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    </style>
    """, unsafe_allow_html=True)

def show_instructions():
    st.markdown("""
    <div class="instruction-box">
        <h3 style='margin-top:0;'>Rating Guidelines</h3>
        <table class="score-table">
            <tr><th>Score</th><th>Definition (Overall Quality)</th><th>Quick Reference</th></tr>
            <tr><td><b>5 - Excellent</b></td><td>Near-human; smooth; clear pronunciation; stable prosody.</td><td>Near-human, clean ➔ <b>5</b></td></tr>
            <tr><td><b>4 - Good</b></td><td>Mostly natural; minor issues (robotic tone, slightly odd pause).</td><td>Natural with tiny quirks ➔ <b>4</b></td></tr>
            <tr><td><b>3 - Fair</b></td><td>Noticeably synthetic; occasional mispronunciation; understandable.</td><td>Synthetic but clear ➔ <b>3</b></td></tr>
            <tr><td><b>2 - Poor</b></td><td>Strongly synthetic; distracting artifacts; requires effort.</td><td>Hard to listen to ➔ <b>2</b></td></tr>
            <tr><td><b>1 - Bad</b></td><td>Unusable; broken/glitchy; truncated or corrupted audio.</td><td>Broken/Unintelligible ➔ <b>1</b></td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

# --- SESSION STATE MANAGEMENT ---
if 'user_ID' not in st.session_state:
    st.session_state.user_ID = None
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'user_data' not in st.session_state:
    st.session_state.user_data = None

# --- ADMIN SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Admin Panel")
    admin_input = st.text_input("Admin Password", type="password")
    
    if admin_input == ADMIN_PASSWORD:
        st.success("Access Granted")
        res_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.csv')]
        
        if res_files:
            st.subheader("Data Management")
            selected_res = st.selectbox("View User Data", res_files)
            view_df = pd.read_csv(os.path.join(RESULTS_DIR, selected_res))
            st.dataframe(view_df)
            
            # Master Download
            if st.button("Export Master CSV"):
                all_dfs = [pd.read_csv(os.path.join(RESULTS_DIR, f)) for f in res_files]
                master_df = pd.concat(all_dfs, ignore_index=True)
                csv_data = master_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download All Results", csv_data, "master_results.csv", "text/csv")
        else:
            st.info("No results recorded yet.")

# --- MAIN APP UI ---
show_instructions()

if st.session_state.user_ID is None:
    st.title("TTS Simultaneous ACR Evaluation")
    uid_input = st.text_input("Please enter your User ID:").strip()
    
    if st.button("Login"):
        try:
            df = pd.read_csv(DESIGN_FILE)
            user_subset = df[df['user'] == uid_input].copy()
            
            if user_subset.empty:
                st.error(f"User ID '{uid_input}' not found in the evaluation design.")
            elif os.path.exists(os.path.join(RESULTS_DIR, f"results_{uid_input}.csv")):
                st.warning("This session has already been completed.")
            else:
                st.session_state.user_ID = uid_input
                st.session_state.user_data = user_subset.reset_index(drop=True)
                st.rerun()
        except FileNotFoundError:
            st.error("Design file not found. Please upload 'final_evaluation_design_18_users.csv' to the server.")

else:
    data = st.session_state.user_data
    idx = st.session_state.current_idx

    if idx < len(data):
        row = data.iloc[idx]
        st.subheader(f"User: {st.session_state.user_ID} | Trial {idx + 1} of {len(data)}")
        st.markdown(f"**Text:** `{row['text']}`")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Sample A")
            st.audio(row['audio_1'])
            score_a = st.feedback("stars", key=f"a_{idx}")
        
        with col2:
            st.markdown("### Sample B")
            st.audio(row['audio_2'])
            score_b = st.feedback("stars", key=f"b_{idx}")

        if st.button("Submit Trial"):
            if score_a is not None and score_b is not None:
                # Store scores (st.feedback is 0-indexed 0-4, we convert to 1-5)
                st.session_state.user_data.at[idx, 'score_1'] = score_a + 1
                st.session_state.user_data.at[idx, 'score_2'] = score_b + 1
                st.session_state.current_idx += 1
                st.rerun()
            else:
                st.error("Please rate both samples before moving to the next trial.")
    else:
        # Save results
        final_path = os.path.join(RESULTS_DIR, f"results_{st.session_state.user_ID}.csv")
        st.session_state.user_data.to_csv(final_path, index=False)
        st.success("Test complete! Your ratings have been submitted.")
        st.balloons()
        if st.button("Log Out / New User"):
            st.session_state.clear()
            st.rerun()
