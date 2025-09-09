from pathlib import Path
import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

# from .prompt import root_instruction
from prompt import root_instruction

from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any, Optional

import json  # Để serialize token nếu cần
# Tính đường dẫn tuyệt đối đến MCP server script
PATH_TO_SCHOOL_MCP_SERVER = str((Path(__file__).parent / "school_mcp_server.py").resolve())
def before_tool_call(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
    token = tool_context.state.get('token')
    args["accessToken"] = str(token) if token else "CURRENT_ACCESS_TOKEN"  # Sử dụng token từ ToolContext hoặc placeholder

    return None  # Trả về None để ADK tiếp tục thực thi công cụ với args đã sửa đổi:contentReference[oaicite:4]{index=4}
def after_tool_callback(
    tool_context: ToolContext, args: dict, tool: dict | str, tool_response:dict
) -> dict | str:
    """
    This callback is executed after a tool runs.
    If the tool is 'read_file', it replaces the file content with a summary message.
    """
    # Nếu tool_response là str chứa JSON
    if isinstance(tool_response, str):
        try:
            tool_response = json.loads(tool_response)
        except Exception:
            pass  # giữ nguyên nếu không phải JSON

    return tool_response


# Khởi tạo agent quản lý trường học
def create_agent() -> LlmAgent:
    """Constructs the ADK agent for school_management_agent."""
    return LlmAgent(
        model="gemini-2.5-flash",
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
        before_tool_callback=before_tool_call ,
    )