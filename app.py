import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from io import BytesIO

# Page config
st.set_page_config(page_title="Football Stats Manager", layout="wide")
st.title("CALCIATORI DI READING")
#st.subheader("L'importante é esserci")

# File upload
uploaded_file = "CALCIATORI_RDG.xlsx"

if uploaded_file:
    # Load sheets
    players_df = pd.read_excel(uploaded_file, sheet_name="Players", engine="openpyxl")
    matches_df = pd.read_excel(uploaded_file, sheet_name="Matches", engine="openpyxl")
    lineups_df = pd.read_excel(uploaded_file, sheet_name="Team Lineups", engine="openpyxl")

    # Filter players with at least 1 match
    st.subheader("Leaderboard")
    filtered_players_df = players_df[players_df["Match Played"] > 0]
    columns_to_display = ["Player Name", "Match Played", "Games Won", "Games Drew", "Games Lost", "Goal Difference", "Goal Scored", "MVP"]
    filtered_players_df = filtered_players_df[columns_to_display]

    # Highlight first three rows (entire row)
    def apply_highlight(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        if len(df) > 0:
            styles.iloc[0, :] = 'background-color: yellow'
        if len(df) > 1:
            styles.iloc[1, :] = 'background-color: lightgrey'
        if len(df) > 2:
            styles.iloc[2, :] = 'background-color: saddlebrown; color: white'
        return styles

    styled_df = filtered_players_df.style.apply(lambda _: apply_highlight(filtered_players_df), axis=None)

    
    
    # Render searchable and sortable table using AgGrid
    gb = GridOptionsBuilder.from_dataframe(filtered_players_df)
    gb.configure_default_column(editable=False, sortable=True, filter=True)
    gb.configure_pagination(enabled=True)
    gb.configure_grid_options(domLayout='normal')  # Normal layout for scroll
    gb.configure_grid_options(suppressHorizontalScroll=False)  # Allow horizontal scroll

    gridOptions = gb.build()

    AgGrid(
        filtered_players_df,
        gridOptions=gridOptions,
        enable_enterprise_modules=False,
        height=400,  # Fixed height for vertical scroll
        fit_columns_on_grid_load=False  # Prevent shrinking columns
    )



   
