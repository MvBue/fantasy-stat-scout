# Fantasy Stat Scout

Compare and filter players from an ESPN Fantasy Football league: per game,
last 3 / last 5 games, season, and single weeks, with trend columns and
pickup / buy-low / sell-high ideas. Runs as a web app you can add to your
phone's home screen. GitHub fetches fresh league data twice a week.

## How it works
- `fetch_league.py` exports your league (rosters, free agents + waivers, weekly stats) to JSON.
- `.github/workflows/update-data.yml` runs that script on GitHub every Tuesday and Friday
  (and on every push to `main`), then publishes `site/` plus the fresh
  `league_data.json` to GitHub Pages.
- `site/index.html` is the app. It loads `league_data.json` from the same address
  and works offline with the last data it saw.

## One-time setup
1. Push this repo to GitHub (branch `main`).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Settings → Secrets and variables → Actions**:
   - Secrets: `ESPN_S2` and `ESPN_SWID` (login cookies from fantasy.espn.com; SWID includes the braces)
   - Variables: `ESPN_LEAGUE_ID` (the `leagueId=` number in your league URL).
     Optional: `ESPN_YEAR` to force a season.
4. **Actions → Update league data → Run workflow**. When it finishes, the run
   shows the site address (`https://<user>.github.io/<repo>/`).
5. Open that address in Chrome on your phone → menu → **Add to Home screen** / **Install app**.

## Privacy
On GitHub's free plan, Pages sites are public. Anyone with the address can see
your league's rosters and stats. Your ESPN cookies stay in GitHub Secrets and
are never published.

## Run locally
```
pip install -r requirements.txt
python fetch_league.py --league <leagueId> --espn-s2 "<espn_s2>" --swid "{<SWID>}" --out site/league_data.json
cd site && python -m http.server 8000   # then open http://localhost:8000
```

## When the update fails
- **401/403 or "espn_s2 and swid are required"**: the cookies expired. Copy new
  ones and update the two secrets.
- ESPN's API is unofficial and can change without notice.
