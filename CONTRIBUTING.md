# Contributing — two-developer workflow

`main` is protected: **no direct commits**. Every change goes through a feature branch and a reviewed pull request.

## Roles
| Developer | Owns | Reviews |
|---|---|---|
| Dev A (engine) | `adapters/`, `services/`, `engine/`, `detectors/`, `tests/` | dashboard PRs |
| Dev B (product) | `app.py`, `pages/`, `frontend/`, `cli.py`, docs | engine PRs |

`CODEOWNERS` enforces the cross-review automatically.

## Branches (initial build plan)
1. `feature/architecture` – project skeleton, settings, adapter contract
2. `feature/safe-archive` – safe extractor + traversal/symlink tests
3. `feature/adapters-resolver` – PyPI / npm adapters, tag resolution
4. `feature/comparison-expected` – comparison engine, expected-difference classifier, source maps
5. `feature/detectors-scoring` – detection rules, correlation, verdicts, synthetic samples
6. `feature/storage-watch` – SQLite / Mongo stores, watch mode, alerts
7. `feature/cli` – command-line interface
8. `feature/dashboard` – Streamlit + web dashboard
9. `feature/ai-explanations` – Groq / OpenRouter explanation service

## Flow
```bash
git switch main && git pull
git switch -c feature/<topic>
# commit in small steps; run: cd backend/pia && pytest
git push -u origin feature/<topic>
gh pr create --base main --fill        # fills .github/pull_request_template.md
```
* The other developer reviews (at least 1 approval), CI (`.github/workflows/ci.yml`) must pass.
* Squash-merge; delete the branch. Rebase open branches on `main` after merges.
* Security-relevant changes (extractor, resolver, detectors) need a test demonstrating the threat and the fix.

## Branch protection (GitHub → Settings → Branches → `main`)
Require PR, require 1 approval, require code-owner review, require status check `tests`, disallow force pushes.
