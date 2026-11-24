import io
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

    # Positions: "Players" sheet, column "Position". A cell can hold several, e.g. "Defender, Midfielder".
    # Blank = unknown. Anything that is not Defender / Midfielder / Forward is reported, not guessed.
    players = pd.read_excel(path, sheet_name="Players", engine="openpyxl")
    positions, unknown = {}, set()
    for name, cell in zip(players["Player Name"], players["Position"]):
        roles = []
        if pd.notna(cell):
            for part in str(cell).split(","):
                role = part.strip().title()
                if role in ROLES:
                    roles.append(role)
                elif role:
                    unknown.add(role)
        positions[name] = tuple(dict.fromkeys(roles))
    return df, matches, positions, sorted(unknown)


ROLES = ["Defender", "Midfielder", "Forward"]
lineups_df, matches_df, positions_map, unknown_positions = load_data(DATA_FILE, os.path.getmtime(DATA_FILE))

last_update = lineups_df["Date"].max().strftime("%d %B %Y")
st.caption(f"Data collected since 13 November 2025 · Last update: {last_update}")


# st.fragment (Streamlit 1.37+) makes widgets inside a function rerun only that function,
# not the whole page. On older versions this quietly does nothing.
fragment = getattr(st, "fragment", lambda f: f)


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


@fragment
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


@st.cache_data(show_spinner="Drawing heatmap...")
def heatmap_png(pairs):
    """Render the pairing matrix once to a PNG. Cached, because drawing ~2,600 labels on a huge
    figure is the slowest thing in the app and the result only changes when the data does."""
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
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=72)
    plt.close(fig)
    return buf.getvalue()


def render_heatmap(period_df):
    st.subheader("Player Pairing Heatmap")
    st.caption("Number of times each player played with each other player (same team). "
               "The diagonal shows the number of games played by each player, for reference.")
    st.image(heatmap_png(compute_pairings(period_df)), use_container_width=True)


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
        by=["Games Won", "Games Drew", "MVP", "Goal Scored"], ascending=False
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
# Team generator
# ---------------------------------------------------------------------------
TEAM_COUNTS = [2, 4]
MIN_PER_TEAM = 2      # need at least this many players per team to generate
REFERENCE_GAMES = 5   # "average" and "spread" are measured on players with at least this many games
SHRINK_GAMES = 8      # a player with N games counts N/(N+8) of their stats; the rest is "average"
IMPACT_ALPHA = 3      # ridge strength for Player Impact: higher = players with few games stay closer to 0
IMPACT_EXTRA_SHRINK = 12  # few-games penalty: a player with G games keeps G/(G+12) of their rating (2 games = 14%, 8 games = 40%, 30 games = 71%). Higher = harsher
MVP_GOALS_PER_AWARD = 0.6  # how much each MVP award adds to Impact (goals/match). 0 = ignore MVPs; 0.2 = gentle; 0.5 = strong (hurts match prediction a little); 0.8 = dominant
MVP_FIRST_AWARD = 0.8      # the 1st MVP award counts only this much of a full award (could be coincidence); later ones count fully
MVP_CAP = 6                # awards beyond this many add nothing more
POSITION_NORMALISE = True   # goals/assists compared with players of the same position (False = everyone together)
ASSISTS_WEIGHT = 0.2       # assists per game: same idea as GOALS_WEIGHT. 0 = ignore
GOALS_WEIGHT = 0.3         # goals scored per game: Impact bonus (goals/match) for each standard deviation above the average regular. 0 = ignore
# Manual adjustments in Strength points (+ stronger, - weaker), applied after everything else. For things the data
# cannot show. Edison: always placed with the strongest players to balance teams, so his results flatter him
# (his average teammate is the strongest of any regular). -14 puts him below every player who has an MVP award.
MANUAL_ADJUSTMENT = {}   # e.g. {"Edison": -14.0}. Edison's -14 was removed on request
OFF_ALPHA = 4             # ridge strength for the attack ratings (used only to pick a multi-position player's best role)
DEF_ALPHA = 6             # ridge strength for the defence ratings (same)
IMPACT_CLIP = 5       # a match counts as at most +-5 goals, so one 13-2 blowout cannot dominate
BALANCE_TOLERANCE = 2.0  # splits within this of the best one are treated as equally good (then picked at random)


