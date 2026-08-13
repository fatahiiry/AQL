import pandas as pd
import streamlit as st

def clean_val(row, col_name, default=""):
    if row is not None:
        row_lowercase = {str(k).lower(): v for k, v in row.to_dict().items()}
        target_key = col_name.lower()
        if target_key in row_lowercase and pd.notna(row_lowercase[target_key]):
            return str(row_lowercase[target_key]).strip()
    return default

# --- Callbacks Tactiles pour les Compteurs ---
def inc_majeur():
    st.session_state["widget_maj"] = st.session_state.get("widget_maj", 0) + 1

def dec_majeur():
    if st.session_state.get("widget_maj", 0) > 0:
        st.session_state["widget_maj"] -= 1

def inc_mineur():
    st.session_state["widget_min"] = st.session_state.get("widget_min", 0) + 1

def dec_mineur():
    if st.session_state.get("widget_min", 0) > 0:
        st.session_state["widget_min"] -= 1

def inc_secu():
    st.session_state.widget_sec = st.session_state.get("widget_sec", 0) + 1

def dec_secu():
    if st.session_state.get("widget_sec", 0) > 0:
        st.session_state.widget_sec -= 1

def reset_compteurs():
    keys_to_reset = [
        "widget_maj",
        "widget_min",
        "widget_sec",
        "widget_total_defauts",
        "nc1_area",
        "nc2_area",
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    if "sauvegarde_mesures" in st.session_state:
        st.session_state["sauvegarde_mesures"] = {}