#!/usr/bin/env python3
"""Quick checks for processed/raw Mongo collections.

Usage:
  python3 tools/check_processed.py

This prints counts, sample documents, and any documents with extraction errors.
"""
from __future__ import annotations

import json
import os
from pymongo import MongoClient


def jprint(obj):
    print(json.dumps(obj, default=str, indent=2, ensure_ascii=False))


def main():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(uri)
    raw_db = os.environ.get("RAW_DB", "btp_rag")
    raw_coll = os.environ.get("RAW_COLLECTION", "raw_files")
    proc_db = os.environ.get("PROCESSED_DB", "btp_rag_processed")
    proc_coll = os.environ.get("PROCESSED_COLLECTION", "processed_docs")

    rc = client[raw_db][raw_coll]
    pc = client[proc_db][proc_coll]

    print("Mongo URI:", uri)
    print()

    counts = {
        "raw_count": rc.count_documents({}),
        "processed_count": pc.count_documents({}),
    }
    jprint(counts)

    print("\nOne sample processed doc:")
    sample = pc.find_one()
    if sample:
        jprint(sample)
    else:
        print("(no processed docs found)")

    print("\nProcessed docs with extract_error (limit 20):")
    errs = list(pc.find({"extract_error": {"$exists": True}}).limit(20))
    if errs:
        for e in errs:
            jprint({"_id": e.get("_id"), "file_path": e.get("file_path"), "extract_error": e.get("extract_error")})
    else:
        print("(no extract_error docs found)")

    print("\nRaw docs without a matching processed doc (limit 20):")
    missing = []
    cursor = rc.find({}).limit(1000)
    for r in cursor:
        proc_id = f"proc_{r.get('_id')}"
        if pc.count_documents({"_id": proc_id}) == 0:
            missing.append({"_id": r.get("_id"), "file_path": r.get("file_path")})
            if len(missing) >= 20:
                break
    if missing:
        jprint(missing)
    else:
        print("(no missing processed docs found in sample)")


if __name__ == '__main__':
    main()
