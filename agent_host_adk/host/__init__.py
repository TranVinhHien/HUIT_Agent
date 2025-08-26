from fastapi import FastAPI, HTTPException,Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .agent import HostAgent, session_service
import uuid
from google.genai import types
import asyncio  
import nest_asyncio  
from datetime import datetime
from .util import call_agent_async
from contextlib import asynccontextmanager

AGENT_NAME = "Host_Agent"

friend_agent_urls = [
            # "http://localhost:10004",  # T2SQL's Agent 
            "http://192.168.1.124:10002",  # RAG HUIT Agent
            "http://192.168.1.115:3636",  # Executor's Agent
        ]
print("initializing host agent")
host = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global host, agents
    print("Initializing host agent...")
    host = await HostAgent.create(remote_agent_addresses=friend_agent_urls,name=AGENT_NAME)
    print("HostAgent initialized successfully")
    
    yield
    # Shutdown
    print("Shutting down host agent...")
    # Add cleanup code here if needed



print("HostAgent initialized")

app = FastAPI(
    title="Agent Host API",
    description="API for managing agent sessions and messages",
    version="1.0.0",
    lifespan=lifespan

)
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

# Pydantic models for request/response
class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    app_name: Optional[str] = None
    user_id: Optional[str] = None
    state: Optional[Dict[str, Any]] = {}

class CreateSessionResponse(BaseModel):
    success: bool
    session_id: str
    message: str

class SendMessageRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class SendMessageResponse(BaseModel):
    success: bool
    response: str
    session_id: str

class HealthResponse(BaseModel):
    status: str
    agent_name: str

class ErrorResponse(BaseModel):
    success: bool
    error: str

@app.post("/api/session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """API để tạo session mới"""
    try:
        # Tạo session_id mới nếu không được cung cấp
        session_id =  str(uuid.uuid4())
        app_name = AGENT_NAME
        user_id = request.user_id 
        state = request.state or {}
        
        # Tạo session
        new_session =await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
            session_id=session_id,
        )
        
        return CreateSessionResponse(
            success=True,
            session_id=session_id,
            message="Session created successfully",
            session_data=new_session
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}"
        )

@app.post("/api/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest,raw_request: Request):
    """API để gửi tin nhắn cho agent"""
    headers = raw_request.headers
    token = headers.get("Authorization", "").replace("Bearer ", "")
    try:
        if not request.message:
            raise HTTPException(
                status_code=400,
                detail="Message is required"
            )
        
        session_id = request.session_id 
        
        # Gửi tin nhắn cho agent và nhận phản hồi
        # response = await root_agent.process_message(request.message, session_id=session_id)
        response = await call_agent_async(host.runner, request.user_id, session_id, request.message, token)

        if not response:
            return "Lỗi hệ thống. vui lòng thử lại"
        return SendMessageResponse(
            success=True,
            response=response,
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )

@app.post("/api/message_stream", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest,raw_request: Request):
    """API để gửi tin nhắn cho agent"""
    headers = raw_request.headers
    token = headers.get("Authorization", "").replace("Bearer ", "")
    try:
        if not request.message:
            raise HTTPException(
                status_code=400,
                detail="Message is required"
            )
        
        session_id = request.session_id 
        
        # Gửi tin nhắn cho agent và nhận phản hồi
        # response = await root_agent.process_message(request.message, session_id=session_id)
        response = await call_agent_async(host.runner, request.user_id, session_id, request.message, token)

        if not response:
            return "Lỗi hệ thống. vui lòng thử lại"
        return SendMessageResponse(
            success=True,
            response=response,
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )



@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        agent_name=AGENT_NAME
    )

@app.get("/api/session/{session_id}/{user_id}")
async def get_session(session_id: str, user_id: str):
    """Lấy thông tin session"""
    try:
        session =await session_service.get_session(session_id=session_id,app_name=AGENT_NAME,user_id=user_id    )
        if not session:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "session_data": session
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session: {str(e)}"
        )

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Xóa session"""
    try:
        result = session_service.delete_session(session_id)
        
        return {
            "success": True,
            "message": f"Session {session_id} deleted successfully",
            "result": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )
        
