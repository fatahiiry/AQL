import streamlit as st

def apply_custom_styles():
    st.markdown(
        """
        <style>
            .main-header {
                background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
                padding: 1.5rem 2rem; border-radius: 12px;
                margin-bottom: 1.5rem; color: white; text-align: center;
            }
            .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
            .main-header p  { margin: 0.3rem 0 0; opacity: .85; font-size: .95rem; }
            .section-header {
                background: #f0f4f8; border-left: 4px solid #2d6a9f;
                padding: .6rem 1rem; border-radius: 0 8px 8px 0;
                margin: 1.2rem 0 .8rem; font-weight: 600; color: #1e3a5f; font-size: 1rem;
            }
            .calc-box {
                background: #e8f4fd; border: 1px solid #bee3f8;
                border-radius: 8px; padding: .8rem 1rem; margin: .4rem 0;
            }
            .calc-box .label { font-size: .8rem; color: #4a6fa5; font-weight: 600; margin-bottom: .2rem; }
            .calc-box .value { font-size: 1.3rem; font-weight: 700; color: #1e3a5f; }
            .calc-box .value.warning { color: #d97706; }
            .calc-box .value.danger  { color: #dc2626; }

            .stButton > button[key="save_btn"] {
                width: 100%;
                background: linear-gradient(135deg, #16a34a, #15803d);
                color: white; border: none; border-radius: 8px;
                padding: .8rem 1.5rem; font-size: 1.1rem; font-weight: 600;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )