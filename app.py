import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_FILE = "CALCIATORI_RDG.xlsx"
SEASON_2026 = (pd.Timestamp("2025-11-13"), pd.Timestamp("2026-11-12"))  # start, end (inclusive)
SEASON_2027 = (pd.Timestamp("2026-11-19"), pd.Timestamp("2027-11-18"))
MIN_GAMES_SERIAL = 5  # "Serial Winners / Losers" need MORE than this many games
MIN_GAMES_RATING = 5  # "Best Performers" needs MORE than this many games

st.set_page_config(page_title="Calciatori di Reading", layout="wide")
st.title("CALCIATORI DI READING")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path, mtime):
    """`mtime` is only here so the cache refreshes when the Excel file changes."""
    df = pd.read_excel(path, sheet_name="Team Lineups", engine="openpyxl")
    df["Date"] = pd.to_datetime(df["Date"])

    # A row with no Result is a placeholder (e.g. a player who switched teams mid-match
    # and is listed on both sides). The real row is the one with a Result, so drop the rest.
    df = df[df["Result"].notna()].copy()

    # MVP is recorded once per match (a player name) in the "Matches" sheet.
    matches = pd.read_excel(path, sheet_name="Matches", engine="openpyxl")
    matches["Date"] = pd.to_datetime(matches["Date"])
    matches["MVP"] = matches["MVP"].astype(str).str.strip()
    return df, matches


lineups_df, matches_df = load_data(DATA_FILE, os.path.getmtime(DATA_FILE))

last_update = lineups_df["Date"].max().strftime("%d %B %Y")
st.caption(f"Data collected since 13 November 2025 · Last update: {last_update}")


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def to_count(series):
    """Numeric counts; blanks and free-text notes (e.g. comments in 'Own Goals') count as 0."""
    return pd.to_numeric(series, errors="coerce").fillna(0)


def prepare_matches(df):
    """One row per player per match, with opponent score, result and clean numeric columns."""
    df = df.copy()
    df["Opp Score"] = df["Team Conceded"]

    df["Win"] = (df["Team Score"] > df["Opp Score"]).astype(int)
    df["Loss"] = (df["Team Score"] < df["Opp Score"]).astype(int)
    df["Draw"] = (df["Team Score"] == df["Opp Score"]).astype(int)
    df["Goal Diff"] = df["Team Score"] - df["Opp Score"]

    df["Goals Scored"] = df["Goals Scored"].fillna(0)
    df["Assists"] = df["Assists"].fillna(0)
    df["Own Goals"] = to_count(df["Own Goals"])
    df["Evaluation"] = pd.to_numeric(df["Evaluation"], errors="coerce")  # blanks stay NaN (not rated)
    return df


def compute_player_stats(df, mvp_names):
    """Leaderboard table (one row per player) for the matches in `df`.
    `mvp_names` = the MVP name of each match in the same period (from the Matches sheet)."""
    df = prepare_matches(df)
    g = df.groupby("Player Name")
    stats = pd.DataFrame({
        "Match Played": g.size(),
        "Games Won": g["Win"].sum(),
        "Games Drew": g["Draw"].sum(),
        "Games Lost": g["Loss"].sum(),
        "Goal Difference": g["Goal Diff"].sum(),
        "Goal Scored": g["Goals Scored"].sum(),
        "Assists": g["Assists"].sum(),
        "Own Goals": g["Own Goals"].sum(),
        "Average Rating": g["Evaluation"].mean().round(2),  # ignores matches with no rating
        "Rated Games": g["Evaluation"].count(),  # games where the player has a rating
    })
    stats["% Win"] = (stats["Games Won"] / stats["Match Played"]).round(2)
    stats["% Lost"] = (stats["Games Lost"] / stats["Match Played"]).round(2)
    stats["Goal/Game"] = (stats["Goal Scored"] / stats["Match Played"]).round(2)
    stats = stats.reset_index()
    stats["MVP"] = stats["Player Name"].map(mvp_names.value_counts()).fillna(0).astype(int)

    for col in ["Goal Difference", "Goal Scored", "Assists", "MVP", "Own Goals"]:
        if (stats[col] % 1 == 0).all():
            stats[col] = stats[col].astype(int)

    columns = ["Player Name", "Match Played", "Games Won", "Games Drew", "Games Lost",
               "% Win", "% Lost", "Goal Difference", "Goal Scored", "Assists",
               "Goal/Game", "MVP", "Own Goals", "Average Rating", "Rated Games"]
    return stats[columns]


