#!/usr/bin/env python3
"""
Process raw files listed in MongoDB `raw_files` and create processed documents in a separate MongoDB collection.

Behavior:
- Connects to MongoDB and iterates over documents in the raw collection.
- For each file, attempts to extract text (HTML via BeautifulSoup, PDF via pdfminer.six, small text files via reading).
- Optionally mark images for OCR (requires external tesseract installation and `pytesseract`).
- Stores processed document in `processed_db.processed_docs` with fields:
  - `_id`: same as source raw _id prefixed (e.g. `proc_{rawid}`)
  - `source_id`, `file_path`, `mime`, `text`, `images`, `metadata`, `processed_at`

Usage:
  pip install -r tools/requirements_process.txt
  python tools/process_with_agno.py --limit 100

"""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import sys
import time
from datetime import datetime
from typing import Optional
import logging
import json

try:
    import requests
except Exception:
    requests = None

try:
    from pymongo import MongoClient
except Exception:
    print("Missing dependency 'pymongo'. Install with: pip install pymongo")
    raise

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from pdfminer.high_level import extract_text as extract_text_from_pdf
except Exception:
    extract_text_from_pdf = None

# configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
try:
    # pdfminer uses its own loggers; silence noisy color warnings like "Cannot set gray"
    logging.getLogger('pdfminer').setLevel(logging.ERROR)
    logging.getLogger('pdfminer.pdfinterp').setLevel(logging.ERROR)
except Exception:
    pass


def extract_text_from_html(path: str) -> Optional[str]:
    if BeautifulSoup is None:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n")
    except Exception:
        return None


