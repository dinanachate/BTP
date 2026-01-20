# Ingestion (raw -> MongoDB)

This folder contains a small idempotent ingestion script to populate a "raw" collection with metadata about every file under `storage/raw_data`.

Quick steps

1. Install dependencies (prefer a virtualenv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements_ingest.txt
```

2. Ensure MongoDB is reachable (default `mongodb://localhost:27017`). If you use Docker Compose from the repository:

```bash
docker compose up -d mongodb
```

3. Run the ingestion (dry run / small sample):

```bash
python tools/ingest_raw_to_mongo.py --root ./storage/raw_data --limit 100
```

4. Run full ingestion:

```bash
python tools/ingest_raw_to_mongo.py --root ./storage/raw_data
```

Options
- `--store-content`: extract and store short text preview for text/html files (requires `beautifulsoup4` for HTML extraction).
- `--fileserver-base`: optional base URL where files are served so the document includes a `file_url` (e.g. `http://localhost:7700/files`).

Notes
- The script stores metadata and (optionally) short content previews, not full binary blobs. If you want to store binaries in MongoDB use GridFS or keep files on disk and reference their path (the latter is what this script does).
- Documents are upserted by SHA256 digest so rerunning is safe.
