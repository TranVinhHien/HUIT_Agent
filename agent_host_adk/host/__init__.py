from fastapi import FastAPI, HTTPException,Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .agent import HostAgent, session_service
import uuid
from google.genai import types
import asyncio  
import nest_asyncio  
from datetime import datetime
from .util import call_agent_async,check_token
from contextlib import asynccontextmanager
from  .call_api import get_agent_urls,get_available_agents,get_user_info
import os
from dotenv import load_dotenv
from fastapi.responses import FileResponse
import jwt
load_dotenv()
AGENT_NAME = "Host_Agent"
IMAGE_DIR = os.getenv("IMAGE_DIR","http://localhost:9000/image/")
friend_agent_urls = get_agent_urls()
# friend_agent_urls = [
#     # "http://192.168.1.163:3636"
#     "http://localhost:10001",
#     "http://localhost:10002",
#     "http://localhost:10003"
#     # "http://192.168.1.136:3636"
#     # "https://ai-agent.bitech.vn/rag"
# ]
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
    response: dict[str, Any] 
    session_id: str

class HealthResponse(BaseModel):
    status: str
    agent_name: str

class ErrorResponse(BaseModel):
    success: bool
    error: str

@app.post("/api/session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest,raw_request: Request):
    """API để tạo session mới"""
    try:
        # Tạo session_id mới nếu không được cung cấp
        session_id =  str(uuid.uuid4())
        app_name = AGENT_NAME
        lang = request.state.get("lang","VN") 
        # state = request.state or {}
        headers = raw_request.headers
        token = headers.get("Authorization", "").replace("Bearer ", "")
        # check token
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Authorization token is missing"
            )
        user_info = get_user_info(token)
        user_id = user_info.get("user_id")
        if not user_id or not user_info:
            raise HTTPException(
                status_code=400,
                detail="user_id and user_info are required"
            )
            
        agent_use = get_available_agents(token)
        if not agent_use:
            raise HTTPException(
                status_code=400,
                detail="No available agents"
            )
        # Tạo session
        new_session = await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state={
                "agent_use":agent_use,
                "user_info":user_info,
                "lang":lang
                },
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
    if check := check_token(token):
        raise HTTPException(
            status_code=401,
            detail=check
        )
    try:
        if not request.message:
            raise HTTPException(
                status_code=400,
                detail="Message is required"
            )
        user_id = jwt.decode(token, options={"verify_signature": False}).get("sub")
        session_id = request.session_id 
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id is required"
            )
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is error in token, please login again"
            )
        # Gửi tin nhắn cho agent và nhận phản hồi
        # response = await root_agent.process_message(request.message, session_id=session_id)
        response = await call_agent_async(host.runner, user_id, session_id, request.message, token)
        if not response:
            return SendMessageResponse(
                success=False,
                response="Lỗi hệ thống. Vui lòng thử lại",
                session_id=session_id
            )
        return SendMessageResponse(
            success=True,
            response=response,
            session_id=session_id
        )
        
    except Exception as e:
        return SendMessageResponse(
            success=True,
            response={"text": f"Lỗi hệ thống. Vui lòng thử lại: {str(e)}"},
            session_id=session_id
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
        if response.get("artifacts"):
            for art in response["artifacts"]:
                if "file_path" in art:
                    print("Saved at:", art["file_path"])
                    # Đọc file và return cho client (Flask/FastAPI: FileResponse, Django: FileResponse)
                elif "file_uri" in art:
                    print("File available at URI:", art["file_uri"])

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


@app.get("/image/{image_name}")
async def get_image(image_name: str):
    file_path = os.path.join(IMAGE_DIR, image_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path, media_type="image/png")


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
        
