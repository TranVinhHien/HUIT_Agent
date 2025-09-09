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
from call_api import get_agent_info
# from school_mcp_server import run_mcp_stdio_server
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
    host = "localhost"
    port = int(os.getenv("PORT", 10001))  # ép về int
    APP_NAME = "school_statistics_agent"
    agent_info = get_agent_info(APP_NAME)
    if not agent_info.get("url"):
        logger.error(f"Agent information for '{APP_NAME}' does not contain 'url'.")
        exit(1)
    try:
        # Check for API key only if Vertex AI is not configured
        if not os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "TRUE":
            if not os.getenv("GOOGLE_API_KEY"):
                raise MissingAPIKeyError(
                    "GOOGLE_API_KEY environment variable not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE."
                )

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
            description=agent_info.get("description","Agent chuyên xử lý và lấy dữ liệu để thực hiện thống kê từ hệ thống trường học HUIT thông qua MCP API.Mọi yêu cầu về việc lấy biểu đồ, thống kê, báo cáo đều được Agent này sử lý.Dữ liệu được trả về ở dạng Ảnh, để phục vụ trực quan hóa biểu đồ."),
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
