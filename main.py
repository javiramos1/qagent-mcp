"""
FastAPI application for Domain-specific Q&A Agent with MCP integration
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Cookie, Response
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from qa_agent import DomainQAAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_env_with_fallback(key: str, default, converter=None):
    """Get environment variable with type conversion and fallback"""
    try:
        value = os.getenv(key, default)
        return converter(value) if converter and value != default else value
    except (ValueError, TypeError):
        logger.warning(f"Invalid {key}, using default: {default}")
        return default


def validate_client_config():
    """Validate required client configuration"""
    google_api_key = os.getenv("GOOGLE_API_KEY")
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

    if not google_api_key or google_api_key == "your_google_api_key_here":
        raise ValueError("GOOGLE_API_KEY environment variable is required for the client LLM")

    return google_api_key, mcp_server_url


def build_config() -> Dict[str, Any]:
    """Build client configuration from environment variables"""
    google_api_key, mcp_server_url = validate_client_config()

    return {
        # Client LLM configuration
        "google_api_key": google_api_key,
        "llm_temperature": get_env_with_fallback("LLM_TEMPERATURE", 0.1, float),
        "llm_max_tokens": get_env_with_fallback("LLM_MAX_TOKENS", 3000, int),
        "llm_timeout": get_env_with_fallback("LLM_TIMEOUT", 60, int),
        
        # Client request configuration
        "request_timeout": get_env_with_fallback("REQUEST_TIMEOUT", 30, int),
        
        # MCP server connection
        "mcp_server_url": mcp_server_url,
    }


def log_config(config: Dict[str, Any]):
    """Pretty print client configuration (excluding API keys)"""
    safe_config = {k: v for k, v in config.items() if not k.endswith("_api_key")}
    logger.info("Client configuration loaded:")
    for key, value in safe_config.items():
        logger.info(f"  {key}: {value}")


def create_config() -> Dict[str, Any]:
    """Create and validate complete configuration"""
    try:
        config = build_config()
        log_config(config)
        logger.info("Environment validation completed")
        return config
    except Exception as e:
        logger.error(f"Environment validation failed: {str(e)}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize session store on startup, cleanup on shutdown"""
    try:
        logger.info("Initializing Q&A Agent session store...")
        config = create_config()
        app.state.user_sessions = {}  # Store for per-session agent instances
        app.state.config = config
        logger.info("Session store initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize session store: {str(e)}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down session store...")
    if hasattr(app.state, "user_sessions"):
        # Close all MCP client connections before clearing sessions
        for session_id, agent in app.state.user_sessions.items():
            try:
                logger.info(f"Closing MCP client for session {session_id}")
                await agent.close()
            except Exception as e:
                logger.error(f"Error closing agent for session {session_id}: {e}")
        
        app.state.user_sessions.clear()
        logger.info("All sessions cleaned up successfully")


app = FastAPI(
    title="Domain Q&A Agent API",
    description="A Q&A agent that searches specific domains using Tavily and Langchain",
    version="1.0.0",
    lifespan=lifespan,
)

def get_or_create_agent(session_id: str) -> DomainQAAgent:
    """Get existing agent instance or create new one for session"""
    if not hasattr(app.state, "user_sessions"):
        raise HTTPException(status_code=500, detail="Session store not initialized")

    if session_id not in app.state.user_sessions:
        logger.info(f"Creating new agent instance for session {session_id}")
        app.state.user_sessions[session_id] = DomainQAAgent(config=app.state.config)

    return app.state.user_sessions[session_id]


class ChatRequest(BaseModel):
    message: str
    reset_memory: bool = False


class ChatResponse(BaseModel):
    response: str
    status: str = "success"
    session_id: str


@app.get("/health")
async def health_check():
    """Health check with session store status"""
    return {
        "message": "Domain Q&A Agent API is running",
        "status": "healthy",
        "version": "1.0.0",
        "active_sessions": (
            len(app.state.user_sessions) if hasattr(app.state, "user_sessions") else 0
        ),
    }


@app.post("/chat", response_model=ChatResponse, summary="Chat with Q&A Agent")
async def chat(
    request: ChatRequest, response: Response, session_id: str = Cookie(None)
):
    """Process user questions through the Q&A agent"""
    # Generate new session ID if none exists
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600,  # 1 hour session
        )

    logger.info(f"Processing chat request for session {session_id}")

    # Get or create agent instance for this session
    agent = get_or_create_agent(session_id)

    if request.reset_memory:
        agent.reset_memory()
        logger.info(f"Memory reset requested for session {session_id}")

    # Async Call to agent's chat method
    response_text = await agent.achat(request.message)
    logger.info(f"Successfully processed chat request for session {session_id}")

    return ChatResponse(response=response_text, status="success", session_id=session_id)


@app.post("/reset", summary="Reset conversation memory")
async def reset_memory(session_id: str = Cookie(None)):
    """Reset conversation memory for the current session"""
    if not session_id:
        raise HTTPException(status_code=400, detail="No active session")

    agent = get_or_create_agent(session_id)
    agent.reset_memory()
    logger.info(f"Memory reset via endpoint for session {session_id}")
    return {"message": "Conversation memory has been reset", "status": "success"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