@st.cache_data(show_spinner=False)
def player_impact(lineups):
    """Player Impact = adjusted plus-minus, in goals per match.

    Every match is one equation: (team A goal difference) = sum of Impact of A's players
    minus sum of Impact of B's players. Solving all 69 matches together (ridge regression) credits a
    player for how much their team beats the opponents *given who else was on the pitch*, so a
    player who only ever plays with strong teammates is not flattered. Ridge pulls players with
    few games towards 0 (average) automatically. Positive = their team does better with them."""
    d = lineups[["Match ID", "Team (A/B)", "Player Name", "Team Score", "Team Conceded"]]
    side = np.where(d["Team (A/B)"] == "A", 1, -1)
    X = pd.pivot_table(d.assign(v=side), index="Match ID", columns="Player Name",
                       values="v", aggfunc="sum", fill_value=0)
    a_rows = d[d["Team (A/B)"] == "A"].groupby("Match ID").first()
    y = (a_rows["Team Score"] - a_rows["Team Conceded"]).reindex(X.index).clip(-IMPACT_CLIP, IMPACT_CLIP).values
    size_diff = X.sum(axis=1).values          # a team with an extra player has an edge (almost always 0)
    A = np.column_stack([X.values, size_diff])
    penalty = np.diag([IMPACT_ALPHA] * X.shape[1] + [1e-6])
    beta = np.linalg.solve(A.T @ A + penalty, A.T @ y)
    games = (X != 0).sum(axis=0).values
    impact = beta[:-1] * games / (games + IMPACT_EXTRA_SHRINK)
    return pd.Series(impact, index=X.columns, name="Impact")


def build_ratings(stats, impact, positions=None):
    """Strength (average regular ~50, spread ~10) from Player Impact, plus an Attack score
    (goals and assists per game) used as a secondary balance."""
    s = stats.copy()
    n = s["Match Played"]
    ref = n >= REFERENCE_GAMES
    if ref.sum() < 5:
        ref = n > 0

    def z(x):
        sd = x[ref].std(ddof=0)
        return ((x - x[ref].mean()) / (sd if sd > 0 else 1)).clip(-3, 3)

    def scale(x):
        sd = x[ref].std(ddof=0)
        return 50 + 10 * (x - x[ref].mean()) / (sd if sd > 0 else 1)

    names = s["Player Name"]

    def z_by_position(x):
        """z-score of x against regulars of the same listed position (a multi-position player: average over his
        positions). Players with no position, or a position with fewer than 3 regulars, use everyone as reference."""
        overall = z(x)
        if not positions or not POSITION_NORMALISE:
            return overall
        per_role = {}
        for role in ROLES:
            in_role = names.map(lambda p: role in positions.get(p, ()))
            pool = x[ref & in_role]
            if len(pool) >= 3:
                sd = pool.std(ddof=0)
                per_role[role] = ((x - pool.mean()) / (sd if sd > 0 else 1)).clip(-3, 3)
        out = overall.copy()
        for i in x.index:
            zs = [per_role[r][i] for r in positions.get(names[i], ()) if r in per_role]
            if zs:
                out[i] = sum(zs) / len(zs)
        return out

    shrink = n / (n + SHRINK_GAMES)
    attack = 0.6 * z(s["Goal Scored"] / n) * shrink + 0.4 * z(s["Assists"] / n) * shrink
    imp = s["Player Name"].map(impact).fillna(0.0)

    # MVP bonus: one award barely counts, repeated awards count a lot (capped).
    awards = s["MVP"].astype(float)
    effective = np.where(awards >= 1, MVP_FIRST_AWARD + np.minimum(awards - 1, MVP_CAP - 1), 0.0)
    trust = n / (n + IMPACT_EXTRA_SHRINK)  # same few-games penalty, applied to the MVP bonus too
    imp_total = imp + MVP_GOALS_PER_AWARD * effective * trust + GOALS_WEIGHT * z_by_position(s["Goal Scored"] / n) * trust
    imp_total = imp_total + ASSISTS_WEIGHT * z_by_position(s["Assists"] / n) * trust

    out = pd.DataFrame({
        "Player Name": s["Player Name"],
        "Strength": scale(imp_total).round(1),
        "Impact": imp.round(2),
        "MVP": s["MVP"],
        "Attack": scale(attack).round(1),
        "Matches": n,
        "Win %": ((s["Games Won"] / n) * 100).round(0).astype(int),
    })
    out = out.set_index("Player Name")
    for name, adj in MANUAL_ADJUSTMENT.items():
        if name in out.index:
            out.loc[name, "Strength"] = round(out.loc[name, "Strength"] + adj, 1)
    return out


