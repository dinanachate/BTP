"""
Course generation service
"""
import os
import json
import asyncio
import uuid
from datetime import datetime
from course_build_agents.orchestrator_with_logging import stream_course_generation_progress
from config_loader import settings


async def stream_course_generation(subject: str, model: str = "course-generator"):
    """
    Stream course generation with progress as reasoning_content

    Args:
        subject: Course subject/topic
        model: Model identifier

    Yields:
        str: Server-sent events formatted response chunks
    """
    message_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_timestamp = int(datetime.now().timestamp())

    config = {
        'retriever_top_k': settings.COURSE_RETRIEVER_TOP_K,
        'enhancer_iterations': settings.COURSE_ENHANCER_ITERATIONS,
        'enhancer_top_k': settings.COURSE_ENHANCER_TOP_K,
    }

    try:
        loop = asyncio.get_event_loop()

        # Track last heartbeat time
        last_heartbeat = asyncio.get_event_loop().time()
        heartbeat_interval = 10  # seconds

        # Run the streaming generator in executor and process updates
        async for update in async_stream_wrapper_with_heartbeat(
            loop, stream_course_generation_progress, subject, config,
            message_id, created_timestamp, model, heartbeat_interval
        ):
            if update['type'] == 'heartbeat':
                # Send heartbeat (empty content to maintain connection)
                heartbeat_chunk = {
                    "id": message_id,
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(heartbeat_chunk)}\n\n"

            elif update['type'] == 'progress':
                # Send progress as reasoning_content (appears in thinking box)
                progress_chunk = {
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
                yield f"data: {json.dumps(progress_chunk)}\n\n"

            elif update['type'] == 'complete':
                # Get final results
                results = update['results']
                course_markdown = results.get('course_markdown', '')

                # Add statistics summary at the end
                summary = (
                    f"\n\n---\n\n"
                    f"**Statistiques de génération :**\n"
                    f"- Nombre total de chapitres : {results['course_structure'].get('total_chapters', 0)}\n"
                    f"- Nombre total de sources : {results['final_source_count']}\n"
                    f"- Sources ajoutées : {results['sources_added']}\n"
                )

                final_content = course_markdown + summary

                # Stream the markdown content in chunks (like RAG does)
                chunk_size = settings.RAG_CHUNK_SIZE
                for i in range(0, len(final_content), chunk_size):
                    chunk = final_content[i:i+chunk_size]
                    chunk_data = {
                        "id": message_id,
                        "object": "chat.completion.chunk",
                        "created": created_timestamp,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    await asyncio.sleep(settings.RAG_CHUNK_DELAY)

        # Send finish signal
        final_chunk = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created_timestamp,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        error_chunk = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created_timestamp,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n\nErreur: {str(e)}"},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


async def async_stream_wrapper_with_heartbeat(loop, generator_func, *args, heartbeat_interval=10):
    """
    Wrapper to run a generator function and yield results asynchronously in real-time.
    Sends heartbeat messages every heartbeat_interval seconds to maintain connection.
    """
    import queue
    import threading
    import time

    result_queue = queue.Queue()

    def run_generator():
        try:
            # Extract the actual args (excluding heartbeat params)
            actual_args = args[:2]  # subject, config
            for item in generator_func(*actual_args):
                result_queue.put(('item', item))
        except Exception as e:
            result_queue.put(('error', e))
        finally:
            result_queue.put(('done', None))

    # Start generator in background thread
    thread = threading.Thread(target=run_generator, daemon=True)
    thread.start()

    # Track last heartbeat time
    last_heartbeat = time.time()

    # Yield items as they come
    while True:
        # Check if we need to send a heartbeat
        current_time = time.time()
        if current_time - last_heartbeat >= heartbeat_interval:
            yield {'type': 'heartbeat'}
            last_heartbeat = current_time

        # Non-blocking check with timeout
        try:
            # Use get_nowait in executor to avoid blocking
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

        except Exception as e:
            # Re-raise if it's not a queue timeout
            if not isinstance(e, queue.Empty):
                raise

    # Wait for thread to finish
    thread.join(timeout=1)
