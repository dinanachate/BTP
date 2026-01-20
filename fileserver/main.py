from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

app = FastAPI(title="File Server", description="Download files by hash code")

# Directory where files are stored (can be overridden by environment variable)
FILES_DIR = os.getenv("FILES_DIR", "/app/files")


@app.get("/")
async def root():
    return {
        "message": "File Server API",
        "usage": "GET /download/{hash_code} to download a file"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/download/{hash_code}")
async def download_file(hash_code: str):
    """
    Download a file by its hash code (extension auto-detected).
    """

    # Sanitize
    hash_code = os.path.basename(hash_code)

    # Look for any file with this hash + any extension
    files_path = Path(FILES_DIR)
    matching_files = list(files_path.glob(f"{hash_code}.*"))

    if not matching_files:
        raise HTTPException(
            status_code=404,
            detail=f"No file found for hash '{hash_code}' (looked for {hash_code}.*)"
        )

    # If multiple results, choose the first one
    file_path = matching_files[0]

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream"
    )


@app.get("/list")
async def list_files():
    """
    List all available files in the directory.

    Returns:
        List of file hashes (filenames)
    """
    try:
        files_path = Path(FILES_DIR)
        if not files_path.exists():
            return {"files": [], "message": "Files directory does not exist"}

        files = [f.name for f in files_path.iterdir() if f.is_file()]
        return {
            "files": files,
            "count": len(files),
            "directory": FILES_DIR
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
