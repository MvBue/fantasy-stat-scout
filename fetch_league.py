#!/usr/bin/env python3
"""
Export an ESPN Fantasy Football league to JSON for the comparison app.

Exports every rostered player (with owning team) plus the top available
players (free agents + waivers) per position, with weekly game stats.

Setup:
    pip install espn-api

Private league: copy two cookies from your browser while logged in to
fantasy.espn.com (DevTools > Application > Cookies > https://fantasy.espn.com):
    espn_s2  (long string)
    SWID     (looks like {XXXXXXXX-XXXX-...}, include the braces)

Usage:
    python fetch_league.py --league 123456 --year 2026 \
        --espn-s2 "AEB..." --swid "{ABC...}"
    # or set env vars ESPN_LEAGUE_ID, ESPN_S2, ESPN_SWID (and optionally ESPN_YEAR)

Output: league_data.json (load it into the app with "Load data").
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from espn_api.football import League

# Stat keys kept per game. Names come from espn_api's PLAYER_STATS_MAP.
STAT_KEYS = [
    "passingAttempts", "passingCompletions", "passingYards", "passingTouchdowns",
    "passingInterceptions",
    "rushingAttempts", "rushingYards", "rushingTouchdowns",
    "receivingTargets", "receivingReceptions", "receivingYards",
    "receivingTouchdowns", "receivingYardsAfterCatch",
    "lostFumbles",
]

# How many available (FA + waiver) players to pull per position, sorted by
# % owned across ESPN. Together with all rostered players this covers
# practically every player with a fantasy-relevant role. Scale with --depth.
FA_PER_POSITION = {"QB": 50, "RB": 120, "WR": 160, "TE": 80, "K": 32, "D/ST": 32}

BATCH = 50  # player ids per player-card request


def slim(breakdown):
    return {k: breakdown[k] for k in STAT_KEYS if k in breakdown and breakdown[k]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", type=int, default=os.environ.get("ESPN_LEAGUE_ID"),
                    help="leagueId from the ESPN URL (or env ESPN_LEAGUE_ID)")
    now = datetime.now()
    # NFL season year: Jan-Jul still belongs to the previous season
    season = now.year if now.month >= 8 else now.year - 1
    ap.add_argument("--year", type=int,
                    default=int(os.environ.get("ESPN_YEAR") or season))
    ap.add_argument("--espn-s2", default=os.environ.get("ESPN_S2"))
    ap.add_argument("--swid", default=os.environ.get("ESPN_SWID"))
    ap.add_argument("--out", default="league_data.json")
    ap.add_argument("--depth", type=float, default=1.0,
                    help="scale the number of available players pulled (e.g. 0.5 or 2)")
    a = ap.parse_args()
    if not a.league:
        ap.error("--league or ESPN_LEAGUE_ID is required")

    print(f"Connecting to league {a.league} ({a.year})...")
    league = League(league_id=a.league, year=a.year, espn_s2=a.espn_s2, swid=a.swid)

    teams = [{"id": t.team_id, "name": t.team_name, "abbrev": t.team_abbrev}
             for t in league.teams]
    owner = {}
    for t in league.teams:
        for p in t.roster:
            owner[p.playerId] = t.team_id
    print(f"  {len(teams)} teams, {len(owner)} rostered players")

    available = set()
    for pos, n in FA_PER_POSITION.items():
        try:
            fas = league.free_agents(size=max(1, int(n * a.depth)), position=pos)
        except Exception as e:  # keep going if one position fails
            print(f"  warning: free agents for {pos} failed: {e}")
            continue
        available.update(p.playerId for p in fas if p.playerId not in owner)
    print(f"  {len(available)} available players (FA + waivers)")

    ids = list(owner) + sorted(available)
    players = []
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        res = league.player_info(playerId=chunk)
        if res is None:
            continue
        if not isinstance(res, list):
            res = [res]
        for p in res:
            weeks = {}
            for wk, s in p.stats.items():
                if not wk:  # 0 = season total, handled below
                    continue
                entry = {}
                if "breakdown" in s:
                    entry["pts"] = s.get("points", 0)
                    entry["stats"] = slim(s["breakdown"])
                    entry["played"] = bool(s["breakdown"])
                if "projected_points" in s:
                    entry["proj"] = s.get("projected_points", 0)
                if wk in p.schedule:
                    entry["opp"] = p.schedule[wk]["team"]
                if entry:
                    weeks[str(wk)] = entry
            players.append({
                "id": p.playerId,
                "name": p.name,
                "pos": p.position,
                "team": p.proTeam,
                "injury": p.injuryStatus if p.injuryStatus not in (None, "ACTIVE", "NORMAL") else "",
                "owner": owner.get(p.playerId),
                "pctOwned": p.percent_owned,
                "seasonPts": p.total_points,
                "projSeasonPts": p.projected_total_points,
                "weeks": weeks,
            })
        print(f"  stats {min(i + BATCH, len(ids))}/{len(ids)}")

    out = {
        "meta": {
            "league": league.settings.name,
            "leagueId": a.league,
            "year": a.year,
            "currentWeek": league.current_week,
            "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "teams": teams,
        },
        "players": players,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Wrote {a.out} ({len(players)} players)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Private league? Check --espn-s2 and --swid (SWID includes the braces).",
              file=sys.stderr)
        sys.exit(1)
