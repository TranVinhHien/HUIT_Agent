### Question Answering using LLM
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import (SystemMessagePromptTemplate, 
                                    HumanMessagePromptTemplate,
                                    ChatPromptTemplate)



from langchain_core.output_parsers import StrOutputParser

# base_url = "http://localhost:11434"
# model = 'llama3.2:3b'

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key="AIzaSyAxoyLOBgIXA7j9Mpf_5k-RQCYoFagqU8U")


system = SystemMessagePromptTemplate.from_template("""
Bạn là một AI assistant chuyên viết câu lệnh SQL, **chỉ sử dụng SELECT**, và luôn tuân thủ quyền truy cập dựa trên user_id và vai trò (role) của người dùng.
Quy tắc nghiêm ngặt:
1. Chỉ được tạo câu lệnh SQL SELECT duy nhất. Phải kết thúc bằng dấu chấm phẩy `;`.
2. Nếu câu hỏi yêu cầu thêm/sửa/xoá dữ liệu (INSERT, UPDATE, DELETE) → Trả về đúng: **"You can't change data."**
3. Nếu không đủ thông tin để trả lời → Trả về đúng: **"I don't know"**
4. Khi truy vấn dữ liệu người dùng, **chỉ được dùng user_id**, tuyệt đối không dùng full_name hoặc email.
5. Quyền truy cập theo role:
   Bắt buộc tuân thủ quyền hạn:
      Học sinh/Giáo viên: Chỉ được truy vấn dữ liệu của chính họ (WHERE UserID=...).
      Cán bộ quản lý: Chỉ được xem dữ liệu người khác khi câu hỏi cung cấp ID cụ thể.
      Luôn dùng ID (UserID, StudentID...) trong mệnh đề WHERE, không bao giờ dùng tên hay email.
Chỉ tạo câu SQL đúng chuẩn, không có giải thích, không bình luận thêm.
""")

prompt = """
### Context:
{context}
### Question:
{question}
### Answer:
"""
prompt = HumanMessagePromptTemplate.from_template(prompt)

messages = [system, prompt]
template = ChatPromptTemplate(messages)

qna_chain = template | llm | StrOutputParser()

def ask_llm(context, question):
    return qna_chain.invoke({'context': context, 'question': question})