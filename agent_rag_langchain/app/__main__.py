import logging
import os
import sys

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.tasks import InMemoryPushNotifier
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from app.agent import RagSchoolInfo
from app.agent_executor import RagSchoolInfoExecutor
from dotenv import load_dotenv
from call_api import get_agent_info
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

def main():
    """Starts RagSchoolInfo Agent server."""
    APP_NAME = "RagSchoolInfo"
    agent_info = get_agent_info(APP_NAME)
    host = "localhost"   # localhost
    port = int(os.getenv("PORT",10002))
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")
        
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skills=[]
        for skill in  agent_info["skills"]:
            # print(skill)

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
            description=agent_info["description"],
            url=f"http://{host}:{port}/",
            version=agent_info["version"],
            defaultInputModes=RagSchoolInfo.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=RagSchoolInfo.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=skills,
        )

        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=RagSchoolInfoExecutor(),
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