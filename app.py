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
    st.subheader("Players Leaderboard")
    filtered_players_df = players_df[players_df["Match Played"] > 0]

    # Display read-only table with formatting for leaderboard
    st.dataframe(
        filtered_players_df,
        use_container_width=True,
        column_config={
            "Goal/Game": st.column_config.NumberColumn(format="%.2f"),
            "% Win": st.column_config.NumberColumn(format="%.1f%%")
        }
    )

    # Download button
    if st.button("Download Updated Excel"):
        # Auto-calculation logic
        for idx, player in players_df.iterrows():
            name = player["Player Name"]
            player_lineups = lineups_df[lineups_df["Player Name"] == name]

            players_df.at[idx, "Match Played"] = len(player_lineups)
            players_df.at[idx, "Goal Scored"] = player_lineups["Goals Scored"].sum()
            players_df.at[idx, "Assists"] = player_lineups["Assists"].sum()
            players_df.at[idx, "Games Won"] = (player_lineups["Result"] == "Win").sum()
            players_df.at[idx, "Games Drew"] = (player_lineups["Result"] == "Draw").sum()
            players_df.at[idx, "Games Lost"] = (player_lineups["Result"] == "Loss").sum()
            players_df.at[idx, "MVP"] = (matches_df["MVP"] == name).sum()
            players_df.at[idx, "Goal/Game"] = (
                players_df.at[idx, "Goal Scored"] / players_df.at[idx, "Match Played"]
                if players_df.at[idx, "Match Played"] > 0 else 0
            )

        # Add % Win column
        players_df["% Win"] = players_df.apply(
            lambda row: (row["Games Won"] / row["Match Played"]) * 100 if row["Match Played"] > 0 else 0,
            axis=1
        )

        # Sort by Games Won, % Win, MVP, Goal Scored
        players_df = players_df.sort_values(
            by=["Games Won", "% Win", "MVP", "Goal Scored"],
            ascending=[False, False, False, False]
        )

        # Save updated file
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            players_df.to_excel(writer, sheet_name="Players", index=False)
            matches_df.to_excel(writer, sheet_name="Matches", index=False)
            lineups_df.to_excel(writer, sheet_name="Team Lineups", index=False)
        output.seek(0)

        st.download_button(
            label="Download Updated Excel",
            data=output,
            file_name="Updated_Football_Stats.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Show sorted table with same formatting
    st.subheader("Players Sorted by Performance")
    st.dataframe(
        players_df,
        use_container_width=True,
        column_config={
            "Goal/Game": st.column_config.NumberColumn(format="%.2f"),
            "% Win": st.column_config.NumberColumn(format="%.1f%%")
        }
    )
