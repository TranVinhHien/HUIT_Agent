import random
from collections.abc import AsyncIterable
from datetime import date, datetime, timedelta
from typing import Any, List, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from app.scripts.llm import ask_llm
from langchain_core.runnables import chain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough 
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
# Hàm kiểm tra kết quả hợp lệ trước khi thực thi query
from langchain_core.runnables import RunnableLambda
memory = MemorySaver()

@chain
def get_correct_sql_query(input):
    context = input['context']
    question = input['question']

    intruction = """
        Use above context to fetch the correct SQL query for following question
        {}
        Do not enclose query in ```sql and do not write preamble and explanation.
        You MUST return only single SQL query.
    """.format(question)

    response = ask_llm(context=context, question=intruction)
    print("intruction:",intruction,"\n")
    print("response:",response)
    # Check if the response is not "I don't know"
    if  "I don't know" in response:
        return {"valid": False, "sql": None, "message": "I don't know how to answer this question."}
    elif  "You can't change data." in response:
        return {"valid": False, "sql": None, "message": "You can't change data."}
    else:
        sql = response.strip().removeprefix("```sql").removesuffix("```").strip()
        return {"valid": True, "sql": sql}


db = SQLDatabase.from_uri("mysql+pymysql://myuser:101204@172.26.127.95:3307/school_management")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key="AIzaSyAxoyLOBgIXA7j9Mpf_5k-RQCYoFagqU8U")

execute_query = QuerySQLDataBaseTool(db=db)
sql_query = create_sql_query_chain(llm, db)



def safe_execute(input):
    print("input: ", input)
    if isinstance(input, dict) and input.get("valid") and input.get("sql"):
        
        a= execute_query.invoke({"query": input["sql"]})
        print("a:", a)
        return a
    return input.get("message", "No valid SQL to execute.")

final_chain = (
    {'context': sql_query, 'question': RunnablePassthrough()}
    | get_correct_sql_query
    | RunnableLambda(safe_execute)
)

# generate code when user asks question call  final_chain.invoke({'question': question})
def generate_sql_query(question):
    return final_chain.invoke({'question': question})


@tool()
def get_data(query: str) -> str:
    """
    hàm này dùng để tạo câu truy vấn select để lấy thông tin liên quan đến cơ sở dữ liệu học vụ.
    """
    print("query:", query)
    response = final_chain.invoke({'question': query})
    print("response final_chain.invoke:", response)
    return response


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str


class RagSQLTool:
    """RagSQLTool - a specialized assistant for querying meeting room data."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    SYSTEM_INSTRUCTION = (
        """
        [VAI TRÒ]
        Bạn là AI chuyên truy vấn cơ sở dữ liệu (CSDL) học vụ.
        [NHIỆM VỤ CHÍNH]
        Phân tích câu hỏi của người dùng về: lịch học, sinh viên, giáo viên, lớp học, điểm số,lịch học, môn học.
        Gọi duy nhất hàm get_data(query) để lấy dữ liệu. query là câu hỏi của người dùng.
        Trả lời dưới dạng JSON theo định dạng yêu cầu.
        [QUY TẮC BẮT BUỘC]
        KHÔNG được tự viết lệnh SQL. Chỉ gọi hàm get_data.
        người dùng gửi câu truy vấn tới kèm theo thông tin của người dùng, bạn gửi tất cả thông tin tới hàm get_data.
        Hiểu logic CSDL:
        Lịch học/điểm của Sinh viên: Tên Sinh viên → Lớp đã đăng ký → Lịch học/Điểm.
        Lịch dạy của Giáo viên: Tên Giáo viên → Lớp phụ trách → Lịch học.
        **Định dạng phản hồi:**
        - Set response status to `input_required` nếu cần thêm thông tin từ người dùng.
        - Set response status to `error` nếu có lỗi khi xử lý truy vấn.
        - Set response status to `completed` nếu đã trả lời xong và đầy đủ.

        Hãy luôn tuân thủ đúng phạm vi và hướng dẫn trên trong mọi tình huống.
        """
    )

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        self.tools = [get_data]
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )

    def invoke(self, query, context_id):
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        print(f"Processing query: {query} with context_id: {context_id}")
        today_str = f"Today's date is {date.today().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser query: {query}"
        self.graph.invoke({"messages": [("user", augmented_query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query, context_id) -> AsyncIterable[dict[str, Any]]:
        today_str = f"Today's date is {date.today().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser query: {query}"
        inputs = {"messages": [("user", augmented_query)]}
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}

        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Checking Kaitlyn's availability...",
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Processing availability...",
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        if structured_response and isinstance(structured_response, ResponseFormat):
            if structured_response.status == "input_required":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            if structured_response.status == "error":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            if structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.message,
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": (
                "We are unable to process your request at the moment. "
                "Please try again."
            ),
        }
