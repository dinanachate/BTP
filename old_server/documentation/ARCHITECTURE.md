# Server Architecture

## Overview

The server has been refactored into a modular architecture following best practices for FastAPI applications.

## Directory Structure

```
server/
├── main.py                         # Entry point with uvicorn
├── config_loader.py                # Configuration management
├── config.ini                      # Application settings
├── .env                            # Environment variables
│
├── app/                            # Main application package
│   ├── main.py                     # FastAPI app factory
│   │
│   ├── api/                        # API layer
│   │   └── routes/                 # Route modules
│   │       ├── rag.py             # RAG endpoints
│   │       └── course.py          # Course endpoints
│   │
│   ├── core/                       # Core components
│   │   └── auth.py                # Authentication & authorization
│   │
│   ├── models/                     # Data models
│   │   └── schemas.py             # Pydantic request/response models
│   │
│   └── services/                   # Business logic
│       ├── rag_service.py         # RAG streaming logic
│       └── course_service.py      # Course generation logic
│
├── rag_engine/                     # RAG implementation
│   └── rag.py                     # Core RAG query logic
│
├── retrivers/                      # Retrieval systems
│   └── hybrid_retriever.py        # BM25 + Vector hybrid search
│
└── course_build_agents/            # Multi-agent course generation
    ├── orchestrator.py
    ├── knowledge_retriever.py
    ├── knowledge_enhancer.py
    └── course_generator.py
```

## Module Responsibilities

### Entry Point (`main.py`)
- Starts uvicorn server with auto-reload
- Loads configuration
- Displays startup banner

### App Factory (`app/main.py`)
- Creates FastAPI application instance
- Configures CORS middleware
- Registers API routers
- Defines root endpoint

### API Routes (`app/api/routes/`)

#### RAG Router (`rag.py`)
- `GET /rag/models` - List available models
- `POST /rag/api/chat/completions` - Chat completions (streaming/non-streaming)

#### Course Router (`course.py`)
- `GET /course/models` - List course generation models
- `POST /course/api/chat/completions` - Generate course (streaming)
- `GET /course/download/{filename}` - Download course files

### Core Components (`app/core/`)

#### Authentication (`auth.py`)
- Bearer token validation
- User authentication dependency
- Token management from environment

### Models (`app/models/`)

#### Schemas (`schemas.py`)
- `ChatMessage` - Individual chat message
- `ChatRequest` - Chat completion request with options

### Services (`app/services/`)

#### RAG Service (`rag_service.py`)
- `stream_rag_response()` - Async generator for streaming RAG responses
- Integrates with rag_engine
- Formats sources and citations

#### Course Service (`course_service.py`)
- `stream_course_generation()` - Async generator for course generation
- Manages multi-agent orchestrator
- Provides heartbeat signals during long operations
- Generates download links

## Configuration Management

### Config Loader (`config_loader.py`)
Centralized configuration using:
- `config.ini` - Application parameters
- `.env` - Sensitive environment variables

### Settings Hierarchy
1. Environment variables (highest priority)
2. config.ini values
3. Default fallbacks

## Data Flow

### RAG Request Flow
```
Client Request
    ↓
rag.router (authentication)
    ↓
rag_service.stream_rag_response()
    ↓
rag_engine.query_rag()
    ↓
hybrid_retriever.retrieve()
    ↓
[Elasticsearch + Qdrant + Ollama]
    ↓
Stream response to client
```

### Course Generation Flow
```
Client Request
    ↓
course.router (authentication)
    ↓
course_service.stream_course_generation()
    ↓
MultiAgentOrchestratorWithLogging
    ↓
[Knowledge Retriever → Enhancer → Generator]
    ↓
Generate DOCX + Markdown
    ↓
Stream completion with download link
```

## Benefits of This Architecture

1. **Separation of Concerns**
   - Routes handle HTTP
   - Services contain business logic
   - Models define data contracts
   - Core provides shared utilities

2. **Testability**
   - Each module can be tested independently
   - Easy to mock dependencies
   - Clear interfaces between layers

3. **Maintainability**
   - Related code grouped together
   - Easy to locate specific functionality
   - Clear file naming conventions

4. **Scalability**
   - Easy to add new routes
   - Services can be extracted to microservices
   - Clear extension points

5. **Reusability**
   - Services can be used by multiple routes
   - Models shared across application
   - Core utilities available everywhere

## Running the Application

### Development (Local)
```bash
python main.py
```
Auto-reload enabled by default.

### Development (Docker)
```bash
docker-compose up -d
```
Volume mounted for hot-reloading.

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Adding New Features

### New API Endpoint
1. Create route in `app/api/routes/`
2. Add service logic in `app/services/`
3. Define schemas in `app/models/schemas.py`
4. Register router in `app/main.py`

### New Configuration
1. Add to `config.ini` (non-sensitive)
2. Add to `.env.example` (sensitive)
3. Update `config_loader.py`

## Legacy Components

The following are kept for backward compatibility:
- `rag_engine/` - Core RAG logic (used by services)
- `retrivers/` - Search implementations (used by rag_engine)
- `course_build_agents/` - Multi-agent system (used by course service)

These can be gradually refactored into the new structure as needed.
