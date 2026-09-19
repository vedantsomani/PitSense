import streamlit as st
from src.live_ui import render_live_page

st.set_page_config(page_title="Live Race Centre", page_icon="🏎️", layout="wide")
render_live_page()