def compute_pairings(df):
    """Square matrix: times each pair of players were on the same team.
    The diagonal is the number of games each player played."""
    m = df.assign(v=1).pivot_table(
        index=["Match ID", "Team (A/B)"], columns="Player Name",
        values="v", aggfunc="max", fill_value=0,
    )
    co = m.T.dot(m)
    order = np.argsort(-np.diag(co.values), kind="stable")
    return co.iloc[order, order]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def render_table(df, key, height=180, leaderboard=False):
    # Position in the ranking (1 = first row), shown as the left-most column
    df = df.reset_index(drop=True)
    df.insert(0, "#", np.arange(1, len(df) + 1))

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=False, sortable=True, filter=leaderboard)
    if leaderboard:
        gb.configure_pagination(enabled=True)
    gb.configure_grid_options(domLayout="normal", suppressHorizontalScroll=False)
    for col in df.columns:
        if col == "#":
            gb.configure_column(col, width=70, minWidth=70, maxWidth=70, cellStyle={"textAlign": "center"})
        elif col == "Player Name":
            gb.configure_column(col, minWidth=150, cellStyle={"textAlign": "left"})
        else:
            gb.configure_column(col, minWidth=120, cellStyle={"textAlign": "center"})
    opts = gb.build()
    opts["suppressAutoSize"] = True
    opts["suppressSizeToFit"] = True
    AgGrid(
        df,
        gridOptions=opts,
        enable_enterprise_modules=False,
        height=height,
        fit_columns_on_grid_load=False,
        key=key,
    )


def render_top5(stats, key, title, caption, sort_col, cols, min_games=0, rename=None):
    st.subheader(title)
    st.caption(caption)
    pool = stats[(stats["Match Played"] > min_games) & stats[sort_col].notna()]
    if pool.empty:
        st.info("Not enough games yet.")
        return
    top = pool.sort_values(by=sort_col, ascending=False).head(5)[cols]
    if rename:
        top = top.rename(columns=rename)
    render_table(top, key=key)


def render_trends(period_df, key):
    st.subheader("Trends Over Time")
    st.caption("Pick a stat and one or more players to see match-by-match progression")

    progress_df = prepare_matches(period_df)
    progress_df = progress_df.sort_values(["Player Name", "Date", "Match ID"])
    progress_df["Match Played"] = 1
    grp = progress_df.groupby("Player Name", group_keys=False)
    progress_df["Match Played"] = grp["Match Played"].cumsum()
    progress_df["Cumulative Goal Scored"] = grp["Goals Scored"].cumsum()
    progress_df["Cumulative Assists"] = grp["Assists"].cumsum()
    progress_df["Cumulative Wins"] = grp["Win"].cumsum()
    progress_df["Cumulative Losses"] = grp["Loss"].cumsum()

    options = {
        "Match played": "Match Played",
        "Goal scored": "Goals Scored",
        "Assists": "Assists",
        "Cumulative goal scored": "Cumulative Goal Scored",
        "Cumulative assists": "Cumulative Assists",
        "Cumulative wins": "Cumulative Wins",
        "Cumulative losses": "Cumulative Losses",
    }

    col_metric, col_players = st.columns([1, 2])
    with col_metric:
        metric_label = st.selectbox("Stat (Y axis)", list(options.keys()), index=3, key=f"{key}_metric")
        metric_col = options[metric_label]

    all_players = sorted(progress_df["Player Name"].dropna().unique())
    default_players = (
        progress_df.groupby("Player Name")["Cumulative Goal Scored"].max()
        .sort_values(ascending=False).head(8).index.tolist()
    )
    with col_players:
        chosen = st.multiselect("Players", all_players, default=default_players, key=f"{key}_players")

    if not chosen:
        st.info("Select at least one player to plot.")
        return

    plot_df = progress_df[progress_df["Player Name"].isin(chosen)]
    fig = px.line(
        plot_df, x="Date", y=metric_col, color="Player Name", markers=True,
        labels={"Date": "Match date", metric_col: metric_label, "Player Name": "Player"},
    )
    fig.update_layout(
        legend_title_text="Player", hovermode="x unified",
        margin=dict(l=10, r=10, t=20, b=10), height=480,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key}_trend_chart")