@st.cache_data(show_spinner=False)
def player_off_def(lineups):
    """Attack and defence ratings from match results, in goals per match, adjusted for teammates and opponents.

    Every (match, team) is one equation: goals scored by the team = sum of the Attack of its players
    minus sum of the Defence of the opposing players (+ a constant). Solved with ridge regression, so a
    defender is credited for the goals his side did NOT concede given who they played against, and a forward for the
    goals the side did score given who defended against them."""
    d = lineups[["Match ID", "Team (A/B)", "Player Name", "Team Score"]]
    names = sorted(d["Player Name"].unique())
    idx = {p: i for i, p in enumerate(names)}
    teams = {k: (list(g["Player Name"]), g["Team Score"].iloc[0]) for k, g in d.groupby(["Match ID", "Team (A/B)"])}
    n = len(names)
    Xo = np.zeros((len(teams), n))
    Xd = np.zeros((len(teams), n))
    y = np.zeros(len(teams))
    for r, ((m, side), (own, goals)) in enumerate(teams.items()):
        for p in own:
            Xo[r, idx[p]] = 1
        for p in teams.get((m, "B" if side == "A" else "A"), ([], 0))[0]:
            Xd[r, idx[p]] = -1
        y[r] = goals
    A = np.column_stack([Xo, Xd, np.ones(len(teams))])
    penalty = np.diag([OFF_ALPHA] * n + [DEF_ALPHA] * n + [0])
    beta = np.linalg.solve(A.T @ A + penalty, A.T @ y)
    return pd.DataFrame({"Off": beta[:n], "Def": beta[n:2 * n]}, index=names)


def assign_positions(ratings, stats, off_def, positions):
    """Puts every player in ONE position.

    A player listed in one position is placed there. A player listed in several is placed in the one where his own
    rating is highest (Forward: goals per game + Attack; Midfielder: assists per game + overall Impact;
    Defender: Defence + overall Impact, all on the same 50 / 10 scale). No position listed = '-'."""
    r = ratings.copy()
    n = r["Matches"]
    ref = n >= REFERENCE_GAMES
    if ref.sum() < 5:
        ref = n > 0
    f = n / (n + IMPACT_EXTRA_SHRINK)
    st_ = stats.set_index("Player Name").reindex(r.index)

    def z(x):
        sd = x[ref].std(ddof=0)
        return ((x - x[ref].mean()) / (sd if sd > 0 else 1)).clip(-3, 3)

    od = off_def.reindex(r.index).fillna(0.0)
    r["Forward"] = 0.6 * z(st_["Goal Scored"] / n) * f + 0.4 * z(od["Off"]) * f
    r["Midfielder"] = 0.5 * z(st_["Assists"] / n) * f + 0.5 * z(r["Impact"])
    r["Defender"] = 0.75 * z(od["Def"]) * f + 0.25 * z(r["Impact"])
    for c in ROLES:   # same 50 / 10 scale for the three roles, so they can be compared
        sd = r[c][ref].std(ddof=0)
        r[c] = (50 + 10 * (r[c] - r[c][ref].mean()) / (sd if sd > 0 else 1)).round(1)

    listed = {p: positions.get(p, ()) for p in r.index}
    best = {p: (max(listed[p], key=lambda x: r.loc[p, x]) if listed[p] else None) for p in r.index}
    r["Listed"] = ["/".join(x[:1] for x in listed[p]) or "-" for p in r.index]
    r["Position"] = [best[p][0] if best[p] else "-" for p in r.index]
    return r


