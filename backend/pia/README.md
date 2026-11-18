# Package Integrity Analyzer (PIA)

PIA detects malicious modifications between packages **published on PyPI / npm** and their **original GitHub source**.
It downloads the exact artifact, extracts it safely, resolves the matching release tag, compares every file and
scores explainable findings into a deterministic verdict: **Clean**, **Suspicious** or **Inconclusive**.

> PIA never executes, imports, installs or builds package contents. Install hooks, setup.py and bytecode are parsed statically.

## Architecture

```
pia/
├── app.py, pages/            Streamlit dashboard (Overview, Analyze, File Comparison, Anomalies, AI, Watchlist, History, Alerts, Demo Lab)
├── cli.py, __main__.py       Command-line interface  (python -m pia …)
├── config/settings.py        Limits, timeouts, AI provider config (env driven)
├── adapters/                 Ecosystem adapters — the ONLY ecosystem-specific code
│   ├── base.py               EcosystemAdapter contract + ReleaseInfo
│   ├── pypi.py, npm.py       Registry metadata, download, tag candidates, metadata/manifest/hook conventions
│   └── synthetic.py          Builds the labelled synthetic lab samples at analysis time
├── services/
│   ├── archive.py            Safe archive inspector (traversal, symlink, hardlink, device, size, ratio, type checks)
│   ├── http.py               Retries + backoff, per-host rate limiting, ETag/TTL caching, size-capped downloads
│   ├── repo_resolver.py      GitHub discovery, `git ls-remote` tag resolution, codeload snapshot (no clone, no hooks)
│   ├── explanation.py        Optional Groq/OpenRouter explanation with redacted minimal snippets
│   ├── redaction.py          Secret / high-entropy masking
│   └── watch.py              Watch mode: polling, dedup, auto-analysis, alerts
├── engine/
│   ├── analyzer.py           Orchestrator (temp dirs + guaranteed cleanup)
│   ├── comparison.py         Path alignment (src/ layouts), hashing, normalised comparison
│   ├── expected.py           Expected-difference classifier (manifests, source maps, version stamps, transpiled output)
│   ├── sourcemap.py          VLQ decoding & source resolution
│   ├── scoring.py            Per-finding scores, correlation, noisy-OR aggregate, verdict rules
│   └── models.py, filetypes.py
├── detectors/                14 explainable rules (see below)
├── database/                 Store abstraction: SQLite (local) and MongoDB (hosted API)
├── sample_data/              3 SYNTHETIC tampered samples + real release list
└── tests/                    pytest unit + integration tests
```

The hosted web dashboard (React) talks to `backend/server.py`, a thin FastAPI layer over the **same engine**.

### Adding an ecosystem or build system
Implement `EcosystemAdapter` (resolve_release, list_versions, and optionally `classify_expected`,
`normalize_for_compare`, `install_hooks`, `build_manifest`, `entry_points`, `tag_candidates`) and register it in
`adapters/__init__.py::ADAPTER_CLASSES`. The comparison engine, detectors and scoring are unchanged.

## Detection rules
| Rule | What it looks at | Context used to avoid false positives |
|---|---|---|
| provenance | repo declared, tag match / missing / commit mismatch, digest verification, rejected archive members | tag-name variants, gitHead |
| install-hook | setup.py cmdclass, `.pth` imports, npm pre/post/install, implicit node-gyp | compared with repository hooks (baseline → info) |
| dynamic-exec | eval/exec/compile/marshal/pickle, `__builtins__` indirection, JS eval/new Function/vm | literal args = low; decoded args = critical; only package-introduced lines |
| process-exec / network-access / credential-access | subprocess, child_process, sockets, HTTP, env dumps, credential files | repository capability baseline downgrades; entry points / hook targets upgrade |
| encoded-payload | Base64 / hex literals decoded (and inflated) safely | data URIs, maps, lock files skipped; only code-like decoded content flagged |
| high-entropy | long high-entropy string literals | hashes, expected build outputs skipped |
| obfuscation | `_0x` identifiers, chr() assembly, fromCharCode, hex escapes, long lines | threshold scoring, minified/expected bundles exempt |
| untracked-file | package-only code / native binaries | expected classifier first |
| manifest-integrity | wheel RECORD hashes, sdist SOURCES.txt | build metadata exempt |
| bytecode | `.pyc` header + code object parsed via `marshal` (never executed) | compares names with compiled source |
| source-map | sourcesContent vs repo, missing sources, **unmapped bundle lines** (VLQ) | external/node_modules sources ignored |
| semantic-change | new sensitive imports / import-time calls / publish-time dependencies | AST diff against repository file |
| correlation | co-occurring behaviours in one file (e.g. network + credentials) | medium+ findings only |

Verdict: **Suspicious** if any high (≥0.7 confidence) / critical finding or aggregate risk ≥ 60;
**Inconclusive** if source is unavailable, the tag is missing (branch fallback), coverage < 50 %, a step failed, or risk is 30–59;
otherwise **Clean**. AI output is stored separately and never alters the verdict.

## Setup (local)
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r pia/requirements.txt
cp pia/.env.example pia/.env        # optional: add GROQ_API_KEY or OPENROUTER_API_KEY
```

### CLI
```bash
python -m pia analyze pypi six 1.17.0
python -m pia analyze npm ms 2.1.3 -v --json report.json
python -m pia samples && python -m pia analyze synthetic left-trim-synth -v
python -m pia watch add npm:ms --interval 60 && python -m pia watch run --once
python -m pia alerts
```
Exit codes: 0 Clean, 2 Inconclusive, 3 Suspicious, 1 error.

### Streamlit dashboard
```bash
cd backend/pia && streamlit run app.py
```

### Tests
```bash
cd backend/pia && pytest            # offline suite
pytest -m network                   # also analyses a real PyPI release
```

## Demo data
* **Synthetic (clearly labelled, inert, NOT real malware):** `colorfmt-synth` (install hook + Base64 exec),
  `tinyhttp-synth` (obfuscated import-time payload, sourceless `.pyc`, missing tag), `left-trim-synth`
  (unmapped bundle code, postinstall hook, path traversal + escaping symlink). Endpoints use `.invalid` / TEST-NET addresses.
* **Real:** `pypi:six@1.17.0`, `pypi:idna@3.10`, `npm:ms@2.1.3` — analysed live.

## Security model
All downloaded packages and repositories are untrusted: HTTPS only, size-capped downloads, digest verification,
safe extraction to temp dirs (files written 0644 with O_EXCL|O_NOFOLLOW), file count/size/ratio limits, timeouts,
`git ls-remote` with prompts/system config disabled, source snapshots via codeload tarballs (no clone, no hooks), and
guaranteed cleanup. AI requests contain at most six redacted snippets — never packages or secrets.

See `CONTRIBUTING.md` for the two-developer branch / PR workflow.
