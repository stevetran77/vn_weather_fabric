# vn_weather_fabric

Data Engineer portfolio project on Microsoft Fabric (Trial). Time budget: 2 weeks.

## Docs (read before working)
- `docs/DESIGN.md`: agreed design (architecture, CI/CD, definition of done, open items)
- `docs/DATA_SOURCES.md`: surveyed APIs, licenses, risks
- `docs/NOTEBOOKS.md`: what each notebook and pipeline does
- `GLOSSARY.md`: domain vocabulary (City, Observation, Reading, Backfill, Refresh window, Model PM2.5, Province)

## Architecture summary
- Sources: Open-Meteo (34 cities, one per Province), provinces.open-api.vn, World Bank
- Batch: Bronze (Parquet) -> Silver, Gold (Delta); lakehouses `lh_bronze`, `lh_silver`, `lh_gold`
- Near-real-time: notebook polls every 2 hours -> Eventstream -> Eventhouse (micro-batch, not a true stream)
- A single workspace `de_vn_prod`, connected to GitHub (`main`, Git folder `fabric/`); no dev/test environment
- CI: GitHub Actions on a single `main` branch; every push runs ruff, pytest, gitleaks, and `scripts/validate_fabric_items.py`
- CD is manual: run "Update all" in Fabric Source control after CI is green (service principal automation was tried and dropped; see `docs/DESIGN.md`)
- `fabric-cicd` is deliberately not used

## Repo layout
- `fabric/`: workspace items (Git folder of `de_vn_prod`)
- `src/`: plain Python modules (API calls, transforms); notebooks only import and call them
- `tests/`: pytest tests for `src/`
- `scripts/`: helper scripts (Fabric item validation)
- `.github/workflows/`: `ci.yml`
- `docs/`: documentation, diagrams

## Conventions
- All markdown files and all code (identifiers, comments, docstrings, log messages, commit messages) in the repo must be in English
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- Fabric items use prefixes: `lh_`, `nb_`, `pl_`, `es_`, `eh_`
- Every function in `src/` must have a test

## Rules
- Never commit secrets, API keys or tokens, even in test files
- Do not hardcode environment-specific values (workspace IDs, etc.): use GitHub variables. If hardcoding is unavoidable, ask for approval first and explain why. The list of city names in the config file is approved. Approved: a notebook may bind `lh_bronze` as its default lakehouse (Fabric writes the lakehouse and workspace IDs into the notebook metadata) so it can run `MSCK REPAIR TABLE` on the Bronze tables
- Ask for approval before writing a new markdown file
- Never run `git commit` or `git push` on your own: wait for the user to ask explicitly, every time
- Use [OK], [FAIL], [SUCCESS] instead of emoji in output
- When something is unverified, say so explicitly; do not guess
- The Fabric UI and the IDE write to the same `main` branch: run "Update all" in Fabric Source control before editing there, run `git pull --rebase` before pushing, and never edit the same item on both sides at once
- Fabric re-serializes items it commits, so hand-written item files must match its format or Fabric shows them as changed: write `.platform` with no trailing newline, and prefer creating a new item in the Fabric UI, pulling it, then editing only its content in the IDE

## Project-specific notes
- Open-Meteo: CC BY 4.0, free tier is non-commercial only; attribution is required in the README
- PM2.5 is model data (CAMS, ~45 km), not station measurements; the README must say so
- Do not use WAQI/AQICN (terms forbid storing or archiving its data)
- Use English city names without diacritics for geocoding (`Hanoi`, not `Ha Noi` with diacritics)

## Status
- Phase: design done, workspace connected to Git, CI in place. Ticket 01 (34-City config and geocoding, `src/geocoding.py`) done; next is ticket 02 (lakehouses, done by the user in the Fabric UI), then ticket 03. See "Open items" in `docs/DESIGN.md`

## Agent skills

### Issue tracker

Issues and specs are local markdown files under `.scratch/<feature-slug>/` (gitignored). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
