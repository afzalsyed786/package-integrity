# PRD — Package Integrity Analyzer (PIA)

## Original problem statement
Build a production-quality cybersecurity app (PIA) that detects malicious modifications between published PyPI/npm packages and their GitHub source: safe download/extraction, source/tag discovery, file comparison with side-by-side diffs, explainable detection engine (install scripts, exec/eval, obfuscation, Base64, entropy, network, untracked files, source maps, missing tags), expected-difference recognition via manifests/source maps/structure, advanced analysis (source maps, JS bundles, bytecode without execution, semantic changes), optional AI explanations via Groq/OpenRouter (explain only), Clean/Suspicious/Inconclusive verdicts, watch mode, Streamlit dashboard, demo data (real + 3 labelled synthetic), CLI, modular adapters, tests, strict security, two-developer git workflow.

## User choices
Skipped clarifications → defaults: live React dashboard in preview + full Streamlit dashboard code; AI off until GROQ/OPENROUTER key added; PyPI + npm.

## Architecture
- `backend/pia/` standalone package: adapters (pypi, npm, synthetic), services (archive, http, repo_resolver, explanation, redaction, watch), engine (analyzer, comparison, expected, sourcemap, scoring), detectors (14 rules), database (SQLite local, Mongo hosted), cli, Streamlit app.py + pages/, sample_data, tests (43 pytest).
- `backend/server.py` FastAPI over same engine (jobs, watch loop thread, Mongo collections prefixed `pia_`).
- `frontend/` React dashboard: Overview, Analyze, Analysis detail (anomalies, file comparison diff, AI, provenance), Comparison/Anomalies/AI workspaces, Watchlist, Release History, Alerts, Demo Lab.
- Repo-level: CONTRIBUTING.md (two-dev flow), .github CODEOWNERS, PR template, CI workflow.

## Implemented (2026-06)
- All core requirements 1–17; real releases six 1.17.0, idna 3.10, ms 2.1.3 → Clean; synthetic colorfmt-synth, tinyhttp-synth, left-trim-synth → Suspicious.
- Testing agent iteration 1: backend 17/18, frontend all flows; fixed watch 500, prerelease/latest logic, diff/AI preview overflow, alert badge refresh.

## Backlog
- P1: Add AI key (Groq/OpenRouter) to enable live explanations; delete/archive analyses; job TTL/persistence.
- P1: Wheel-vs-sdist dual analysis; GitLab/Bitbucket resolvers as adapters.
- P2: Email/Slack alert delivery; Sigstore/PEP 740 attestation checks; SBOM export.
- Git: actual branches/PRs must be created on the user's GitHub (workflow documented; platform commits to main).
