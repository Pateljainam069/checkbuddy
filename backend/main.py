"""FastAPI service: OCR, rule check, persist, return.

    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import ocr
import rules
import storage
import supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("checkbuddy")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(
    title="CheckBuddy",
    description="Legal Metrology (Packaged Commodities) Rules, 2011 — label compliance checks.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Widened for a deployed frontend later; local development needs only the list above.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(storage.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=storage.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def announce_backend() -> None:
    """Say which persistence backend is live — during a demo this must not be a guess."""
    active = storage.get_storage()
    log.info("Storage backend: %s", active.name)
    if not supabase_client.is_configured():
        log.info("Supabase credentials absent. Scans are being saved locally.")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "storage": storage.get_storage().name,
        "supabase_configured": supabase_client.is_configured(),
    }


@app.post("/scan")
async def scan(image: UploadFile = File(...), barcode: str | None = Form(None)) -> dict:
    """Run the full pipeline on one label photo."""
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image was empty.")

    suffix = os.path.splitext(image.filename or "")[1] or ".jpg"
    temp_path = os.path.join(tempfile.gettempdir(), f"checkbuddy-{uuid.uuid4().hex}{suffix}")
    with open(temp_path, "wb") as handle:
        handle.write(data)

    try:
        try:
            # OCR is synchronous and CPU-bound, and takes seconds. Calling it
            # directly inside an async handler blocks the event loop, which
            # freezes every other request for the duration — during a demo, one
            # scan in progress would hang the history page and stall the images
            # on it. The threadpool keeps the rest of the server responsive.
            ocr_results = await run_in_threadpool(ocr.run_ocr, temp_path)
        except Exception as exc:  # noqa: BLE001 - OCR failure must not 500 the demo
            log.exception("OCR failed")
            raise HTTPException(status_code=500, detail=f"Could not read the image: {exc}")

        report = rules.check_compliance(ocr_results)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    field_dicts = [f.to_dict() for f in report.fields]
    scan_id = None
    image_url = None

    # Persistence is best-effort by design: a storage failure must never swallow a
    # compliance result that has already been computed (SPEC_backend.md).
    try:
        active = storage.get_storage()
        filename = f"{uuid.uuid4().hex}{suffix}"
        image_url = active.upload_image(data, filename)
        row = storage.new_scan_row(barcode, image_url, report.ocr_raw_text, report.overall_status)
        active.save_scan(row, field_dicts)
        scan_id = row["id"]
    except Exception:  # noqa: BLE001
        log.exception("Could not save this scan. Returning the result anyway.")

    return {
        "scan_id": scan_id,
        "barcode": barcode or None,
        "image_url": image_url,
        "overall_status": report.overall_status,
        "fields": field_dicts,
        "ocr_raw_text": report.ocr_raw_text,
        "message": report.message,
    }


@app.get("/history")
def history() -> list[dict]:
    """The 50 most recent scans, newest first."""
    try:
        return storage.get_storage().list_scans()
    except Exception as exc:  # noqa: BLE001
        log.exception("Could not read history")
        raise HTTPException(status_code=503, detail=f"History is unavailable: {exc}")


@app.get("/scan/{scan_id}")
def scan_detail(scan_id: str) -> dict:
    """One scan with all of its per-field results."""
    try:
        record = storage.get_storage().get_scan(scan_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Could not read scan %s", scan_id)
        raise HTTPException(status_code=503, detail=f"Scan lookup failed: {exc}")

    if record is None:
        raise HTTPException(status_code=404, detail="No scan with that id.")
    return record
