from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService 
from google.adk.events import Event
from datetime import datetime
import tempfile, os, mimetypes
from a2a.types import  FilePart
import base64
import uuid
import json
from dotenv import load_dotenv
load_dotenv()
import os
import jwt
IMAGE_URL = os.getenv("IMAGE_URL","http://localhost:9000/image/")
secret_key = os.getenv("SECRET_KEY","")
# ANSI color codes for terminal output
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

 
async def display_state(
    session_service: BaseSessionService, app_name: str, user_id: str, session_id: str, label: str = "Current State"
):
    """Display the current session state in a formatted way."""
    try:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # Format the output with clear sections
        print(f"\n{'-' * 10} {label} {'-' * 10}")

        # Handle the user name
        # user_name = await session.state.get("user_name", "Unknown")
        print(f"👤 User: {session}")



        print("-" * (22 + len(label)))
    except Exception as e:
        print(f"Error displaying state: {e}")

async def store_file_temporarily(list_file:list[dict[str:str]] ) -> str:
    """Store a File from base 64 to ."""
    try:
        image_urls = []
        for file in list_file: 
            # Decode về bytes get("file").get("bytes")
            image_bytes = base64.b64decode(file.get("file").get("bytes"))
            id = uuid.uuid4()
            # Lưu thành file PNG
            with open(f"host/imgs/baocao_{id}.png", "wb") as f:
                f.write(image_bytes)
            image_urls.append(IMAGE_URL + f"baocao_{id}.png")
        return image_urls
    except Exception as e:
        print(f"Error storing file temporarily: {e}")
        return None

async def process_agent_response(event: Event):
    """Process and display agent response events."""
    # Check for specific parts first
    has_specific_part = False
    if event.content and event.content.parts:
        for part in event.content.parts:
            if hasattr(part, "executable_code") and part.executable_code:
                # Access the actual code string via .code
                print(
                    f"  Debug: Agent generated code:\n```python\n{part.executable_code.code}\n```"
                )
                has_specific_part = True
            elif hasattr(part, "code_execution_result") and part.code_execution_result:
                # Access outcome and output correctly
                print(
                    f"  Debug: Code Execution Result: {part.code_execution_result.outcome} - Output:\n{part.code_execution_result.output}"
                )
                has_specific_part = True
            elif hasattr(part, "tool_response") and part.tool_response:
                # Print tool response information
                print(f"  Tool Response: {part.tool_response.output}")
                has_specific_part = True
            # Also print any text parts found in any event for debugging
            elif hasattr(part, "text") and part.text and not part.text.isspace():
                print(f"  Text: '{part.text.strip()}'")
    print(
                f"\n{Colors.BG_YELLOW}{Colors.WHITE}{Colors.BOLD}╔══ Event final ═════════════════════════════════════════{Colors.RESET}"
            )
    print(f"{Colors.CYAN}{Colors.BOLD}{event}{Colors.RESET}")
    print(
                f"{Colors.BG_YELLOW}{Colors.WHITE}{Colors.BOLD}╚═════════════════════════════════════════════════════════════{Colors.RESET}\n"
            )
    # Check for final response after specific parts
    final_response = None
    if event.is_final_response():

        # return file
        if part.function_response and part.function_response.response:
            # print(
            #     f"\n{Colors.BG_YELLOW}{Colors.WHITE}{Colors.BOLD}╔══ Event final ═════════════════════════════════════════{Colors.RESET}"
            # )
            # print(f"{Colors.CYAN}{Colors.BOLD}{part.function_response.response.get("result")}{Colors.RESET}")
            # print(
            #     f"{Colors.BG_YELLOW}{Colors.WHITE}{Colors.BOLD}╚═════════════════════════════════════════════════════════════{Colors.RESET}\n"
            # )
            if part.function_response.response.get("result")[0].get("kind") == "text":
                final_response = {
                    "text": part.function_response.response.get("result")[0].get("text","Lỗi không lấy được câu trả lời từ Agent")
                }
                return final_response
            if part.function_response.response.get("result")[0].get("kind") == "file":
                final_response = {
                    "result":part.function_response.response.get("result")
                }
                hh= {
                     "result":part.function_response.response.get("result")
                }
                return final_response
            # file_url=await store_file_temporarily(part.function_response.response.get("result"))
            # final_response= {
            #     "files":file_url,
            #     "text":""
            # }
        # return text agent
        if (
            event.content
            and event.content.parts
            and hasattr(event.content.parts[0], "text")
            and event.content.parts[0].text
        ):
            final_response = {
                "text":event.content.parts[0].text.strip()
            }
            # Use colors and formatting to make the final response stand out
            
            # print(
            #     f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}╔══ AGENT RESPONSE ═════════════════════════════════════════{Colors.RESET}"
            # )
            # print(f"{Colors.CYAN}{Colors.BOLD}{final_response}{Colors.RESET}")
            # print(
            #     f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}╚═════════════════════════════════════════════════════════════{Colors.RESET}\n"
            # )
        else:
            print(
                f"\n{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD}==> Final Agent Response: [No text content in final event]{Colors.RESET}\n"
            )
            return {"text":"Không nhận được kết quả trả về."}

    return final_response




async def call_agent_async(runner: Runner, user_id:str, session_id:str, query: str,token:str):
    
    """Call the agent asynchronously with the user's query."""
    content = types.Content(role="user", parts=[types.Part(text=query)])
    print(
        f"\n{Colors.BG_GREEN}{Colors.BLACK}{Colors.BOLD}--- Running Query: {query} ---{Colors.RESET}"
    )
    final_response_text = None
    state_delta: dict[str, str] = {
    "token": token,
}
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content,state_delta=state_delta
        ):
            # Process each event and get the final response if available
            response = await process_agent_response(event)
            final_response_text = response
    except Exception as e:
        print(f"Error during agent call: {e}")
    print("Agent call completed.")
    return final_response_text

def check_token(token: str) -> str|None:
    """Check if the provided token is valid."""
    
    # Implement your token validation logic here
    # For example, check against a database or an external service
    try:
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        return None
    except jwt.ExpiredSignatureError as e:
        return f"Token đã hết hạn: {e}"
    except jwt.InvalidTokenError as e:
        return "Token không hợp lệ"
