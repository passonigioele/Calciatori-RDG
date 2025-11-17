import streamlit as st
import pandas as pd
from io import BytesIO

# Page config
st.set_page_config(page_title="Football Stats Manager", layout="wide")
st.title("⚽ Football Stats Manager")

# File upload
uploaded_file = "CALCIATORI_RDG.xlsx"

if uploaded_file:
    # Load sheets
    players_df = pd.read_excel(uploaded_file, sheet_name="Players", engine="openpyxl")
    matches_df = pd.read_excel(uploaded_file, sheet_name="Matches", engine="openpyxl")
    lineups_df = pd.read_excel(uploaded_file, sheet_name="Team Lineups", engine="openpyxl")

    # Filter players with at least 1 match
    st.subheader("Overall Leaderboard")
    filtered_players_df = players_df[players_df["Match Played"] > 0]
    filtered_players_df = players_df["Match Played"]

    # Highlight first three cells in the first column
    def apply_highlight(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        if len(df) > 0:
            styles.iloc[0, ] = 'background-color: yellow'
        if len(df) > 1:
            styles.iloc[1, ] = 'background-color: lightgrey'
        if len(df) > 2:
            styles.iloc[2, ] = 'background-color: saddlebrown; color: white'
        return styles

    styled_df = filtered_players_df.style.apply(lambda _: apply_highlight(filtered_players_df), axis=None)

    # Render styled table as HTML (read-only)
    st.write(styled_df.to_html(), unsafe_allow_html=True)

    