def render_heatmap(period_df):
    st.subheader("Player Pairing Heatmap")
    st.caption("Number of times each player played with each other player (same team). "
               "The diagonal shows the number of games played by each player, for reference.")

    pairs = compute_pairings(period_df)
    n = len(pairs)
    vmax = max(1, int(pairs.values.max()))
    fig_size = max(6, n * 0.7)

    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    cax = ax.imshow(pairs.values, aspect="auto", cmap="magma_r", vmin=0, vmax=vmax)
    fig.colorbar(cax)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(pairs.columns, fontsize=15, fontweight="bold", rotation=90)
    ax.set_yticklabels(pairs.index, fontsize=15, fontweight="bold")
    ax.tick_params(top=True, bottom=True, labeltop=True, labelbottom=True)

    for i in range(n):
        for j in range(n):
            value = pairs.iloc[i, j]
            ax.text(j, i, f"{int(value)}", ha="center", va="center",
                    color="white" if value > 0.5 * vmax else "black",
                    fontsize=15, fontweight="bold")

    ax.set_title("Player Pairings")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def render_period(period_df, key, subtitle=None, show_best_performers=True):
    if subtitle:
        st.caption(subtitle)
    if period_df.empty:
        st.info("No matches played in this period yet.")
        return

    period_mvps = matches_df.loc[matches_df["Match ID"].isin(period_df["Match ID"]), "MVP"]
    stats = compute_player_stats(period_df, period_mvps)

    # General leaderboard
    st.subheader("General Leaderboard")
    st.caption("Sorted by Games Won, Games Drew, MVP, and Goal Scored. "
               "Only players with one or more games played in this period are visible. "
               "Average Rating is the mean of the ratings given to the player (blank if never rated).")
    leaderboard = stats.drop(columns="Rated Games").sort_values(
        by=["Games Won", "% Win", "Average Rating", "MVP"], ascending=False
    )
    render_table(leaderboard, key=f"{key}_leaderboard", height=400, leaderboard=True)

    render_top5(stats, f"{key}_vet", "Veterani",
                "Top 5 players by number of matches played",
                "Match Played", ["Player Name", "Match Played"])
    render_top5(stats, f"{key}_goals", "Capocannonieri",
                "Top 5 players by number of goals scored",
                "Goal Scored", ["Player Name", "Goal Scored", "Goal/Game"])
    if show_best_performers:
        rated = lineups_df.loc[lineups_df["Evaluation"].notna(), "Date"]
        since = f"; ratings recorded since {fmt(rated.min())}" if not rated.empty else ""
        render_top5(stats, f"{key}_rating", "Best Performers",
                    f"Top 5 players by average rating. Match Played counts only the games where the player "
                    f"was rated. Only players with more than {MIN_GAMES_RATING} games played overall "
                    f"are included{since}",
                    "Average Rating", ["Player Name", "Average Rating", "Rated Games"],
                    min_games=MIN_GAMES_RATING, rename={"Rated Games": "Match Played"})
    render_top5(stats, f"{key}_assists", "Fantasisti",
                "Top 5 players by number of assists",
                "Assists", ["Player Name", "Assists"])
    render_top5(stats, f"{key}_mvp", "MVP",
                "Top 5 players by number of MVP awards",
                "MVP", ["Player Name", "MVP"])
    render_top5(stats, f"{key}_win", "Serial Winners",
                f"Top 5 players by ratio of games won (only players with more than {MIN_GAMES_SERIAL} games played)",
                "% Win", ["Player Name", "% Win", "Games Won"], min_games=MIN_GAMES_SERIAL)
    render_top5(stats, f"{key}_lost", "Serial Losers",
                f"Top 5 players by ratio of games lost (only players with more than {MIN_GAMES_SERIAL} games played)",
                "% Lost", ["Player Name", "% Lost", "Games Lost"], min_games=MIN_GAMES_SERIAL)
    render_top5(stats, f"{key}_og", "Il Re dell'Autogol",
                "Top 5 players by number of own goals",
                "Own Goals", ["Player Name", "Own Goals"])

    render_trends(period_df, key)
    render_heatmap(period_df)


# ---------------------------------------------------------------------------
# Three views of the same dashboard (2027 Season, 2026 Season, All Time)
# ---------------------------------------------------------------------------
def fmt(d):
    return d.strftime("%d %B %Y").lstrip("0")


def in_season(season):
    start, end = season
    return lineups_df[(lineups_df["Date"] >= start) & (lineups_df["Date"] <= end)]


tab_2027, tab_2026, tab_all = st.tabs(["2027 Season", "2026 Season", "All Time"])

with tab_2027:
    render_period(
        in_season(SEASON_2027), "s2027",
        f"Season started on {fmt(SEASON_2027[0])} and will finish on {fmt(SEASON_2027[1])}.",
    )

with tab_2026:
    render_period(
        in_season(SEASON_2026), "s2026",
        f"Season started on {fmt(SEASON_2026[0])} and finished on {fmt(SEASON_2026[1])}.",
        show_best_performers=False,
    )

with tab_all:
    render_period(lineups_df, "all")

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
with open(DATA_FILE, "rb") as file:
    st.download_button(
        label="Download Data",
        data=file,
        file_name="data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