def balance_by_position(strength, groups, n_teams, seed, restarts=200):
    """Split players into `n_teams` teams, position by position.

    1. Players are grouped by position. Each group is dealt out so every team gets the same number of that
       position (when a group does not divide exactly, the spare players go to the teams that currently have the
       fewest players, so team sizes never differ by more than one).
    2. Within those quotas, players of the same position are swapped between teams until the teams' Strength
       is as even as possible (a team with an extra player is expected to be a bit stronger in total).
    Random starts are repeated; one of the best splits found is picked at random, so a new seed gives a new split."""
    strength = np.asarray(strength, float)
    groups = np.asarray(groups)
    n = len(strength)
    excess = strength - strength.mean()   # strength above or below the average player
    same_group = groups[:, None] == groups[None, :]
    rng = np.random.default_rng(seed)
    found = {}

    for _ in range(restarts):
        labels = np.full(n, -1)
        sizes = np.zeros(n_teams)
        for g in rng.permutation(np.unique(groups)):
            members = rng.permutation(np.flatnonzero(groups == g))
            quota = np.full(n_teams, len(members) // n_teams)
            spare = len(members) % n_teams
            for t in sorted(range(n_teams), key=lambda t: (sizes[t], rng.random()))[:spare]:
                quota[t] += 1
            labels[members] = np.repeat(np.arange(n_teams), quota)
            sizes += quota
        while True:
            dev = np.bincount(labels, weights=excess, minlength=n_teams)
            li, lj = labels[:, None], labels[None, :]
            ei = excess[:, None]
            ej = excess[None, :]
            # swap i (team li) with j (team lj): team li gains ej-ei, team lj gains ei-ej
            delta = (dev[li] + ej - ei) ** 2 + (dev[lj] + ei - ej) ** 2 - dev[li] ** 2 - dev[lj] ** 2
            delta = np.where(same_group & (li != lj), delta, 0.0)
            k = np.argmin(delta)
            i, j = divmod(k, n)
            if delta[i, j] >= -1e-9:
                break
            labels[i], labels[j] = labels[j], labels[i]
        key = tuple(sorted(tuple(np.flatnonzero(labels == t)) for t in range(n_teams)))
        dev = np.bincount(labels, weights=excess, minlength=n_teams)
        found[key] = float((dev ** 2).sum())

    best = min(found.values())
    good = [k for k, c in found.items() if c <= best + BALANCE_TOLERANCE]
    if len(good) < 4:  # small pools: still offer a few of the best splits so "generate again" can vary
        good = sorted(found, key=found.get)[:4]
    chosen = list(good[rng.integers(len(good))])
    rng.shuffle(chosen)
    return [list(t) for t in chosen], len(good)


@fragment
def render_team_generator(stats):
    st.subheader("Team Generator")
    st.caption("Builds balanced teams from the All Time stats. Pick the players who turned up and choose 2 or 4 teams. "
               "Players are split by position first, so every team gets the same number of defenders, midfielders and "
               "forwards, then balanced on Strength. Press the button again for a different, similarly balanced split.")

    ratings = assign_positions(build_ratings(stats, player_impact(lineups_df), positions_map),
                               stats, player_off_def(lineups_df), positions_map)
    if unknown_positions:
        st.warning("Position labels not recognised (ignored): " + ", ".join(unknown_positions)
                   + ". Use Defender, Midfielder or Forward.")

    n_teams = st.radio("Number of teams", TEAM_COUNTS, horizontal=True, key="tg_teams")
    chosen = st.multiselect("Players available", sorted(ratings.index), key="tg_players")
    minimum = MIN_PER_TEAM * n_teams
    ready = len(chosen) >= minimum
    if ready:
        low, extra = divmod(len(chosen), n_teams)
        st.caption(f"{len(chosen)} players selected: " + (f"{n_teams} teams of {low}." if extra == 0 else
                   f"{extra} team{'s' if extra > 1 else ''} of {low + 1} and {n_teams - extra} of {low}."))
    else:
        st.info(f"Select at least {minimum} players ({MIN_PER_TEAM} per team). {len(chosen)} selected so far.")

    signature = (n_teams, tuple(sorted(chosen)))
    if st.button("Generate teams", disabled=not ready, key="tg_go"):
        seed = st.session_state.get("tg_seed", 0) + 1
        st.session_state["tg_seed"] = seed
        pool = ratings.loc[sorted(chosen)]
        teams, n_options = balance_by_position(pool["Strength"], pool["Position"], n_teams, seed)
        st.session_state["tg_result"] = {
            "signature": signature,
            "teams": [[pool.index[i] for i in t] for t in teams],
            "options": n_options,
        }

    result = st.session_state.get("tg_result")
    if not ready or not result or result["signature"] != signature:
        return

    names = "ABCD"
    cols = st.columns(n_teams)
    summary = []
    for t, members in enumerate(result["teams"]):
        team = ratings.loc[members].sort_values("Strength", ascending=False).reset_index()
        with cols[t]:
            st.markdown(f"**Team {names[t]}**")
            st.dataframe(team[["Player Name", "Position", "Strength", "Matches"]], hide_index=True, use_container_width=True)
        summary.append({
            "Team": f"Team {names[t]}",
            "Players": len(team),
            "Total Strength": round(team["Strength"].sum(), 1),
            "Avg Strength": round(team["Strength"].mean(), 1),
            "Defenders": int((team["Position"] == "D").sum()),
            "Midfielders": int((team["Position"] == "M").sum()),
            "Forwards": int((team["Position"] == "F").sum()),
            "No position": int((team["Position"] == "-").sum()),
            "Avg Win %": round(team["Win %"].mean()),
        })
    summary_df = pd.DataFrame(summary)
    gap = summary_df["Avg Strength"].max() - summary_df["Avg Strength"].min()
    st.markdown("**Balance check**")
    st.dataframe(summary_df, hide_index=True, use_container_width=True)
    st.caption(f"Gap in average Strength between the strongest and weakest team: {gap:.1f} points "
               f"(a single player is worth about 10). {result['options']} candidate split(s) were considered this round.")

    with st.expander("How are the teams built?"):
        st.markdown(
            "1. **Every player is placed in one position.** A player listed in one position is placed there. "
            "A player listed in two (for example Defender and Midfielder) is placed in the one where his own rating is "
            "highest. Players with no position in the sheet form a separate group (shown as -).\n"
            "2. **Each position group is dealt out evenly.** With 2 teams, a group of 4 defenders gives 2 to each team. "
            "If a group doesn't divide exactly, the spare players go to the teams with the fewest "
            "players so far, so team sizes never differ by more than one.\n"
            "3. **Strength is balanced within those groups.** Players of the same position are swapped between teams "
            "until the teams' Strength is as even as possible, and one of the best splits is picked at random."
        )
    with st.expander("How is Strength calculated?"):
        st.markdown(
            "**Strength** is based on each player's **Impact**: how much better (or worse) their team does "
            "when they play, measured in goals per match. Every match in the spreadsheet is used. A team's goal "
            "difference is explained by who played on each side, and all matches are solved together, so a player is "
            "credited for results *after accounting for their teammates and their opponents* (not just their own goals). "
            "Blowouts count as at most 5 goals. **Players with few games are penalised**: a player keeps only "
            f"games / (games + {IMPACT_EXTRA_SHRINK}) of their rating (for example about {2 / (2 + IMPACT_EXTRA_SHRINK):.0%} with 2 games, "
            f"{8 / (8 + IMPACT_EXTRA_SHRINK):.0%} with 8, {30 / (30 + IMPACT_EXTRA_SHRINK):.0%} with 30), "
            "so a great run over a handful of matches does not make anyone a star.\n\n"
            "**MVP awards** are then added as a bonus: the first award counts about 80% of a full "
            f"award, each further award counts fully, up to {MVP_CAP}. Each full award is worth "
            f"{MVP_GOALS_PER_AWARD} goals per match of Impact (setting `MVP_GOALS_PER_AWARD`), reduced by the same few-games penalty. "
            f"**Goals scored per game** add a bonus too: {GOALS_WEIGHT} goals per match of Impact for each standard deviation "
            "above the average regular **of the same position** (a defender is compared with defenders, a forward with forwards; below average counts against), with the same few-games penalty. "
            f"**Assists per game** work the same way, at {ASSISTS_WEIGHT} per standard deviation.\n\n"
            "Strength rescales Impact so an average regular is about 50 and the spread is about 10."
            + (" **Manual adjustments** (set by hand): "
               + ", ".join(f"{k} {v:+.0f}" for k, v in MANUAL_ADJUSTMENT.items()) + "." if MANUAL_ADJUSTMENT else "")
        )
    with st.expander("All players: position, Strength, Impact and MVP awards"):
        full = ratings.reset_index().sort_values(["Strength", "Matches"], ascending=False)
        full.insert(0, "#", np.arange(1, len(full) + 1))
        st.dataframe(full[["#", "Player Name", "Listed", "Position", "Strength", "Forward", "Midfielder", "Defender",
                           "Impact", "MVP", "Matches"]], hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Tabs: 2027 Season, 2026 Season, All Time, Team Generator
# ---------------------------------------------------------------------------
def fmt(d):
    return d.strftime("%d %B %Y").lstrip("0")


def in_season(season):
    start, end = season
    return lineups_df[(lineups_df["Date"] >= start) & (lineups_df["Date"] <= end)]


tab_2027, tab_2026, tab_all, tab_teams = st.tabs(["2027 Season", "2026 Season", "All Time", "Team Generator"])

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

with tab_teams:
    render_team_generator(compute_player_stats(lineups_df, matches_df["MVP"]))

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
