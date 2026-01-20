"""
Course generation endpoints router
"""
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from datetime import datetime

from app.models.schemas import ChatRequest
from app.core.auth import get_current_user
from app.services.course_service import stream_course_generation
from config_loader import settings

router = APIRouter(prefix="/course", tags=["Course Generation"])


@router.get("/models")
async def course_models(current_user: dict = Depends(get_current_user)):
    """List available course generation models"""
    return {
        "object": "list",
        "data": [{
            "id": "course-generator",
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "custom"
        }]
    }


@router.post("/api/chat/completions")
async def course_chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Course generation endpoint

    Generates a complete course based on the subject provided
    """
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="Aucun message utilisateur trouvé")

    subject = user_messages[-1].content.strip()
    if not subject:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Veuillez fournir un sujet pour le cours."},
                "finish_reason": "stop"
            }]
        }

    return StreamingResponse(
        stream_course_generation(subject, request.model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/download/{filename:path}")
async def course_download(filename: str):
    """
    Download generated course files

    Args:
        filename: Path to the file to download

    Returns:
        FileResponse: The requested file
    """
    file_path = os.path.normpath(filename)
    print(file_path)

    if not file_path.startswith(settings.DOWNLOAD_ALLOWED_BASE_PATH):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "application/octet-stream"
    if file_path.endswith('.docx'):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif file_path.endswith('.txt') or file_path.endswith('.log'):
        media_type = "text/plain"
    elif file_path.endswith('.md'):
        media_type = "text/markdown"
    elif file_path.endswith('.json'):
        media_type = "application/json"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=os.path.basename(file_path)
    )
