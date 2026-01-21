"""
RAG service for streaming responses
"""
import json
import asyncio
import uuid
from datetime import datetime
from rag_engine.rag import stream_rag_with_thinking
from config_loader import settings

# --- FORCE le modèle Ollama exact pour éviter le 404 ---
DEFAULT_RAG_MODEL = "mistral:latest"


async def stream_rag_response(question: str, top_k: int = 5, model: str = None):
    """
    Stream RAG response with thinking from Ollama, then corrected final response

    Args:
        question: User question
        top_k: Number of top results to retrieve
        model: Model identifier (overridden by DEFAULT_RAG_MODEL)

    Yields:
        str: Server-sent events formatted response chunks
    """
    if model is None:
        model = DEFAULT_RAG_MODEL  # force mistral:latest

    try:
        message_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created_timestamp = int(datetime.now().timestamp())

        loop = asyncio.get_event_loop()

        # Use the async wrapper to stream in real-time
        async for update in async_rag_stream_wrapper(loop, stream_rag_with_thinking, question, top_k, model):
            if update['type'] == 'thinking':
                # Stream Ollama response as reasoning_content (thinking box)
                thinking_chunk = {
                    "id": message_id,
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "reasoning_content": update['content']
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(thinking_chunk)}\n\n"

            elif update['type'] == 'final':
                # Send final corrected response with sources
                answer_with_links = update['content']
                used_sources = update['sources']

                if used_sources:
                    sources_text = "\n\n**Sources:**\n"
                    for idx, source in enumerate(used_sources, 1):
                        sources_text += f"{idx}. [{source['title']}]({source['url']})\n"
                    answer_with_links += sources_text

                # Send complete final response
                final_content_chunk = {
                    "id": message_id,
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": answer_with_links},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_content_chunk)}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        error_chunk = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n\nError: {str(e)}"},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


async def async_rag_stream_wrapper(loop, generator_func, *args):
    """Wrapper to run RAG streaming generator in real-time."""
    import queue
    import threading

    result_queue = queue.Queue()

    def run_generator():
        try:
            for item in generator_func(*args):
                result_queue.put(('item', item))
        except Exception as e:
            result_queue.put(('error', e))
        finally:
            result_queue.put(('done', None))

    # Start generator in background thread
    thread = threading.Thread(target=run_generator, daemon=True)
    thread.start()

    # Yield items as they come
    while True:
        # Non-blocking check with timeout
        def get_with_timeout():
            try:
                return result_queue.get(timeout=0.1)
            except queue.Empty:
                return None

        result = await loop.run_in_executor(None, get_with_timeout)

        if result is None:
            # Queue was empty, continue waiting
            await asyncio.sleep(0.01)
            continue

        msg_type, data = result

        if msg_type == 'item':
            yield data
        elif msg_type == 'error':
            raise data
        elif msg_type == 'done':
            break

    # Wait for thread to finish
    thread.join(timeout=1)