def extract_text_from_file(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in {".txt", ".md", ".py", ".json", ".csv"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        if ext in {".html", ".htm"}:
            return extract_text_from_html(path)
        if ext == ".pdf":
            if extract_text_from_pdf is None:
                return None
            try:
                return extract_text_from_pdf(path)
            except Exception as e:
                # Log the PDF extraction error and return None so processing continues
                logging.warning("PDF extraction failed for %s: %s", path, e)
                return None
    except Exception:
        return None
    return None


def call_agno(agno_endpoint: str, file_url: Optional[str], file_path: str) -> Optional[dict]:
    logging.debug("Calling Agno HTTP endpoint %s for %s (file_url=%s)", agno_endpoint, file_path, file_url)
    if requests is None:
        logging.debug("requests not available, cannot call HTTP Agno")
        return None
    try:
        payload = {"file_path": file_path}
        if file_url:
            payload["file_url"] = file_url
        resp = requests.post(agno_endpoint, json=payload, timeout=60)
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                return None
        return None
    except Exception:
        return None


def call_agno_py(root_folder: str, rel_path: str) -> Optional[dict]:
    """Attempt to call an installed Agno Python API. Returns a dict-like result or None."""
    logging.debug("Attempting to import agno python package for %s", rel_path)
    try:
        import agno
        logging.debug("Imported agno module: %s", getattr(agno, "__version__", str(agno)))
    except Exception as e:
        logging.debug("Agno python import failed: %s", e)
        return None

    # try a couple of likely API names; adapt if your agno package differs
    full = os.path.join(root_folder, rel_path)
    try:
        # try common function names
        if hasattr(agno, "process_file"):
            logging.debug("Calling agno.process_file(%s)", full)
            res = agno.process_file(full)
            return res if isinstance(res, dict) else None
        if hasattr(agno, "process"):
            logging.debug("Calling agno.process(%s)", full)
            res = agno.process(full)
            return res if isinstance(res, dict) else None
        if hasattr(agno, "run"):
            logging.debug("Calling agno.run(%s)", full)
            # some libs expose run(...) returning a dict
            res = agno.run(full)
            return res if isinstance(res, dict) else None
    except Exception as e:
        logging.warning("Agno python processing failed for %s: %s", full, e)
        return None

    logging.debug("Agno installed but no supported API found")
    return None


def process_one(raw_doc: dict, root_folder: str, ocr: bool = False, agno_endpoint: Optional[str] = None, fileserver_base: Optional[str] = None) -> dict:
    rel = raw_doc.get("file_path")
    full = os.path.join(root_folder, rel)
    mime = raw_doc.get("mime") or mimetypes.guess_type(rel)[0] or "application/octet-stream"

    processed = {
        "source_id": raw_doc.get("_id"),
        "file_path": rel,
        "mime": mime,
        "metadata": {},
        "processed_at": datetime.utcnow(),
    }

    text = None
    images = []

    # If AGNO endpoint provided, try it first
    file_url = None
    if fileserver_base:
        file_url = fileserver_base.rstrip('/') + '/' + rel.replace(os.path.sep, '/')

    if agno_endpoint:
        agno_res = call_agno(agno_endpoint, file_url, rel)
        if agno_res:
            # prefer agno result fields
            if isinstance(agno_res, dict):
                if agno_res.get('markdown'):
                    processed['text'] = agno_res.get('markdown')
                elif agno_res.get('text'):
                    processed['text'] = agno_res.get('text')
                if agno_res.get('images'):
                    processed['images'] = agno_res.get('images')
                # include any extra metadata returned by Agno
                processed['metadata'].update(agno_res.get('metadata', {}))
                return processed

    if os.path.exists(full):
        try:
            text = extract_text_from_file(full)
        except Exception as e:
            logging.exception("Unexpected error extracting text from %s: %s", full, e)
            processed['extract_error'] = str(e)
            text = None

        if text:
            # basic normalization
            processed["text"] = text.strip()
        else:
            # if image mime, mark for OCR if requested
            if mime and mime.startswith("image/"):
                processed.setdefault("images", []).append(rel)
                if ocr:
                    # OCR requires pytesseract + tesseract binary; attempt if available
                    try:
                        import pytesseract
                        from PIL import Image

                        img = Image.open(full)
                        ocr_text = pytesseract.image_to_string(img)
                        processed["text"] = ocr_text.strip()
                    except Exception as oe:
                        logging.warning("OCR failed for %s: %s", full, oe)
                        processed.setdefault('extract_error', None)
                        processed['extract_error'] = processed.get('extract_error') or str(oe)
    else:
        processed["error"] = "file_not_found"

    return processed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
    p.add_argument("--raw-db", default=os.environ.get("RAW_DB", "btp_rag"))
    p.add_argument("--raw-collection", default=os.environ.get("RAW_COLLECTION", "raw_files"))
    p.add_argument("--processed-db", default=os.environ.get("PROCESSED_DB", "btp_rag_processed"))
    p.add_argument("--processed-collection", default=os.environ.get("PROCESSED_COLLECTION", "processed_docs"))
    p.add_argument("--root", default="./storage/raw_data", help="Root folder where raw files live")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--ocr", action="store_true", help="Attempt OCR on images (requires tesseract + pytesseract)")
    p.add_argument("--fileserver-base", default=os.environ.get("FILESERVER_BASE_URL", None), help="Optional base URL where raw files are served (for Agno)")
    p.add_argument("--agno-endpoint", default=os.environ.get("AGNO_ENDPOINT", None), help="Optional Agno HTTP endpoint to process files (preferred)")
    p.add_argument("--use-agno-py", action="store_true", help="If installed, use Agno Python API (tries agno.process_file/process/run)")
    p.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    client = MongoClient(args.mongo_uri)
    raw_coll = client[args.raw_db][args.raw_collection]
    proc_coll = client[args.processed_db][args.processed_collection]

    query = {}
    cursor = raw_coll.find(query)
    total = 0
    inserted = 0
    updated = 0

    for doc in cursor:
        total += 1
        processed = process_one(
            doc,
            args.root,
            ocr=args.ocr,
            agno_endpoint=args.agno_endpoint,
            fileserver_base=args.fileserver_base,
            # pass flag to try agno python API first
            agno_py=args.use_agno_py,
        )
        proc_id = f"proc_{doc.get('_id')}"
        processed_record = {"_id": proc_id, **processed}
        # idempotent upsert
        existing = proc_coll.find_one({"_id": proc_id})
        if existing:
            # preserve first_scraped_at if present
            if 'first_scraped_at' in existing:
                processed_record['first_scraped_at'] = existing['first_scraped_at']
            proc_coll.update_one({"_id": proc_id}, {"$set": processed_record})
            updated += 1
        else:
            # set first_scraped_at to now
            processed_record['first_scraped_at'] = datetime.utcnow()
            proc_coll.insert_one(processed_record)
            inserted += 1

        if args.limit and total >= args.limit:
            break

    print({"total": total, "inserted": inserted, "updated": updated})


if __name__ == "__main__":
    main()
