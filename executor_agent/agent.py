from pathlib import Path
import sys
import asyncio

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

# from .prompt import root_instruction
from prompt import root_instruction

from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any, Optional
import json  # Để serialize token nếu cần
from dotenv import load_dotenv
import os
load_dotenv()
MODEL_NAME= os.getenv("MODEL_NAME")
# Tính đường dẫn tuyệt đối đến MCP server script
PATH_TO_SCHOOL_MCP_SERVER = str((Path(__file__).parent / "school_mcp_server.py").resolve())

def before_tool_call(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
    # Lấy token hiện tại từ ToolContext của ADK
    token = tool_context.state.get('token')
    # = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc1NTc5MjIxMSwianRpIjoiOTlkMjRjMjAtZDYzZC00NjdlLWE4NmItNWZiYzBmMDk4MzQ4IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjEzIiwibmJmIjoxNzU1NzkyMjExLCJleHAiOjE3NTU3OTU4MTEsInVzZXJuYW1lIjoiZ3YxMDA4IiwidXNlcl90eXBlIjoiR2lcdTAwZTFvIHZpXHUwMGVhbiIsImZ1bGxfbmFtZSI6IlRyXHUxZWE3biBUaFx1MWVjYiBQaFx1MDFiMFx1MDFhMW5nIn0.l5xtQ4iv4nlTy-wozeJwovjk4Kf-lUdPiJcwgip-LYk"
    # args["accessToken"] = str("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc1NTgzMjk0OCwianRpIjoiZGZhM2RjMzItOGQ5NC00NDBkLWEyNDItYzcwZDQzN2ExMTNkIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjciLCJuYmYiOjE3NTU4MzI5NDgsImV4cCI6MTc1NTgzNjU0OCwidXNlcm5hbWUiOiJndjEwMDIiLCJ1c2VyX3R5cGUiOiJHaVx1MDBlMW8gdmlcdTAwZWFuIiwiZnVsbF9uYW1lIjoiSHVcdTFlZjNuaCBUaFx1MWVjYiBRdVx1MWVmM25oIiwiZGVwYXJ0bWVudCI6Ik1hcmtldGluZyIsIm1ham9yIjpudWxsfQ.qr6VqIbUrYbRa6CATO3WgsPoVqKr3u4W1JX-W3DunHM") 
    args["accessToken"] = str(token) if token else "CURRENT_ACCESS_TOKEN"  # Sử dụng token từ ToolContext hoặc placeholder

    return None  # Trả về None để ADK tiếp tục thực thi công cụ với args đã sửa đổi:contentReference[oaicite:4]{index=4}
# Khởi tạo agent quản lý trường học
def create_agent() -> LlmAgent:
    """Constructs the ADK agent for school_management_agent."""
    return LlmAgent(
        model=MODEL_NAME,
        name="school_management_agent",
        description="An agent for managing school-related tasks.",
        instruction=root_instruction,
        tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,  # Sử dụng Python từ môi trường hiện tại
                    args=[PATH_TO_SCHOOL_MCP_SERVER],
                ),
                timeout=90.0  # Timeout cao hơn cho API calls
            )
        )
    ],
        before_tool_callback=before_tool_call 
    )


# root_agent =  LlmAgent(
#         model="gemini-2.5-pro",
#         name="school_management_agent",
#         instruction=root_instruction,
#         tools=[
#         MCPToolset(
#             connection_params=StdioConnectionParams(
#                 server_params=StdioServerParameters(
#                     command=sys.executable,  # Sử dụng Python từ môi trường hiện tại
#                     args=[PATH_TO_SCHOOL_MCP_SERVER],
#                 ),
#                 timeout=90.0  # Timeout cao hơn cho API calls
#             )
#         )
#     ],
#         before_tool_callback=before_tool_call 

#     )
