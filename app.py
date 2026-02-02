import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from io import BytesIO
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="Calciatori di Reading", layout="wide")
st.title("CALCIATORI DI READING")
st.caption("Data collected since 13 November 2025")

# File upload
uploaded_file = "CALCIATORI_RDG.xlsx"

if uploaded_file:
    # Load sheets
    players_df = pd.read_excel(uploaded_file, sheet_name="Players", engine="openpyxl")
    matches_df = pd.read_excel(uploaded_file, sheet_name="Matches", engine="openpyxl")
    lineups_df = pd.read_excel(uploaded_file, sheet_name="Team Lineups", engine="openpyxl")



    # Latest match scoreboard with dynamic layout
    latest_match_id = lineups_df.sort_values(by="Date", ascending=False)["Match ID"].iloc[0]
    latest_match_df = lineups_df[lineups_df["Match ID"] == latest_match_id]
    
    # Extract scores
    team_a_score = latest_match_df[latest_match_df["Team (A/B)"] == "A"]["Team Score"].iloc[0]
    team_b_score = latest_match_df[latest_match_df["Team (A/B)"] == "B"]["Team Score"].iloc[0]
    
    # Team labels
    team_a_label = "Home"
    team_b_label = "Away"
    
    # Goal scorers
    team_a_scorers = latest_match_df[(latest_match_df["Team (A/B)"] == "A") & (latest_match_df["Goals Scored"] > 0)]
    team_b_scorers = latest_match_df[(latest_match_df["Team (A/B)"] == "B") & (latest_match_df["Goals Scored"] > 0)]
    
    # Dynamic figure height based on max scorers
    max_scorers = max(len(team_a_scorers), len(team_b_scorers))
    fig_height = 2 + (max_scorers*0.3)  # Add space per scorer
    
    fig, ax = plt.subplots(figsize=(6, fig_height))
    ax.axis('off')
    
    # Title
    match_date = latest_match_df['Date'].iloc[0].strftime("%d %B %Y")
    ax.set_title(f"{latest_match_id}° Giornata  ({match_date})", fontsize=12, fontweight='bold', ha='center')
    
    # Display teams and scores
    ax.text(0.25, 0.9, team_a_label, fontsize=12, ha='center')
    ax.text(0.75, 0.9, team_b_label, fontsize=12, ha='center')
    ax.text(0.25, 0.7, str(team_a_score), fontsize=24, ha='center', fontweight='bold', color='blue')
    ax.text(0.75, 0.7, str(team_b_score), fontsize=24, ha='center', fontweight='bold', color='red')
    
    # Separator
    ax.text(0.5, 0.7, "VS", fontsize=12, ha='center')
    
    # Dynamic spacing for scorers
    start_y = 0.65
    line_height = 0.08
    
    # Team A scorers
    if not team_a_scorers.empty:
        for i, (_, row) in enumerate(team_a_scorers.iterrows()):
            ax.text(0.25, start_y - (i+1) * line_height, f"{row['Player Name']} ({int(row['Goals Scored'])})", fontsize=10, ha='center')
    else:
        ax.text(0.25, start_y - line_height, "-", fontsize=10, ha='center')
    
    # Team B scorers
    if not team_b_scorers.empty:
        for i, (_, row) in enumerate(team_b_scorers.iterrows()):
            ax.text(0.75, start_y - (i+1) * line_height, f"{row['Player Name']} ({int(row['Goals Scored'])})", fontsize=10, ha='center')
    else:
        ax.text(0.75, start_y - line_height, "-", fontsize=10, ha='center')
    
    st.pyplot(fig)

   


    
    # Filter players with at least 1 match
    st.subheader("General Leaderboard")
    st.caption("Sorted by Games Won, Games Drew, Goal Difference, Goal Scored, and MVP. Only players with one or more game played since 13-11-2025 are visible")
    filtered_players_df = players_df[players_df["Match Played"] > 0]
    columns_to_display = ["Player Name", "Match Played", "Games Won", "Games Drew", "Games Lost", "Goal Difference", "Goal Scored", "Assists", "Goal/Game", "MVP", "Own Goals"]
    filtered_players_df = filtered_players_df[columns_to_display]
    columns_to_sort = ["Games Won", "Games Drew", "Goal Difference", "Goal Scored", "MVP"]
    filtered_players_df = filtered_players_df.sort_values(by=columns_to_sort, ascending=False)

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




# Top 5 players by Match Played
st.subheader("Veterani")
st.caption("Top 5 players by number of matches played")
top_players_df = filtered_players_df.sort_values(by="Match Played", ascending=False).head(5)
columns_to_display2 = ["Player Name", "Match Played"]
top_players_df = top_players_df[columns_to_display2]

# Render using AgGrid for consistency
gb_top = GridOptionsBuilder.from_dataframe(top_players_df)
gb_top.configure_default_column(editable=False, sortable=True, filter=False)
gb_top.configure_grid_options(domLayout='normal')
gb_top.configure_grid_options(suppressHorizontalScroll=False)

# Column alignment
for i, col in enumerate(top_players_df.columns):
    if i == 0:
        gb_top.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
    else:
        gb_top.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})

