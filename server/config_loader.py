"""
Configuration loader for RAG server.
Loads settings from config.ini and environment variables.
"""
import os
import configparser
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the directory containing this file
BASE_DIR = Path(__file__).parent

# Load config.ini
config = configparser.ConfigParser()
config_path = BASE_DIR / 'config.ini'
config.read(config_path)


class Config:
    """Configuration class that combines config.ini and environment variables."""

    # Server Configuration
    SERVER_HOST = config.get('server', 'host', fallback='0.0.0.0')
    SERVER_PORT = config.getint('server', 'port', fallback=8080)
    LOG_LEVEL = config.get('server', 'log_level', fallback='info')

    # CORS Configuration
    CORS_ALLOW_ORIGINS = config.get('cors', 'allow_origins', fallback='*').split(',')
    CORS_ALLOW_CREDENTIALS = config.getboolean('cors', 'allow_credentials', fallback=True)
    CORS_ALLOW_METHODS = config.get('cors', 'allow_methods', fallback='*').split(',')
    CORS_ALLOW_HEADERS = config.get('cors', 'allow_headers', fallback='*').split(',')

    # RAG Configuration
    # Force Ollama model to mistral:latest
    RAG_MODEL = "mistral:latest"
    RAG_DEFAULT_TOP_K = config.getint('rag', 'default_top_k', fallback=30)
    RAG_CHUNK_SIZE = config.getint('rag', 'chunk_size', fallback=5)
    RAG_CHUNK_DELAY = config.getfloat('rag', 'chunk_delay', fallback=0.01)
    RAG_TEMPERATURE = config.getfloat('rag', 'temperature', fallback=0.7)

    # Hybrid Retriever Configuration
    EMBED_MODEL = config.get('hybrid_retriever', 'embed_model', fallback='embeddinggemma')
    BM25_WEIGHT = config.getfloat('hybrid_retriever', 'bm25_weight', fallback=0.5)
    VECTOR_WEIGHT = config.getfloat('hybrid_retriever', 'vector_weight', fallback=0.5)
    RETRIEVER_TOP_K = config.getint('hybrid_retriever', 'top_k', fallback=8)
    RETRIEVER_FINAL_K = config.getint('hybrid_retriever', 'final_k', fallback=5)

    # Course Generation Configuration
    COURSE_RETRIEVER_TOP_K = config.getint('course_generation', 'retriever_top_k', fallback=5)
    COURSE_ENHANCER_ITERATIONS = config.getint('course_generation', 'enhancer_iterations', fallback=3)
    COURSE_ENHANCER_TOP_K = config.getint('course_generation', 'enhancer_top_k', fallback=5)
    COURSE_OUTPUT_BASE_DIR = config.get('course_generation', 'output_base_dir', fallback='./course_outputs')
    COURSE_ENABLE_LOGGING = config.getboolean('course_generation', 'enable_logging', fallback=True)
    COURSE_HEARTBEAT_INTERVAL = config.getint('course_generation', 'heartbeat_interval', fallback=10)

    # Paths Configuration
    SPACY_MODEL = config.get('paths', 'spacy_model', fallback='fr_core_news_sm')

    # Download Configuration
    DOWNLOAD_ALLOWED_BASE_PATH = config.get('download', 'allowed_base_path', fallback='course_outputs')

    # Environment Variables (API URLs and sensitive data)
    ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
    ELASTICSEARCH_INDEX = os.getenv('ELASTICSEARCH_INDEX', 'btp_bm25_v2_index')

    QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
    QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'btp_rag_docs_v2')

    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

    SERVER_BASE_URL = os.getenv('SERVER_BASE_URL', f'http://localhost:{SERVER_PORT}')

    # Authentication Tokens
    @staticmethod
    def get_auth_tokens() -> Dict[str, Dict[str, str]]:
        """
        Parse AUTH_TOKENS from environment variable.
        Format: token1:user_id1:name1,token2:user_id2:name2
        """
        tokens_str = os.getenv('AUTH_TOKENS', 'dev-token-123:user_1:Developer')
        tokens = {}

        for token_entry in tokens_str.split(','):
            parts = token_entry.strip().split(':')
            if len(parts) == 3:
                token, user_id, name = parts
                tokens[token] = {"user_id": user_id, "name": name}

        return tokens


# Export singleton instance
settings = Config()
