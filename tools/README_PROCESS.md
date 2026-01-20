# Processing raw files -> processed MongoDB

This script (`tools/process_with_agno.py`) reads metadata documents inserted by `ingest_raw_to_mongo.py` and produces processed documents containing extracted text and metadata.

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements_process.txt
```

Notes:
- OCR: `pytesseract` requires the `tesseract` binary installed on your system (`brew install tesseract` on macOS). OCR is optional and disabled by default.
- `pdfminer.six` is used to extract PDF text; complex PDF layouts may not extract cleanly.

Agno integration
----------------
If you have an Agno HTTP endpoint available, set the environment variable `AGNO_ENDPOINT` or pass `--agno-endpoint` to the script. When provided, the processor will call Agno first and use its output (Markdown/text/images) if successful. If Agno is unavailable or returns an error, the script falls back to local extraction.

The script can also construct a `file_url` for Agno if you serve raw files through the fileserver — set `FILESERVER_BASE_URL` or pass `--fileserver-base`.

Quick run examples:

Process a small sample (100 docs):

```bash
python3 tools/process_with_agno.py --limit 100
```

Process all and attempt OCR on images:

```bash
python3 tools/process_with_agno.py --ocr
```

Configuration via environment variables:
- `MONGO_URI` (default `mongodb://localhost:27017`)
- `RAW_DB` / `RAW_COLLECTION` (defaults: `btp_rag.raw_files`)
- `PROCESSED_DB` / `PROCESSED_COLLECTION` (defaults: `btp_rag_processed.processed_docs`)
