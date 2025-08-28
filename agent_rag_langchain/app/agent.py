import logging
import time
import hashlib
from collections.abc import AsyncIterable
from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
import os
import requests
import tiktoken
from dotenv import load_dotenv
import jwt 
# Cấu hình logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Bộ nhớ hội thoại
memory = MemorySaver()
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
K = os.getenv("K")
SIMILARITY = os.getenv("SIMILARITY")

# Cấu hình API key cho Gemini
# GEMINI_API_KEY = "AIzaSyBB6YENUYxt5nkTDaAj_xO_usbunugUj8o"
# token_temp = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoia2hhbmhfMTIzIiwidXNlcm5hbWUiOiJraGFuaCIsInJvbGUiOiJ0ZWFjaGVyIiwiaWF0IjoxNzU1NTY2MzQ3LCJleHAiOjE3NTU2NTI3NDd9.Xzp15UyaDCEZQdccMI6GXWKdigiMbd31HonmTa2nCz0"
genai.configure(api_key=GEMINI_API_KEY)
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# Tokenizer cho model GPT-4o (tương tự Gemini)
encoding = tiktoken.encoding_for_model("gpt-4o")
data_types=[
        {
            "type":"admin",
            "permissions":["Cán bộ quản lý"],
            "description":"Quản lý hệ thống, có quyền truy cập đầy đủ vào tất cả các chức năng và dữ liệu."
        },
        {
            "type":"teacher",
            "permissions":["Cán bộ quản lý","Giáo viên"],
            "description":"Giáo viên và quản lý có quyền truy cập vào dữ liệu này"
        },
        {
            "type":"student",
            "permissions":["Cán bộ quản lý","Học sinh"],
            "description":"Học sinh có quyền truy cập vào dữ liệu của riêng mình."
        },
        {
            "type":"public",
            "permissions":["Cán bộ quản lý", "Giáo viên", "Học sinh"],
            "description":"Mọi người trong tổ chức đều được truy cập vào hệ thống."
        }
    ]
def count_tokens(text: str) -> int:
    """Đếm token trong đoạn text theo tokenizer GPT-4o"""
    return len(encoding.encode(text))

def truncate_to_max_tokens(text: str, max_tokens: int) -> str:
    tokens = encoding.encode(text)
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        text = encoding.decode(tokens)
    return text

class GetDataInput(BaseModel):
    query: str = Field(..., description="Câu hỏi của người dùng")
    token: str = Field(
        ..., description="Loại tài liệu cần tìm"
    )




