# vn_weather_fabric

Data Engineer portfolio project on Microsoft Fabric (Trial), also used to prepare for the DP-700 exam. Time budget: 2 weeks.

## Docs (read before working)
- `docs/design.md`: agreed design (architecture, CI/CD, definition of done, open items)
- `docs/data_sources.md`: surveyed APIs, licenses, risks

## Architecture summary
- Sources: Open-Meteo (6 Vietnamese cities), provinces.open-api.vn, World Bank
- Batch: Bronze (Parquet) -> Silver, Gold (Delta); lakehouses `lh_bronze`, `lh_silver`, `lh_gold`
- Near-real-time: notebook polls every 2 hours -> Eventstream -> Eventhouse (micro-batch, not a true stream)
- A single workspace `de_vn_prod`, not connected to Git; the repo is the source of truth
- CI/CD: GitHub Actions, single `main` branch; push -> CI (ruff, pytest, gitleaks, validate) -> deploy with `fabric-cicd` (service principal + OIDC)

## Repo layout
- `fabric/`: workspace items
- `src/`: plain Python modules (API calls, transforms); notebooks only import and call them
- `tests/`: pytest tests for `src/`
- `.github/workflows/`: `ci.yml`, `deploy.yml`
- `docs/`: documentation, diagrams

## Conventions
- All markdown files and all code (identifiers, comments, docstrings, log messages, commit messages) in the repo must be in English
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- Fabric items use prefixes: `lh_`, `nb_`, `pl_`, `es_`, `eh_`
- Every function in `src/` must have a test

## Rules
- Never commit secrets, API keys or tokens, even in test files
- Do not hardcode environment-specific values (workspace IDs, etc.): use the `fabric-cicd` parameter file and GitHub variables. If hardcoding is unavoidable, ask for approval first and explain why
- Ask for approval before writing a new markdown file
- Use [OK], [FAIL], [SUCCESS] instead of emoji in output
- When something is unverified, say so explicitly; do not guess

## Project-specific notes
- Open-Meteo: CC BY 4.0, free tier is non-commercial only; attribution is required in the README
- PM2.5 is model data (CAMS, ~45 km), not station measurements; the README must say so
- Do not use WAQI/AQICN (terms forbid storing or archiving its data)

## Status
- Phase: design done, implementation not started. See "Open items" in `docs/design.md`
