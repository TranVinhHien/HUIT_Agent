import logging
import os
import sys

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from app.agent import RagSQLTool
from app.agent_executor import RagSQLToolExecutor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


def main():
    """Starts RagSQLTool Agent server."""
    host = "localhost"
    port = 10004
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")

        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id="RagSQLTool",
            name="truy ván dữ liệu như thông tin liên quan đến học sinh, giảng viên, môn học, lịch học.",
            description="Giúp truy vấn thông tin liên quan đến lịch học của sinh viên, mô học sinh viên đăng kí, thông tin về mô học và lốp học , thông tin giảng viên..",
            tags=["scheduling", "education","student_info","classroom", "database"],
            examples=["Cho tôi biết lịch học của tôi trong tuần này.", "Danh sách học sinh của tôi trong môn học ABC?"],
        )
        agent_card = AgentCard(
            name="RagSQLTool",
            description="Giúp truy vấn thông tin từ cơ sở dữ liệu liên quan đến học sinh, giảng viên, môn học, lịch học, môn học.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=RagSQLTool.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=RagSQLTool.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=RagSQLToolExecutor(),
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx_client),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
