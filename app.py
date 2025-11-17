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
    # Configure AgGrid
    gb = GridOptionsBuilder.from_dataframe(filtered_players_df)
    gb.configure_default_column(editable=False, sortable=True, filter=True)
    gb.configure_pagination(enabled=True)

    # Force scrollable layout
    gb.configure_grid_options(domLayout='normal')  # Allows scrolling
    gb.configure_grid_options(suppressHorizontalScroll=False)
    
    # Set minimum column width so they don't shrink
    for col in filtered_players_df.columns:
        gb.configure_column(col, minWidth=120)  # Adjust as needed

    
    # Set minimum column width and alignment
    for i, col in enumerate(filtered_players_df.columns):
        if i == 0:
            # First column: left-aligned
            gb.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
        else:
            # Other columns: center-aligned
            gb.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})


    # Add row styling for top 3 rows
    def row_style(params):
        if params['node']['rowIndex'] == 0:
            return {'backgroundColor': 'gold', 'color': 'black', 'fontWeight': 'bold'}
        elif params['node']['rowIndex'] == 1:
            return {'backgroundColor': 'silver', 'color': 'black', 'fontWeight': 'bold'}
        elif params['node']['rowIndex'] == 2:
            return {'backgroundColor': '#cd7f32', 'color': 'white', 'fontWeight': 'bold'}  # Bronze
        return {}
    
    gb.configure_grid_options(getRowStyle=row_style)


    
    gridOptions = gb.build()
    
    # Disable auto-sizing completely
    gridOptions['suppressAutoSize'] = True
    gridOptions['suppressSizeToFit'] = True
    
    # Render AgGrid with fixed height
    AgGrid(
        filtered_players_df,
        gridOptions=gridOptions,
        enable_enterprise_modules=False,
        height=400,  # Fixed height for vertical scroll
        fit_columns_on_grid_load=False  # Prevent auto-fit
    )
