from pathlib import Path
import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

from prompt import root_instruction
from constants import GEMINI_MODEL # Giả sử bạn có file constants

from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any, Optional
from copy import deepcopy
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()
PATH_TO_SCHOOL_MCP_SERVER = str((Path(__file__).parent / "school_mcp_server.py").resolve())
def before_tool_call(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
    token = tool_context.state.get('token')
    print(f"[Callback] before_tool_call: tool={tool.name}, args={args}, token={token}")
    args["token"] = str(token) if token else "CURRENT_TOKEN" 

    return None 
import json

async def  after_tool_call(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) ->Dict | str:
    """Callback sau khi gọi tool - lưu response vào file"""
    
    if hasattr(tool_response, "model_dump"):
        raw_response = tool_response.model_dump()
    elif hasattr(tool_response, "content"):

        raw_response = tool_response.content
    elif isinstance(tool_response, dict):

        raw_response = tool_response
    else:

        print("[Callback] Không biết unwrap kiểu gì")
        return None
    if raw_response.get("isError",False):
        print("[Callback] Lỗi khi gọi tool")
        return None
    text_content = raw_response.get("content", [])[0].get("text", "")
    parsed_json = json.loads(text_content)
  
    chart_base64 = parsed_json.get("chart_base64", "")
    if not chart_base64:
        print("[Callback] Không tìm thấy chart_base64 trong tool_response")
        return None   # không có ảnh thì trả nguyên
    modified_response = deepcopy(parsed_json)
    tool_context.actions.skip_summarization=True

    return modified_response # Return the modified dictionary

def create_agent() -> LlmAgent:
    return LlmAgent(
        name="school_stats_agent",
        description="Một agent giúp người dùng tạo thống kê tương tác từ dữ liệu thống kê lớp học.",
        model=GEMINI_MODEL,
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
        after_tool_callback=after_tool_call,
    )

