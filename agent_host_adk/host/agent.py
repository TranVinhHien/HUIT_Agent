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
############# uv run uvicorn host:app --host 0.0.0.0 --port 8000 --reload #############
#############                                                             #############
#############                                                             #############
#######################################################################################
load_dotenv()
nest_asyncio.apply()
llm_model = os.getenv("LLM_MODEL")
db_url = os.getenv("DB_URL")

# MONGO_URI = "sqlite:///./sessions_management.db"  # hoặc mongodb+srv://... nếu Atlas
# MONGO_URI = "mysql+pymysql://root:12345@172.26.127.95/session_db"  # hoặc mongodb+srv://... nếu Atlas
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
            # artifact_service=InMemoryArtifactService(),
            session_service=session_service,
            # session_service=InMemorySessionService(),
            # memory_service=InMemoryMemoryService(),
        )
#python -m google.adk.api_server --session-service-type db --session-service-db-url "sqlite:///./sessions_management.db"
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
                # book_pickleball_court,
                # list_court_availabilities,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        lang= context.state.get("lang")
        user_info= context.state.get("user_info")
        text = f"""
            Vai trò: Bạn là một agent điều phối (orchestrator) của hệ thống Trường Đại học Công Thương TP.HCM (HUIT).
            Người dùng có thể là sinh viên, giảng viên, cán bộ quản lý hoặc người quan tâm đến trường.

            Nhiệm vụ:
            - Quan trọng nhất: chọn đúng agent trong <Available Agents> để xử lý yêu cầu, gọi qua hàm send_message.
            - Phải đọc kỹ phần <Available Agents> trước khi làm gì.
            - Phân tích câu hỏi, so khớp với mô tả/kỹ năng của agent => chọn agent phù hợp nhất.
            - Chỉ gọi agent có trong <Available Agents>. KHÔNG được tự tạo dữ liệu, KHÔNG đoán mò.
            - Khi đã chọn agent, gửi ngay yêu cầu bằng send_message và trả lại kết quả cho người dùng. KHÔNG xử lý hay viết lại nội dung trả về.
            - Nếu agent trả về rỗng, thử các agent khác trước khi thông báo "không tìm thấy thông tin".

            Yêu cầu trả lời (ngôn ngữ {lang}):
            - Ngắn gọn, rõ ràng, dễ hiểu.
            - Luôn ghi rõ agent nào đã được gọi.
            - Nếu tất cả agent đều không có dữ liệu, báo: "Không tìm thấy thông tin phù hợp trong hệ thống." kèm 1–2 gợi ý (ví dụ: cung cấp thêm từ khóa, bối cảnh).

            Quy tắc xử lý:
            1) Phân tích câu hỏi → xác định từ khóa.
            2) Đọc kỹ <Available Agents> → chọn agent phù hợp.
            3) Gọi send_message tới agent đó.
            4) Trả ngay kết quả agent trả về cho người dùng.không chế biến lại kết quả trả về.Không thay đổi bất cứ thông tin nào trong kết quả kể cả dấu".".

            Lưu ý: 
            - KHÔNG trả lời khi chưa gọi agent.
            - KHÔNG suy đoán ngoài dữ liệu.
            - Ưu tiên tốc độ: chọn agent nhanh, gọi ngay, trả kết quả thẳng.

           Ngày hiện tại (YYYY-MM-DD):** {datetime.now().strftime("%Y-%m-%d")}
            Thông tin người dùng:
            {user_info}
            <Available Agents>
            {self.agents}
            </Available Agents>
        """
        return text
       
    #Người dùng có quyền để truy cập tới các agent: {agent_can_use}. nếu yêu cầu của người dùng có liên quan tới agent  không nằm trong các agent có thể sử dụng thì trả về bạn không có quyền truy cập.



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
        
        # --- Cập nhật session.state với initial_state_delta ---
        # Đây là bước quan trọng để đảm bảo stateDelta được lưu vào session.state
        # và từ đó có thể truy cập qua tool_context.state
        if initial_state_delta:
            # Lấy trạng thái hiện tại dưới dạng một dict có thể sửa đổi.
            # Lưu ý: session.state là MappingProxyType, nên cần chuyển đổi nó trước.
            # ADK sẽ tự động chuyển đổi lại thành MappingProxyType khi lưu.
            current_session_state = dict(session.state)
            current_session_state.update(initial_state_delta) # Cập nhật state với delta
            
            # Lưu session đã cập nhật vào session service
            # Bạn chỉ cần truyền một dictionary thông thường vào update_session
            await self.runner.session_service.__update_session_state(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session.id,
                state=current_session_state, # Truyền dict đã sửa đổi vào đây
            )
            # Sau khi update_session, session object của bạn sẽ được làm mới
            # hoặc bạn có thể cần lấy lại session từ service nếu bạn muốn làm việc với state đã cập nhật ngay lập tức.
            # Tuy nhiên, trong ngữ cảnh này, runner sẽ đọc state mới.
        # --------------------------------------------------------

        async for event in self.runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=content,
            # QUAN TRỌNG: Truyền state_delta trực tiếp vào run_async
            # Điều này đảm bảo runner xử lý delta đúng cách và truyền vào tool_context
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
        #raise ValueError("\n\n\n\n token:",token,"\n\n\n\n")
        if not client:
            return("Agent {} không khả dụng".format(agent_name))
        # if True:
        #     raise NotImplementedError(f"\n\n\n\n\n\n\n token \n\n\n\n\n\n\n current_state:{tool_context.__dict__}  ")

        # Lấy user_role từ state của tool_context
        agent_can_use= tool_context.state._value.get("agent_use")
        lang= tool_context.state._value.get("lang")
        user_info= tool_context.state._value.get("user_info")
        
        if agent_name not in agent_can_use:
            return f"Bạn không đủ quyền để truy cập Agent {agent_name} để thực hiện yêu cầu."
        # Simplified task and context ID management
        state = tool_context.state
        print("state\n",state)
        task_id = state.get("task_id", str(uuid.uuid4()))
        context_id = state.get("context_id", str(uuid.uuid4()))
        message_id = str(uuid.uuid4())
        # message_from_host = f"""
        # Đây là người dùng có tên='{user_info.get('full_name', 'Người dùng không xác định')}', email:'{user_info.get('email', 'Không xác định')}', vai trò:'{user_info.get('role', 'Không xác định')}' và user_id='{user_info.get("user_ID","Không xác định")}'.
        # Họ đã gửi câu hỏi: {task}
        # bạn hãy trả lời câu hỏi này bằng tiếng {lang}
        # """
        # "user_info":{
        #     "full_name":"Hoàng Hữu Quân",
        #     "email":"gv1001@school.edu.vn",
        #     "user_ID":6,
        #     "role":"Giáo viên",
        #     "StudentCode":"gv1001"
        # },
        # token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc1NTU3NTY1MywianRpIjoiZGNmYTU1YjctOTVjOC00YWFlLWFhODgtZDc0MmZhOTgzNjM3IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjQiLCJuYmYiOjE3NTU1NzU2NTMsImV4cCI6MTc1NTU3OTI1MywidXNlcm5hbWUiOiJ0ZWFjaGVyMDAxIiwidXNlcl90eXBlIjoiR2lcdTAwZTFvIHZpXHUwMGVhbiIsImZ1bGxfbmFtZSI6IlRTLiBMXHUwMGVhIFZcdTAxMDNuIENcdTAxYjBcdTFlZGRuZyJ9.UJTjbO-gcyGUhLhiwfYtr4riNpxy-xft4QNoh7cl2W0"
        #token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc1NTU4OTcwMCwianRpIjoiNjY3MWY4YmQtYjY4NC00MTcyLTllMDUtYjIyODgxOGE1OGM0IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjYiLCJuYmYiOjE3NTU1ODk3MDAsImV4cCI6MTc1NTU5MzMwMCwidXNlcm5hbWUiOiJndjEwMDEiLCJ1c2VyX3R5cGUiOiJHaVx1MDBlMW8gdmlcdTAwZWFuIiwiZnVsbF9uYW1lIjoiSG9cdTAwZTBuZyBIXHUxZWVmdSBRdVx1MDBlMm4ifQ.Essu9GP0JVU5uV2RL_ZqghmxcUeQ04hBanzAehta_r8"
        print("message_from_host",task)
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
        return resp






# def _get_initialized_host_agent_sync():
#     """Synchronously creates and initializes the HostAgent."""

#     async def _async_main():
#         # Hardcoded URLs for the  agents
#         friend_agent_urls = [
#             "http://localhost:10004",  # T2SQL's Agent
#             "http://localhost:10002",  # RAG Shoppe Agent
#         ]
        
#         print("initializing host agent")
#         hosting_agent_instance = await HostAgent.create(
#             remote_agent_addresses=friend_agent_urls
#         )
#         print("HostAgent initialized")
#         return hosting_agent_instance.create_agent("Host_Agent")

#     try:
#         return asyncio.run(_async_main())
#     except RuntimeError as e:
#         if "asyncio.run() cannot be called from a running event loop" in str(e):
#             print(
#                 f"Warning: Could not initialize HostAgent with asyncio.run(): {e}. "
#                 "This can happen if an event loop is already running (e.g., in Jupyter). "
#                 "Consider initializing HostAgent within an async function in your application."
#             )
#         else:
#             raise


# # root_agent = _get_initialized_host_agent_sync()
