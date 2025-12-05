#!/usr/bin/env python3
"""
Generate a minimalist HTML page that shows Chelsea fixtures
within a ±30 day window around today, rendered in Beijing time.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import requests
from zoneinfo import ZoneInfo

API_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/chelsea/schedule"
OUTPUT_HTML = Path("chelsea_recent_fixtures.html")
WINDOW_DAYS = 30
CN_TZ = ZoneInfo("Asia/Shanghai")


def fetch_schedule() -> List[Dict[str, Any]]:
    """Return ESPN schedule payload for Chelsea."""
    response = requests.get(API_URL, timeout=20)
    response.raise_for_status()
    data = response.json()
    events = data.get("events")
    if events is None:
        raise ValueError("ESPN payload missing 'events'")
    return events


def parse_event(event: Dict[str, Any]) -> Dict[str, Any] | None:
    """Extract Chelsea-specific data from an ESPN event record."""
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    chelsea = None
    opponent = None
    for team in competitors:
        name = (team.get("team") or {}).get("displayName")
        if not name:
            continue
        if "chelsea" in name.lower():
            chelsea = team
        else:
            opponent = team
    if chelsea is None or opponent is None:
        return None
    raw_date = event.get("date")
    if not raw_date:
        return None
    if raw_date.endswith("Z"):
        raw_date = raw_date.replace("Z", "+00:00")
    kickoff_utc = dt.datetime.fromisoformat(raw_date).astimezone(dt.timezone.utc)
    kickoff_local = kickoff_utc.astimezone(CN_TZ)
    status = event.get("status") or {}
    status_type = (status.get("type") or {}).get("description") or status.get("type", {}).get("state") or "Scheduled"
    venue_info = (comp.get("venue") or {}).get("fullName") or "TBD"
    notes = comp.get("notes")
    if isinstance(notes, list) and notes:
        competition_name = notes[0].get("headline")
    elif isinstance(notes, str):
        competition_name = notes
    else:
        competition_name = event.get("shortName") or event.get("name")
    score_home = chelsea.get("score")
    score_away = opponent.get("score")
    display_score = ""
    if score_home is not None and score_away is not None:
        display_score = f"{score_home} - {score_away}"
    outcome = chelsea.get("winner")
    label_outcome = ""
    if outcome is True:
        label_outcome = "胜"
    elif outcome is False:
        label_outcome = "负"
    elif (status.get("type") or {}).get("completed"):
        label_outcome = "平"
    return {
        "kickoff_local": kickoff_local,
        "opponent": (opponent.get("team") or {}).get("displayName", "未知对手"),
        "home": chelsea.get("homeAway") == "home",
        "venue": venue_info,
        "competition": competition_name,
        "status": status_type,
        "score": display_score,
        "outcome": label_outcome,
    }


def filter_window(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return fixtures inside ±WINDOW_DAYS from now (local time)."""
    parsed = filter(None, (parse_event(evt) for evt in events))
    now = dt.datetime.now(CN_TZ)
    start = now - dt.timedelta(days=WINDOW_DAYS)
    end = now + dt.timedelta(days=WINDOW_DAYS)
    in_range = [
        evt for evt in parsed if start <= evt["kickoff_local"] <= end
    ]
    return sorted(in_range, key=lambda e: e["kickoff_local"])


def render_html(fixtures: List[Dict[str, Any]]) -> str:
    """Build the HTML string with a simple card layout."""
    generated = dt.datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")
    cards = []
    for fx in fixtures:
        date_str = fx["kickoff_local"].strftime("%Y-%m-%d %H:%M")
        home_away_badge = "主场" if fx["home"] else "客场"
        outcome = f"<span class='outcome'>{fx['outcome']}</span>" if fx["outcome"] else ""
        score = f"<div class='score'>{fx['score']}</div>" if fx["score"] else ""
        cards.append(
            f"""
            <article class="fixture">
              <header>
                <div class="date">{date_str}（北京时间）</div>
                <div class="competition">{fx['competition']}</div>
              </header>
              <div class="opponent">
                <span class="badge">{home_away_badge}</span>
                <span class="name">切尔西 vs {fx['opponent']}</span>
              </div>
              {score}
              <div class="meta">
                <span>{fx['venue']}</span>
                <span>{fx['status']}</span>
                {outcome}
              </div>
            </article>
            """
        )
    body = "\n".join(cards) if cards else "<p class='empty'>当前窗口内没有赛程。</p>"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>切尔西近期开赛日程</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1526;
      --card-bg: #112240;
      --accent: #1d9bf0;
      --text: #f5f7fa;
    }}
    body {{
      font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
      margin: 0;
      padding: 2.5rem 1rem;
      background: radial-gradient(circle at top, rgba(29,155,240,0.3), transparent 60%), var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}
    h1 {{
      text-align: center;
      letter-spacing: 0.1em;
      margin-bottom: 0.5rem;
    }}
    .generated {{
      text-align: center;
      color: #98a2b3;
      margin-bottom: 2rem;
      font-size: 0.9rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.25rem;
      max-width: 1200px;
      margin: 0 auto;
    }}
    .fixture {{
      background: var(--card-bg);
      border-radius: 1rem;
      padding: 1.25rem;
      box-shadow: 0 15px 30px rgba(0,0,0,0.35);
      border: 1px solid rgba(255,255,255,0.05);
      backdrop-filter: blur(10px);
    }}
    .fixture header {{
      display: flex;
      justify-content: space-between;
      font-size: 0.9rem;
      color: #d0d6e3;
      margin-bottom: 1rem;
    }}
    .opponent {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 1.1rem;
      font-weight: 600;
    }}
    .badge {{
      background: var(--accent);
      color: #05111f;
      padding: 0.15rem 0.6rem;
      border-radius: 999px;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .score {{
      font-size: 2rem;
      font-weight: 700;
      margin: 0.9rem 0;
      text-align: center;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.4rem;
      font-size: 0.85rem;
      color: #9fb0c7;
    }}
    .outcome {{
      font-weight: 600;
      color: var(--accent);
    }}
    .empty {{
      text-align: center;
      color: #cbd5f5;
      font-size: 1.05rem;
    }}
  </style>
</head>
<body>
  <h1>切尔西赛程快照</h1>
  <p class="generated">窗口：前后 {WINDOW_DAYS} 天 · 生成时间：{generated}</p>
  <section class="grid">
    {body}
  </section>
</body>
</html>
"""


def main() -> None:
    events = fetch_schedule()
    fixtures = filter_window(events)
    html = render_html(fixtures)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Generated {OUTPUT_HTML} with {len(fixtures)} fixtures.")


if __name__ == "__main__":
    main()