def fetch_context_from_faiss(query: str,file_type:str, token: str, k: int, similarity: float, max_tokens: int = 8000 ) -> str:
    """Gọi API FAISS để lấy context dựa trên query và token.
    Loại bỏ chunk trùng hẳn, xử lý overlap và giới hạn tổng token context.
    """
    logger.info(f"[fetch_context_from_faiss] query='{query}', token='{token}', k={k}, similarity={similarity}, max_tokens={max_tokens}")
    url = os.getenv("URL_SEARCH")
    # url = "http://192.168.1.142:8000/documents/vector/search"
    try:
        payload = {
            "query": query,
            "file_type": file_type,
            "k": k,
            "similarity_threshold": similarity,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
        if response.status_code != 200:
            logger.error(f"[fetch_context_from_faiss] Lỗi API: {response.status_code} - {response.text}")
            return ""

        data = response.json()
        results = data.get("results", [])
        if not results:
            logger.info("[fetch_context_from_faiss] Không có kết quả phù hợp.")
            return ""
        # Loại bỏ chunk trùng hẳn dựa trên hash nội dung
        unique_chunks = []
        seen_hashes = set()
        for item in results:
            content = item.get("content", "").strip()
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(content)
# Xây dựng context với cấu trúc: Mỗi chunk được đánh số và phân cách bằng '---'
        context_parts = []
        total_tokens = 0
        for i, chunk in enumerate(unique_chunks, start=1):
            part = chunk  # Bỏ xử lý overlap tạm thời để đơn giản hóa

            part_tokens = count_tokens(part)

            if total_tokens + part_tokens > max_tokens:
                allowed_tokens = max_tokens - total_tokens
                tokens = encoding.encode(part)
                tokens = tokens[:allowed_tokens]
                part = encoding.decode(tokens)

            # Định dạng chunk với số thứ tự
            formatted_chunk = f"Chunk {i}:\n{part}\n---\n"
            chunk_tokens = count_tokens(formatted_chunk)  # Đếm token bao gồm định dạng

            if total_tokens + chunk_tokens > max_tokens:
                # Nếu vượt, cắt part thêm để fit định dạng
                remaining_tokens = max_tokens - total_tokens - count_tokens(f"Chunk {i}:\n\n---\n")
                if remaining_tokens > 0:
                    tokens = encoding.encode(part)
                    tokens = tokens[:remaining_tokens]
                    part = encoding.decode(tokens)
                    formatted_chunk = f"Chunk {i}:\n{part}\n---\n"
                    context_parts.append(formatted_chunk)
                break
            else:
                context_parts.append(formatted_chunk)
                total_tokens += chunk_tokens

        context = "".join(context_parts)
        logger.info(f"[fetch_context_from_faiss] Tổng token context trả về: {total_tokens}")
        return context

    except Exception as e:
        logger.error(f"[fetch_context_from_faiss] Exception: {e}")
        return ""

def create_prompt(context: str, query: str) -> str:
    """Tạo prompt từ context và query, trích xuất thông tin liên quan từ các chunk."""
    prompt_template = """
    Bạn là trợ lý chuyên trích xuất và tổng hợp thông tin từ tập tài liệu <DOCS> bạn phải làm theo các bước sau:
    1. Đọc toàn bộ <DOCS> và tìm mọi thông tin liên quan đến câu hỏi: {query}.
    2. **Chỉ** dùng thông tin có trong <DOCS> để trả lời. Nếu không đủ dữ liệu, trả lời không tìm thấy thông tin.
    3. Trả lời bằng **văn bản thuần** (plain text) — ưu tiên **bullet points** cho các ý chính, kèm 1 câu **Kết luận** ngắn cuối cùng.
    4. Không bịa, không phóng đại, câu trả lời phải ngắn, chính xác và trực quan.
    <DOCS>
    {context}
    </DOCS>
PHẢI Sau quá trình phân tích chuyên sâu, nếu thật sự không tìm thấy thông tin liên quan, hãy nói rõ ràng rằng không có thông tin nào được tìm thấy thì hãy dứt khoát trả lời 'Không biết'. Không được bịa câu trả lời nếu không đủ thông tin.
"""
    return prompt_template.format(context=context, query=query)

@tool(args_schema=GetDataInput)
def get_data(
    query: str,
    token: str
) -> str:
    """
    Hàm chính: lấy context, tạo prompt, gọi llm.invoke và trả kết quả.
    """
    logger.info(f"[get_data] START - query='{query}', token='{token}'")
    start_all = time.perf_counter()

    
    # lấy payload trong token
    payload= jwt.decode(token, options={"verify_signature": False})
    user_type = payload.get("user_type")
    types_for_user = [item["type"] for item in data_types if user_type in item["permissions"]]

        
    # Lấy context
    start_fetch = time.perf_counter()
    sum_conten=""
    for type in types_for_user:
        context = fetch_context_from_faiss(query,type,token,K,SIMILARITY)
        if not context:
            continue
        sum_conten+= "\n "+context
    end_fetch = time.perf_counter()
    logger.info(f"[get_data] fetch_context_from_faiss time = {end_fetch - start_fetch:.3f}s")

    if not sum_conten:
        logger.info(f"[get_data] Không tìm thấy thông tin phù hợp, kết thúc sau {time.perf_counter() - start_all:.3f}s")
        return "Không tìm thấy thông tin phù hợp."

    # Tạo prompt
    start_prompt = time.perf_counter()
    prompt_text = create_prompt(sum_conten, query)
    # prompt_text = truncate_to_max_tokens(prompt_text, max_input_tokens)
    logger.info(f"[get_data] Prompt cho LLM: {prompt_text}")
    input_token_count = count_tokens(prompt_text)
    logger.info(f"[get_data] Số tokens input: {input_token_count}")
    end_prompt = time.perf_counter()
    logger.info(f"[get_data] create_prompt & truncate time = {end_prompt - start_prompt:.3f}s")

    logger.info("[get_data] Gọi LLM với prompt đã tạo...")
    start_llm = time.perf_counter()
    try:
        answer = llm.invoke(prompt_text)
    except TypeError:
        # fallback: pass as dict input if the wrapper expects { "input": ... } or similar
        try:
            answer = llm.invoke({"input": prompt_text})
        except Exception as e:
            logger.exception("[get_data] llm.invoke fallback failed")
            answer = str(e)
    logger.info(f"[get_data] Kết quả trả về từ llm: {answer}")
    end_llm = time.perf_counter()
    logger.info(f"[get_data] llm.invoke time = {end_llm - start_llm:.3f}s")

    # Lấy text output từ answer
    output_text = getattr(answer, "content", str(answer))
    output_token_count = count_tokens(output_text)
    logger.info(f"[get_data] Số tokens output trả về: {output_token_count}")
    logger.info(f"[get_data] Kết quả trả về (tokens={output_token_count}): {output_text}")
    total_time = time.perf_counter() - start_all
    logger.info(f"[get_data] DONE - total_time={total_time:.3f}s")
    return output_text

# Khởi tạo LLM global
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

class ResponseFormat(BaseModel):
    status: Literal["input_required", "completed", "error"] = "completed"
    message: str

class RagSchoolInfo:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    SYSTEM_INSTRUCTION = (
        """
Bạn là AI chuyên cung cấp thông tin từ hàm get_data.
Trả về câu trả lời trực tiếp từ get_data mà không modify thêm.
"""
    )

    def __init__(self):
        t_init = time.perf_counter()
        logger.info("[RagSchoolInfo] Khởi tạo model...")
        #self.model = llm
        logger.info(f"[RagSchoolInfo] Khởi tạo xong - time={time.perf_counter()-t_init:.3f}s")

    def invoke(self, query, context_id, token="public"):
        start_total = time.perf_counter()
        logger.info(f"[invoke] START - query='{query}', token='{token}', context_id='{context_id}'")

        today_str = f"Today's date is {date.today().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser query: {query}\nFile type: {token}"
        start_get_data = time.perf_counter()
        # Gọi get_data như một tool với dictionary input
        input_data = {"query": augmented_query, "token": token}
        try:
            result = get_data.invoke({"query": augmented_query, "token": token})
        except TypeError:
            # Fallback: older langchain might accept positional dict call
            result = get_data({"query": augmented_query, "token": token})
        end_get_data = time.perf_counter()
        logger.info(f"[invoke] get_data done - time={end_get_data - start_get_data:.3f}s")

        total_elapsed = time.perf_counter() - start_total
        logger.info(f"[invoke] DONE - total_time={total_elapsed:.3f}s")
        return {
            "is_task_complete": True,
            "require_user_input": False,
            "content": result
        }

    async def stream(self, query, context_id, token) -> AsyncIterable[dict[str, Any]]:
        start_total = time.perf_counter()
        logger.info(f"[stream] START - query='{query}', token='{token}', context_id='{context_id}'")

        today_str = f"Today's date is {date.today().strftime('%Y-%m-%d')}."
        augmented_query = f"{today_str}\n\nUser query: {query}\nToken: {token}"

        logger.info("[stream] Đang tìm kiếm thông tin...")
        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Đang tìm kiếm thông tin...",
        }

        start_get_data = time.perf_counter()
        try:
            result =  get_data({"query": augmented_query, "token": token})
        except TypeError:
            # fallback to positional dict call if needed
            result =  get_data({"query": augmented_query, "token": token})
        end_get_data = time.perf_counter()
        logger.info(f"[stream] get_data done - time={end_get_data - start_get_data:.3f}s")

        logger.info("[stream] Đang xử lý dữ liệu...")
        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Đang xử lý dữ liệu...",
        }

        total_stream_time = time.perf_counter() - start_total
        logger.info(f"[stream] DONE - total_time={total_stream_time:.3f}s")
        yield {
            "is_task_complete": True,
            "require_user_input": False,
            "content": result
        }

    def get_agent_response(self, config):
        logger.warning("[get_agent_response] Phương thức này không sử dụng trong chế độ hiện tại")
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "Phương thức get_agent_response không áp dụng.",
        }

