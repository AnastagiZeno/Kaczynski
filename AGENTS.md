# Repository Guidelines

## Project Structure & Module Organization
The repository is intentionally compact. `big_a.py` holds every datasource fetch, transformation, and HTML/PNG/CSV export for the macro-plus-equity dashboard; running it produces `china_10yr_macro_equity.{png,csv,html}` in the repo root. `chelsea_schedule.py` is the second toy: it fetches Chelsea fixtures and emits `chelsea_recent_fixtures.html` with a ±30 天窗口。`goblue.sh` is a convenience script that stages, commits, and pushes with a fixed message, so update it before reusing. Keep extra datasets inside a dedicated `data/` folder (create it if needed) to avoid cluttering the root, and document new entry points in `README.md` so agents know where to start.

## Build, Test, and Development Commands
Create an isolated environment and install dependencies before touching Akshare or Plotly:
```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy matplotlib plotly akshare requests
python big_a.py                  # regenerates charts + exports
python chelsea_schedule.py       # 写出 HTML 赛程卡片
```
When iterating, run `python big_a.py --help` first if you add CLI arguments; keep default execution side-effect free beyond writing the export trio. `chelsea_schedule.py` should only hit the ESPN endpoint and write a single HTML file—avoid hidden side effects so it can be re-run safely.

## Coding Style & Naming Conventions
Follow standard Python style: 4-space indentation, `snake_case` for functions, and uppercase constants for tunables such as `FREQ` or `INDEX_MAP`. The current modules mix English identifiers with concise中文注释；扩展时保持这种双语色调。Prefer explicit helper functions (see `_get_index_close_primary` and `parse_event`) over inline blocks, and keep imports grouped by stdlib → third-party. Run `ruff check .` or `black big_a.py chelsea_schedule.py` if you introduce substantial code (add the tool to `requirements.txt` when you do).

## Testing Guidelines
There is no automated suite yet; rely on deterministic data slices. After each change, re-run `python big_a.py` and verify (1) console warnings only appear for unavailable endpoints, (2) generated CSVs have fresh timestamps, and (3) the HTML view renders both normalized and raw panels. For `chelsea_schedule.py`, confirm the ESPN payload still exposes `events`, that Beijing时间的排序正确，并在浏览器里 spot check 卡片布局。When touching API parsing logic, add `assert`-style smoke checks near the transform to surface schema drift.

## Commit & Pull Request Guidelines
Git history currently uses the terse `tick-tock` message from `goblue.sh`. Keep messages short but descriptive (e.g., `fix cpi fallback parsing`, `add chelsea window html`) so future diffs are traceable, and retire the helper script if it obscures intent. Every pull request should summarize the macro indices or fixtures touched, list reproducible steps (`python big_a.py` or `python chelsea_schedule.py`), link the issue, and—when visual changes occur—attach一张 HTML/PNG 截图。Mention external dependencies (Akshare rate limits, matplotlib fonts, ESPN availability) so reviewers can reproduce without surprises.
