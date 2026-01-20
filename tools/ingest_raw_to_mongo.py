#!/usr/bin/env python3
"""
Ingest files from `storage/raw_data` into MongoDB collection `raw_files`.

Behavior:
- Walks the `storage/raw_data` directory recursively.
- For each file computes SHA256 and stores a document per file with metadata.
- Uses the SHA256 as `_id` so the script is idempotent (upserts on change).
- Optionally can store small text content for text-like files with `--store-content`.

Usage examples:
  pip install -r tools/requirements_ingest.txt
  python tools/ingest_raw_to_mongo.py --root ./storage/raw_data

"""
import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from typing import Optional

try:
    from pymongo import MongoClient
except Exception as e:
    print("Missing dependency 'pymongo'. Install with: pip install pymongo")
    raise


CHUNK_SIZE = 8192


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def maybe_extract_text(path: str) -> Optional[str]:
    # Very small heuristic: extract text for common small text files
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in {".txt", ".md", ".py", ".json", ".csv"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            return data
        if ext in {".html", ".htm"}:
            # simple fallback to strip tags if bs4 not installed
            try:
                from bs4 import BeautifulSoup

                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    html = f.read()
                soup = BeautifulSoup(html, "html.parser")
                return soup.get_text(separator="\n")
            except Exception:
                return None
    except Exception:
        return None
    return None


def process_file(client, db_name, coll_name, root, rel_path, store_content=False, fileserver_base=None):
    full_path = os.path.join(root, rel_path)
    try:
        stat = os.stat(full_path)
    except FileNotFoundError:
        return None

    file_hash = sha256_of_file(full_path)
    mime = guess_mime(full_path)
    doc = {
        "_id": file_hash,
        "file_path": rel_path,
        "size": stat.st_size,
        "mtime": datetime.utcfromtimestamp(stat.st_mtime),
        "created_at": datetime.utcnow(),
        "mime": mime,
        "source": "raw_data",
    }

    if fileserver_base:
        # ensure trailing slash
        doc["file_url"] = fileserver_base.rstrip("/") + "/" + rel_path.replace(os.path.sep, "/")

    if store_content:
        text = maybe_extract_text(full_path)
        if text:
            # trim if extremely large
            doc["content_preview"] = text[:50_000]

    db = client[db_name]
    coll = db[coll_name]

    # Upsert: if same _id exists but size or mtime changed, update metadata
    existing = coll.find_one({"_id": file_hash})
    if existing:
        # update fields that may change
        update_fields = {"size": doc["size"], "mtime": doc["mtime"], "mime": doc["mime"], "file_path": doc["file_path"], "updated_at": datetime.utcnow()}
        if "file_url" in doc:
            update_fields["file_url"] = doc["file_url"]
        if store_content and "content_preview" in doc:
            update_fields["content_preview"] = doc["content_preview"]
        coll.update_one({"_id": file_hash}, {"$set": update_fields})
        return {"action": "updated", "_id": file_hash}
    else:
        coll.insert_one(doc)
        return {"action": "inserted", "_id": file_hash}


def walk_and_ingest(args):
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"Root path not found: {root}")
        sys.exit(2)

    client = MongoClient(args.mongo_uri)
    db_name = args.db
    coll_name = args.collection

    total = 0
    inserted = 0
    updated = 0
    skipped = 0

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            total += 1
            try:
                res = process_file(client, db_name, coll_name, root, rel, store_content=args.store_content, fileserver_base=args.fileserver_base)
                if res is None:
                    skipped += 1
                elif res["action"] == "inserted":
                    inserted += 1
                elif res["action"] == "updated":
                    updated += 1
            except Exception as e:
                print(f"Error processing {rel}: {e}")

            if args.limit and total >= args.limit:
                break
        if args.limit and total >= args.limit:
            break

    print(json.dumps({"total_seen": total, "inserted": inserted, "updated": updated, "skipped": skipped}, default=str, indent=2))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="./storage/raw_data", help="Root folder with raw files (default ./storage/raw_data)")
    p.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", "mongodb://localhost:27017"), help="MongoDB URI")
    p.add_argument("--db", default=os.environ.get("RAW_DB", "btp_rag"), help="MongoDB database name")
    p.add_argument("--collection", default=os.environ.get("RAW_COLLECTION", "raw_files"), help="MongoDB collection name")
    p.add_argument("--store-content", action="store_true", help="Store small text content previews when possible")
    p.add_argument("--fileserver-base", default=os.environ.get("FILESERVER_BASE_URL", None), help="Optional base URL where files are served (fileserver)")
    p.add_argument("--limit", type=int, default=0, help="Limit number of files to ingest (for testing)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.limit == 0:
        args.limit = None
    start = time.time()
    walk_and_ingest(args)
    print(f"Done in {time.time()-start:.2f}s")


if __name__ == "__main__":
    main()
