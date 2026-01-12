import streamlit as st
import pandas as pd
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---
DESIGN_FILE = "final_evaluation_design_18_users.csv"
# Updated to your provided link
SPREADSHEET_ID = "1rCXFFLteUrvT-O-I8IowFx_Eg8IYlVaFeUOdVLfJiNU" 
SHEET_NAME = "Sheet1"

# Load Credentials and Password from Streamlit Secrets
# (Set these up in the Streamlit Cloud Dashboard under Settings > Secrets)
try:
    creds_info = st.secrets["gcp_service_account"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception as e:
    st.error("Secrets not configured correctly. Please check Streamlit Cloud settings.")
    st.stop()

# Initialize Google Sheets Service
@st.cache_resource
def get_sheets_service():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    return build("sheets", "v4", credentials=creds)

def append_to_sheet(rows):
    """Appends trial data to the Google Sheet."""
    service = get_sheets_service()
    body = {"values": rows}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:J",
        valueInputOption="RAW",
        body=body
    ).execute()

def get_existing_user_ids():
    """Fetch user IDs from the first column of the sheet to prevent double-testing."""
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:A"
        ).execute()
        values = result.get('values', [])
        return [row[0] for row in values if row]
    except:
        return []

# --- UI SETTINGS & CSS ---
st.set_page_config(page_title="TTS Evaluation Portal", layout="wide")

st.markdown("""
    <style>
    .instruction-box { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 20px; color: black; }
    .score-table { width: 100%; border-collapse: collapse; font-size: 14px; color: black; }
    .score-table th, .score-table td { border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }
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
            <tr><td><b>3 - Fair</b></td><td>Noticeably synthetic; understandable; mild artifacts.</td><td>Synthetic but clear ➔ <b>3</b></td></tr>
            <tr><td><b>2 - Poor</b></td><td>Strongly synthetic; distracting artifacts; requires effort.</td><td>Hard to listen to ➔ <b>2</b></td></tr>
            <tr><td><b>1 - Bad</b></td><td>Unusable; broken/glitchy; truncated or corrupted audio.</td><td>Broken/Unintelligible ➔ <b>1</b></td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'user_ID' not in st.session_state:
    st.session_state.user_ID = None
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'user_data' not in st.session_state:
    st.session_state.user_data = None

# --- ADMIN SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Admin Panel")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.success("Access Granted")
        st.write(f"📊 [View Results Sheet](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID})")
        if st.button("Refresh Cache"):
            st.cache_resource.clear()

# --- MAIN APP FLOW ---
show_instructions()

if st.session_state.user_ID is None:
    st.title("TTS Simultaneous ACR Evaluation")
    uid_input = st.text_input("Please enter your User ID:").strip()
    
    if st.button("Login"):
        # Basic check to see if user exists in design and hasn't finished
        df = pd.read_csv(DESIGN_FILE)
        user_subset = df[df['user'] == uid_input].copy()
        
        if user_subset.empty:
            st.error(f"User ID '{uid_input}' not found in the evaluation design.")
        else:
            st.session_state.user_ID = uid_input
            st.session_state.user_data = user_subset.reset_index(drop=True)
            st.rerun()

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
                # Prepare row for Google Sheets (Matching your CSV columns)
                # user, model_1, model_2, sample_ID, trial_Index, text, audio_1, audio_2, score_1, score_2
                sheet_row = [
                    st.session_state.user_ID, row['model_1'], row['model_2'], 
                    row['sample_ID'], int(row['trial_Index']), row['text'], 
                    row['audio_1'], row['audio_2'], score_a + 1, score_b + 1
                ]
                append_to_sheet([sheet_row])
                
                st.session_state.current_idx += 1
                st.rerun()
            else:
                st.error("Please rate both samples before moving to the next trial.")
    else:
        st.success("Test complete! Your ratings have been submitted to Google Sheets.")
        st.balloons()
        if st.button("Log Out / Finish"):
            st.session_state.clear()
            st.rerun()
