"""PIA HTTP API — thin layer over the pia engine (the same engine used by the CLI and Streamlit dashboard)."""
import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from pia.adapters import AnalysisInputError  # noqa: E402
from pia.config import get_settings  # noqa: E402
from pia.database.mongo_store import MongoStore  # noqa: E402
from pia.detectors import default_detectors  # noqa: E402
from pia.engine.analyzer import Analyzer  # noqa: E402
from pia.services.explanation import ExplanationService  # noqa: E402
from pia.services.watch import WatchService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("pia.api")

settings = get_settings()
store = MongoStore(os.environ["MONGO_URL"], os.environ["DB_NAME"])
analyzer = Analyzer(settings, store=store)
explainer = ExplanationService(settings)
watch = WatchService(store, analyzer)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pia-analysis")
jobs: dict[str, dict] = {}
stop_event = threading.Event()

app = FastAPI(title="Package Integrity Analyzer API")
api = APIRouter(prefix="/api")


class AnalyzeRequest(BaseModel):
    ecosystem: str = Field(pattern="^(pypi|npm|synthetic)$")
    name: str = Field(min_length=1, max_length=214)
    version: str | None = Field(default=None, max_length=100)


class WatchRequest(BaseModel):
    ecosystem: str = Field(pattern="^(pypi|npm)$")
    name: str = Field(min_length=1, max_length=214)
    interval_minutes: int = Field(default=60, ge=5, le=1440)


def _run_job(job_id: str, req: AnalyzeRequest) -> None:
    job = jobs[job_id]

    def progress(stage, pct, msg):
        job.update(stage=stage, progress=pct, message=msg)

    try:
        result = analyzer.analyze(req.ecosystem, req.name, req.version, progress)
        job.update(status="completed", analysis_id=result["id"], verdict=result["verdict"], progress=100)
    except AnalysisInputError as e:
        job.update(status="failed", error=str(e))
    except Exception as e:  # surface unexpected engine failures to the client instead of hanging the job
        log.exception("analysis failed")
        job.update(status="failed", error=f"{type(e).__name__}: {e}")


@api.get("/health")
def health():
    return {"status": "ok", "engine": "pia", "detectors": [d.id for d in default_detectors()], "ai": explainer.status()}


@api.get("/ecosystems")
def ecosystems():
    return [{"id": k, "label": a.label} for k, a in analyzer.adapters.items()]


@api.get("/samples")
def samples():
    real = json.loads((settings.samples_dir / "real_releases.json").read_text())
    return {"synthetic": analyzer.adapters["synthetic"].samples(), "real": real}


@api.post("/analyses")
def start_analysis(req: AnalyzeRequest):
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"id": job_id, "status": "running", "stage": "queued", "progress": 0, "message": "Queued",
                    "request": req.model_dump(), "created_at": datetime.now(timezone.utc).isoformat()}
    executor.submit(_run_job, job_id, req)
    return jobs[job_id]


@api.get("/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "job not found")
    return jobs[job_id]


@api.get("/analyses")
def list_analyses(limit: int = Query(50, ge=1, le=500), ecosystem: str | None = None, package: str | None = None, verdict: str | None = None):
    return store.list_analyses(limit=limit, ecosystem=ecosystem, package=package, verdict=verdict)


@api.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    doc = store.get_analysis(analysis_id)
    if not doc:
        raise HTTPException(404, "analysis not found")
    return doc


@api.get("/analyses/{analysis_id}/files/{file_id}")
def file_detail(analysis_id: str, file_id: str):
    payload = store.get_file_detail(analysis_id, file_id)
    if payload is None:
        raise HTTPException(404, "no detail stored for this file")
    return payload


@api.get("/ai/status")
def ai_status():
    return explainer.status()


@api.get("/analyses/{analysis_id}/explain/preview")
def explain_preview(analysis_id: str):
    doc = get_analysis(analysis_id)
    return explainer.build_payload(doc)


@api.post("/analyses/{analysis_id}/explain")
def explain(analysis_id: str):
    doc = get_analysis(analysis_id)
    result = explainer.explain(doc)
    store.set_ai_explanation(analysis_id, result)
    return result


@api.get("/stats")
def stats():
    return store.stats()


@api.get("/watchlist")
def list_watch():
    return store.list_watch()


@api.post("/watchlist")
def add_watch(req: WatchRequest):
    try:
        return watch.add(req.ecosystem, req.name, req.interval_minutes)
    except AnalysisInputError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@api.delete("/watchlist/{watch_id}")
def remove_watch(watch_id: str):
    store.delete_watch(watch_id)
    return {"ok": True}


@api.post("/watchlist/{watch_id}/check")
def check_watch(watch_id: str):
    if not store.get_watch(watch_id):
        raise HTTPException(404, "watch item not found")
    executor.submit(watch.check, watch_id)
    return {"ok": True, "message": "Check started"}


@api.post("/watchlist/{watch_id}/rewind")
def rewind_watch(watch_id: str):
    version = watch.rewind(watch_id)
    if not version:
        raise HTTPException(404, "nothing to rewind")
    executor.submit(watch.check, watch_id)
    return {"ok": True, "rediscovering": version}


@api.get("/releases")
def releases(ecosystem: str | None = None, name: str | None = None, limit: int = Query(200, ge=1, le=1000)):
    return store.list_releases(ecosystem, name, limit)


@api.get("/alerts")
def alerts(limit: int = Query(100, ge=1, le=500), unread_only: bool = False):
    return store.list_alerts(limit, unread_only)


@api.post("/alerts/read-all")
def read_all():
    store.mark_all_alerts_read()
    return {"ok": True}


@api.post("/alerts/{alert_id}/read")
def read_alert(alert_id: str):
    store.mark_alert_read(alert_id)
    return {"ok": True}


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def start_watch_loop():
    threading.Thread(target=watch.run_forever, args=(stop_event, 60), daemon=True, name="pia-watch").start()


@app.on_event("shutdown")
def shutdown():
    stop_event.set()
    executor.shutdown(wait=False, cancel_futures=True)