gridOptions_top = gb_top.build()
gridOptions_top['suppressAutoSize'] = True
gridOptions_top['suppressSizeToFit'] = True

AgGrid(
    top_players_df,
    gridOptions=gridOptions_top,
    enable_enterprise_modules=False,
    height=180,  # Smaller height for top 5
    fit_columns_on_grid_load=False
)


# Top 5 players by Goal Scored
st.subheader("Capocannonieri")
st.caption("Top 5 players by number of goals scored")
top_goals_df = filtered_players_df.sort_values(by="Goal Scored", ascending=False).head(5)
columns_to_display3 = ["Player Name", "Goal Scored"]
top_goals_df = top_goals_df[columns_to_display3]

# Render using AgGrid for consistency
gb_top = GridOptionsBuilder.from_dataframe(top_goals_df)
gb_top.configure_default_column(editable=False, sortable=True, filter=False)
gb_top.configure_grid_options(domLayout='normal')
gb_top.configure_grid_options(suppressHorizontalScroll=False)

# Column alignment
for i, col in enumerate(top_goals_df.columns):
    if i == 0:
        gb_top.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
    else:
        gb_top.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})

gridOptions_top = gb_top.build()
gridOptions_top['suppressAutoSize'] = True
gridOptions_top['suppressSizeToFit'] = True

AgGrid(
    top_goals_df,
    gridOptions=gridOptions_top,
    enable_enterprise_modules=False,
    height=180,  # Smaller height for top 5
    fit_columns_on_grid_load=False
)



# Top 5 players by Assist
st.subheader("Fantasisti")
st.caption("Top 5 players by number of assists")
top_assists_df = filtered_players_df.sort_values(by="Assists", ascending=False).head(5)
columns_to_display4 = ["Player Name", "Assists"]
top_assists_df = top_assists_df[columns_to_display4]

# Render using AgGrid for consistency
gb_top = GridOptionsBuilder.from_dataframe(top_assists_df)
gb_top.configure_default_column(editable=False, sortable=True, filter=False)
gb_top.configure_grid_options(domLayout='normal')
gb_top.configure_grid_options(suppressHorizontalScroll=False)

# Column alignment
for i, col in enumerate(top_assists_df.columns):
    if i == 0:
        gb_top.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
    else:
        gb_top.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})

gridOptions_top = gb_top.build()
gridOptions_top['suppressAutoSize'] = True
gridOptions_top['suppressSizeToFit'] = True

AgGrid(
    top_assists_df,
    gridOptions=gridOptions_top,
    enable_enterprise_modules=False,
    height=180,  # Smaller height for top 5
    fit_columns_on_grid_load=False
)





# Top 5 players by MVP
st.subheader("MVP")
st.caption("Top 5 players by number of MVP awards")
top_mvp_df = filtered_players_df.sort_values(by="MVP", ascending=False).head(5)
columns_to_display6 = ["Player Name", "MVP"]
top_mvp_df = top_mvp_df[columns_to_display6]

# Render using AgGrid for consistency
gb_top = GridOptionsBuilder.from_dataframe(top_mvp_df)
gb_top.configure_default_column(editable=False, sortable=True, filter=False)
gb_top.configure_grid_options(domLayout='normal')
gb_top.configure_grid_options(suppressHorizontalScroll=False)

# Column alignment
for i, col in enumerate(top_mvp_df.columns):
    if i == 0:
        gb_top.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
    else:
        gb_top.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})

gridOptions_top = gb_top.build()
gridOptions_top['suppressAutoSize'] = True
gridOptions_top['suppressSizeToFit'] = True

AgGrid(
    top_mvp_df,
    gridOptions=gridOptions_top,
    enable_enterprise_modules=False,
    height=180,  # Smaller height for top 5
    fit_columns_on_grid_load=False
)




# Top 5 players by own goals
st.subheader("Il Re dell'Autogol")
st.caption("Top 5 players by number of own goals")
top_og_df = filtered_players_df.sort_values(by="Own Goals", ascending=False).head(5)
columns_to_display7 = ["Player Name", "Own Goals"]
top_og_df = top_og_df[columns_to_display7]

# Render using AgGrid for consistency
gb_top = GridOptionsBuilder.from_dataframe(top_og_df)
gb_top.configure_default_column(editable=False, sortable=True, filter=False)
gb_top.configure_grid_options(domLayout='normal')
gb_top.configure_grid_options(suppressHorizontalScroll=False)

# Column alignment
for i, col in enumerate(top_og_df.columns):
    if i == 0:
        gb_top.configure_column(col, minWidth=150, cellStyle={'textAlign': 'left'})
    else:
        gb_top.configure_column(col, minWidth=120, cellStyle={'textAlign': 'center'})

gridOptions_top = gb_top.build()
gridOptions_top['suppressAutoSize'] = True
gridOptions_top['suppressSizeToFit'] = True

AgGrid(
    top_og_df,
    gridOptions=gridOptions_top,
    enable_enterprise_modules=False,
    height=180,  # Smaller height for top 5
    fit_columns_on_grid_load=False
)

