"""PIA command-line interface (independent of any dashboard)."""
import argparse
import json
import sys
import threading

from .adapters import AnalysisInputError
from .config import get_settings
from .database import get_store
from .engine.analyzer import Analyzer
from .services.explanation import ExplanationService
from .services.watch import WatchService

COLORS = {"Clean": "\033[32m", "Suspicious": "\033[31m", "Inconclusive": "\033[33m", "critical": "\033[31m", "high": "\033[91m",
          "medium": "\033[33m", "low": "\033[36m", "info": "\033[37m"}
RESET = "\033[0m"


def _c(text, key):
    return f"{COLORS.get(key, '')}{text}{RESET}" if sys.stdout.isatty() else text


def print_report(r: dict, verbose: bool = False) -> None:
    print(f"\n{'=' * 72}\n {r['ecosystem']}:{r['package']}@{r['version']}" + ("   [SYNTHETIC SAMPLE]" if r.get("synthetic") else ""))
    print(f" Verdict: {_c(r['verdict'], r['verdict'])}   Risk score: {r['risk_score']}/100   Coverage: {r.get('coverage', 0):.0%}")
    src = r.get("source", {})
    print(f" Source: {src.get('repo') or '-'}  ref={src.get('ref') or '-'}  tag status={src.get('status')}")
    s = r.get("summary", {})
    print(f" Files: identical={s.get('identical', 0)} modified={s.get('modified', 0)} package-only={s.get('package_only', 0)} "
          f"expected={s.get('expected', 0)} repo-only={s.get('repo_only', 0)}")
    print(" Reasons:")
    for reason in r.get("verdict_reasons", []):
        print(f"   - {reason}")
    print(f"{'-' * 72}\n Findings ({len(r.get('findings', []))}):")
    for f in r.get("findings", []):
        if f["severity"] == "info" and not verbose:
            continue
        loc = f"{f.get('file') or ''}{':' + str(f['line']) if f.get('line') else ''}"
        print(f"  [{_c(f['severity'].upper(), f['severity']):>8}] score={f['score']:>2} {f['title']}  {loc}")
        print(f"            {f['reason'][:180]}")
        if verbose and f.get("evidence"):
            for line in f["evidence"].splitlines()[:8]:
                print(f"            | {line[:150]}")
    if r.get("errors"):
        print(" Errors: " + "; ".join(r["errors"]))
    print("=" * 72)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pia", description="Package Integrity Analyzer — detect tampering between published packages and source")
    ap.add_argument("--db", help="SQLite database path (default: pia/pia.sqlite3)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyze a package release")
    a.add_argument("ecosystem", choices=["pypi", "npm", "synthetic"])
    a.add_argument("name")
    a.add_argument("version", nargs="?")
    a.add_argument("--json", dest="json_out", help="write the full JSON report to this file ('-' for stdout)")
    a.add_argument("--explain", action="store_true", help="request an AI explanation (needs GROQ_API_KEY / OPENROUTER_API_KEY)")
    a.add_argument("--no-save", action="store_true")
    a.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("samples", help="list synthetic tampered samples")
    sub.add_parser("history", help="list stored analyses")
    w = sub.add_parser("watch", help="watch mode")
    w.add_argument("action", choices=["add", "list", "remove", "check", "run"])
    w.add_argument("target", nargs="?", help="ecosystem:name")
    w.add_argument("--interval", type=int, default=60)
    w.add_argument("--once", action="store_true")
    sub.add_parser("alerts", help="show recent alerts")
    args = ap.parse_args(argv)

    store = get_store("sqlite", path=args.db) if args.db else get_store("sqlite")
    analyzer = Analyzer(get_settings(), store=None if getattr(args, "no_save", False) else store)
    try:
        if args.cmd == "analyze":
            def progress(stage, pct, msg):
                print(f"  [{pct:3d}%] {msg}", file=sys.stderr)
            r = analyzer.analyze(args.ecosystem, args.name, args.version, progress)
            if args.explain:
                r["ai_explanation"] = ExplanationService(get_settings()).explain(r)
                if not args.no_save:
                    store.set_ai_explanation(r["id"], r["ai_explanation"])
            if args.json_out == "-":
                print(json.dumps(r, indent=2, default=str))
            else:
                print_report(r, args.verbose)
                if args.json_out:
                    with open(args.json_out, "w") as fh:
                        json.dump(r, fh, indent=2, default=str)
                if r.get("ai_explanation"):
                    print("\nAI explanation (does not affect verdict):\n" + r["ai_explanation"]["text"])
            return {"Clean": 0, "Inconclusive": 2, "Suspicious": 3}[r["verdict"]]
        if args.cmd == "samples":
            for s in analyzer.adapters["synthetic"].samples():
                print(f"  {s['package']} {s['version']}  [{s['label']}]  {s['title']}")
            return 0
        if args.cmd == "history":
            for r in store.list_analyses(limit=50):
                print(f"  {r['created_at'][:19]}  {r['ecosystem']}:{r['package']}@{r['version']:<12} {r['verdict']:<13} risk={r['risk_score']}")
            return 0
        if args.cmd == "alerts":
            for al in store.list_alerts(limit=50):
                print(f"  {al['created_at'][:19]}  [{al['severity']:<8}] {al['title']} — {al.get('message', '')[:100]}")
            return 0
        watch = WatchService(store, Analyzer(get_settings(), store=store))
        if args.action == "list":
            for it in store.list_watch():
                print(f"  {it['id']:<30} every {it['interval_minutes']}m latest={it.get('latest_version')} last_checked={it.get('last_checked', '')[:19]}")
        elif args.action in ("add", "remove", "check"):
            if not args.target or ":" not in args.target:
                ap.error("target must be ecosystem:name")
            if args.action == "add":
                print(watch.add(*args.target.split(":", 1), interval_minutes=args.interval))
            elif args.action == "remove":
                store.delete_watch(args.target)
            else:
                print(json.dumps(watch.check(args.target), indent=2))
        else:
            if args.once:
                print(watch.run_due())
            else:
                print("Watching… Ctrl+C to stop")
                try:
                    watch.run_forever(threading.Event())
                except KeyboardInterrupt:
                    pass
        return 0
    except (AnalysisInputError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
