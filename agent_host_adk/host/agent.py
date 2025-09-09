import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterable, List

import httpx
import nest_asyncio
from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from typing import Any, AsyncIterable, List, Optional  # Đảm bảo import MappingProxyType nếu bạn dùng Python 3.9 trở lên
from google.adk.sessions import DatabaseSessionService 
import os

from .remote_agent_connection import RemoteAgentConnections
#######################################################################################
#############                                                             #############
#############                                                             #############
#############                                                             #############
############# uv run uvicorn host:app --host 0.0.0.0 --port 9000 --reload #############
#############                                                             #############
#############                                                             #############
#######################################################################################
load_dotenv()
nest_asyncio.apply()
llm_model = os.getenv("LLM_MODEL")
db_url = os.getenv("DB_URL")

session_service = DatabaseSessionService(db_url=db_url) 
class HostAgent:
    """The Host agent."""

    def __init__(
        self,
        name_agent:str
    ):
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ""
        self._agent = self.create_agent(name_agent)
        self._user_id = "host_agent"
        self.runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            session_service=session_service,
        )
    async def _async_init_components(self, remote_agent_addresses: List[str]):
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(client, address)
                try:
                    
                    card = await card_resolver.get_agent_card()
                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(f"ERROR: Failed to get agent card from {address}: {e}")
                except Exception as e:
                    print(f"ERROR: Failed to initialize connection for {address}: {e}")
        # agent_info = [
        #     json.dumps({"name": card.name, "description": card.description, "skills": card_skill})
        # ]
        agent_info = [
            {
                "name": card.name,
                "description": card.description,
                "skills": [
                    {"name": skill.name, "description": skill.description}
                    for skill in card.skills
                ]
            }
            for card in self.cards.values()
        ]
        # agent_info = 
        
        print("agent_info:", "\n".join([str(info) for info in agent_info]) if agent_info else "No agent found")
        self.agents = "\n".join([str(info) for info in agent_info]) if agent_info else "No agent found"

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: List[str],
        name: str
    ):
        instance = HostAgent(name)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self,name) -> Agent:
        return Agent(
            model=llm_model,
            name=name,
            instruction=self.root_instruction,
            description="Bạn là một agent điều phối (orchestrator) chịu trách nhiệm điều hướng các yêu cầu của người dùng tới đúng các Agent khác để sử lý.",
            tools=[
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        lang= context.state.get("lang")
        user_info= context.state.get("user_info")
        text = f"""
            Vai trò: Bạn là một agent điều phối (orchestrator) của hệ thống Trường Đại học Công Thương TP.HCM (HUIT).
            Người dùng có thể là sinh viên, giảng viên, cán bộ quản lý hoặc người quan tâm đến trường.
            Nhiệm vụ:
            Nhiệm vụ duy nhất của bạn là chọn đúng agent trong <Available Agents> để xử lý yêu cầu, gọi qua hàm send_message.
            - Phải đọc kỹ phần <Available Agents> trước khi thực hiện gọi hàm send_message.
            - Chỉ gọi agent có trong <Available Agents>. Không tự trả lời câu hỏi.
            - Yêu cầu trả lời (ngôn ngữ {lang}):
            - Nếu tất cả agent sau quá trình gọi tới đều không có dữ liệu, báo: "Không tìm thấy thông tin phù hợp trong hệ thống.".

            Quy tắc xử lý:
            1) Phân tích câu hỏi → xác định từ khóa.
            2) Đọc kỹ <Available Agents> → chọn agent phù hợp.
            3) Gọi send_message tới agent đó.
            Lưu ý: 
            - KHÔNG trả lời khi chưa gọi agent.
            - Ưu tiên tốc độ: chọn agent nhanh, gọi ngay, trả kết quả thẳng.

           Ngày hiện tại (YYYY-MM-DD):** {datetime.now().strftime("%Y-%m-%d")}
            Thông tin người dùng:
            {user_info}
            <Available Agents>
            {self.agents}
            </Available Agents>
        """
        return text
    async def stream(
        self,
        query: str,
        session_id: str,
        # Thêm tham số mới để nhận stateDelta từ yêu cầu ban đầu
        initial_state_delta: Optional[dict[str, Any]] = None, 
    ) -> AsyncIterable[dict[str, Any]]:
        """
        Streams the agent's response to a given query.
        """
        session = await self.runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )
        content = types.Content(role="user", parts=[types.Part.from_text(text=query)])

        if session is None:
            session = await self.runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={}, # Khởi tạo state rỗng nếu là session mới
                session_id=session_id,
            )
        
        if initial_state_delta:
            current_session_state = dict(session.state)
            current_session_state.update(initial_state_delta) # Cập nhật state với delta
            
            await self.runner.session_service.__update_session_state(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session.id,
                state=current_session_state, # Truyền dict đã sửa đổi vào đây
            )
        # --------------------------------------------------------

        async for event in self.runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=content,
            state_delta=initial_state_delta 
        ):
            if event.is_final_response():
                response = ""
                if (
                    event.content
                    and event.content.parts
                    and event.content.parts[0].text
                ):
                    response = "\n".join(
                        [p.text for p in event.content.parts if p.text]
                    )
                yield {
                    "is_task_complete": True,
                    "content": response,
                }
            else:
                yield {
                    "is_task_complete": False,
                    "updates": "The host agent is thinking...",
                }




    async def send_message(self, agent_name: str, task: str, tool_context: ToolContext):
        """Sends a task to a remote agent."""
        if agent_name not in self.remote_agent_connections:
            return(f"Không {agent_name} tìm thấy agent phù hợp để thực hiện yêu cầu")
        client = self.remote_agent_connections[agent_name]
        token= tool_context.state["token"]
        if not client:
            return("Agent {} không khả dụng".format(agent_name))
        agent_can_use= tool_context.state._value.get("agent_use")
        lang= tool_context.state._value.get("lang")
        user_info= tool_context.state._value.get("user_info")
        # check token có invalid không
        # check agent có thể dùng
        if agent_name not in agent_can_use:
            return f"Bạn không đủ quyền để truy cập Agent {agent_name} để thực hiện yêu cầu."
        if token is None or token == "":
            return "Token không hợp lệ. Vui lòng đăng nhập lại."
        if user_info is None or user_info == "":
            return "Thông tin người dùng không hợp lệ. Vui lòng đăng nhập lại."
        state = tool_context.state
        task_id = state.get("task_id", str(uuid.uuid4()))
        context_id = state.get("context_id", str(uuid.uuid4()))
        message_id = str(uuid.uuid4())

        payload = {
            "message": {
                "role": "user",
                "metadata":{
                    "lang":lang,
                    "user_info": user_info,
                    "session":tool_context.state._value,
                    "token":token
                },
                "parts": [{"type": "text", "text": task}],
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
            },
        }
        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(message_request)

        if not isinstance(
            send_response.root, SendMessageSuccessResponse
        ) or not isinstance(send_response.root.result, Task):
            print("Received a non-success or non-task response. Cannot proceed.")
            return

        response_content = send_response.root.model_dump_json(exclude_none=True)
        json_content = json.loads(response_content)
        resp = []
        if json_content.get("result", {}).get("artifacts"):
            for artifact in json_content["result"]["artifacts"]:
                if artifact.get("parts"):
                    resp.extend(artifact["parts"])
                    tool_context.actions.skip_summarization = True
                    for part in artifact["parts"]:
                        if part.get("file"):
                            tool_context.actions.skip_summarization = True
                            pass
        return resp