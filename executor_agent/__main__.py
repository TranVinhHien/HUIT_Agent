import logging
import os
import sys
import asyncio

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent import create_agent
from agent_executor import ExecutorAgentExecutor
from dotenv import load_dotenv
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import os

from call_api import get_agent_info
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

    pass


def main():
    """Starts the agent server."""
    # Ensure Windows can spawn subprocesses from asyncio (needed for MCP stdio client)
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    host = "0.0.0.0"
    port =int( os.getenv("PORT", 10003))
    APP_NAME = "AgentExecutor"
    agent_info = get_agent_info(APP_NAME)
    if not agent_info:
        logger.error(f"Agent information for '{APP_NAME}' not found.")
        exit(1)
    
    try:
        # Check for API key only if Vertex AI is not configured
        if not os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "TRUE":
            if not os.getenv("GOOGLE_API_KEY"):
                raise MissingAPIKeyError(
                    "GOOGLE_API_KEY environment variable not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE."
                )
        # capabilities = AgentCapabilities(streaming=True)
        # skill = AgentSkill(
        #     id="mcp_call_api_skill",
        #     name="Call MCP",
        #     description="""gọi MCP để thực hiện các API của hệ thống trường học HUIT.Server MCP này là một hệ thống quản lý trường học toàn diện, cung cấp các API được phân quyền theo ba vai trò chính: Học sinh, Giáo viên, và Quản lý, cùng với các chức năng xác thực cơ bản.
        #     MCP server có chức năng đăng nhập vào hệ thống để sử dụng các chức năng.
        #     Đối với người dùng cuối, hệ thống cho phép học sinh xem lịch học, thông báo và đăng ký lớp; giáo viên có thể quản lý lịch dạy và danh sách học sinh của mình.
        #     Ở cấp độ quản trị, vai trò Quản lý có toàn quyền CRUD (tạo, đọc, cập nhật, xóa) đối với các thực thể chính như lớp học, học sinh, và giáo viên. Chức năng này còn bao gồm việc phân công giảng dạy và truy xuất báo cáo tổng quan toàn hệ thống, cung cấp khả năng điều hành và giám sát đầy đủ.
        #     """,
        #     tags=["Học vụ", "sinh viên","giáo viên"],
        #     examples=["Xem lịch học của tôi kì này?","đăng kí giúp tôi học phần môn.","Lịch giảng dạy của tôi kì này."],
        # )
        # agent_card = AgentCard(
        #     name="AgentExecutor",
        #     description="Một agent chuyên để thực thi tất cả các API của hệ thống trường học HUIT bằng phương thức MCP.Ví dụ 1 só API như xem lịch học, đăng kí học phần,Xem lịch dạy...",
        #     url=f"http://{host}:{port}/",
        #     version="1.0.0",
        #     defaultInputModes=["text/plain"],
        #     defaultOutputModes=["text/plain"],
        #     capabilities=capabilities,
        #     skills=[skill],
        # )
        capabilities = AgentCapabilities(streaming=True)
        skills=[]
        for skill in  agent_info["skills"]:
            item =AgentSkill(
                id=skill["id"],
                name=skill["name"],
                description=skill["description"],
                tags=skill["tags"],
                examples=skill["examples"],
            )
            skills.append(item)
    
        agent_card = AgentCard(
            name=APP_NAME,
            description=agent_info.get("description","Một agent chuyên để thực thi tất cả các API của hệ thống trường học HUIT bằng phương thức MCP.Ví dụ 1 só API như xem lịch học, đăng kí học phần,Xem lịch dạy..."),
            url=f"http://{host}:{port}/",
            version=agent_info.get("version","1.0.0"),
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text", "image/png","images/*"],
            capabilities=capabilities,
            skills=skills,
        )
        adk_agent = create_agent()
        runner = Runner(
            app_name=agent_card.name,
            agent=adk_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        agent_executor = ExecutorAgentExecutor(runner)

        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        uvicorn.run(server.build(), host=host, port=port)
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()

# from .agent import root_agent