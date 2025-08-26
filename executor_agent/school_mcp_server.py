
import asyncio
import json
import logging
import os
import aiohttp
from typing import Dict, Any, Optional

from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from google.adk.tools.tool_context import ToolContext

from mcp.server.stdio import stdio_server
import sys
load_dotenv()

# --- Logging Setup ---

# --- Logging Setup ---
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "school_mcp_server_activity.log")

# SỬA LẠI ĐOẠN NÀY
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)


# Lấy logger gốc
logger = logging.getLogger() 

# Tạo một FileHandler với encoding UTF-8
# Đây là dòng quan trọng nhất
file_handler = logging.FileHandler(LOG_FILE_PATH, mode="w", encoding="utf-8")

# Tạo một formatter và gán nó cho handler
formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
file_handler.setFormatter(formatter)

# Thêm handler đã cấu hình vào logger gốc
# Nếu có handler cũ, có thể cần xóa đi trước logger.handlers.clear()
logger.addHandler(file_handler)

# API Configuration
API_BASE_URL = "https://ai-api.bitech.vn/api"
# API_BASE_URL = "http://localhost:5000/api"

ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc1NTc4NTk4NywianRpIjoiMDIxOGMwNWEtY2RhMy00NjMxLThlNjYtOThmZjUzOTZmNzYwIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjI3IiwibmJmIjoxNzU1Nzg1OTg3LCJleHAiOjE3NTU3ODk1ODcsInVzZXJuYW1lIjoiZ3YxMDIyIiwidXNlcl90eXBlIjoiR2lcdTAwZTFvIHZpXHUwMGVhbiIsImZ1bGxfbmFtZSI6IlBoXHUxZWExbSBNXHUxZWY5IEdpYW5nIn0.j2-w8yVawseEnOpq3RV9Z5-e6Q4_Lx1xPKnsOSThn64"
# Sửa đổi hàm này để không cần tool_context
async def make_api_request(
    method: str, 
    endpoint: str, 
    *,  # Dấu sao quan trọng ở đây
    data: Dict = None, 
    auth_required: bool = True,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """Thực hiện HTTP request đến API, sử dụng global ACCESS_TOKEN."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    # print(f"Token trong get_profile: {token}")
    # logging.debug(f"Thực hiện request: {method.upper()} {token} với auth_required={auth_required}")
    token = token.strip('"')
    token=token.replace('"','')
    if isinstance(token, bytes):
            token = token.decode("utf-8", errors="ignore")
    access_token = token
    if auth_required:
        if not token:
            logging.warning(f"Yêu cầu xác thực cho endpoint '{endpoint}' nhưng không tìm thấy token.")
            return {"success": False, "message": "Lỗi xác thực: Bạn chưa đăng nhập hoặc phiên đã hết hạn. Vui lòng sử dụng tool 'login'."}
        

        headers["Authorization"] = f"Bearer {token}"
    
    logging.debug(f"Thực hiện request: {method.upper()} {url} với auth_required={auth_required}")
    
    async with aiohttp.ClientSession() as session:
        try:
            # (Phần còn lại của hàm giữ nguyên)
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method.upper() == "POST":
                async with session.post(url, headers=headers, json=data) as response:
                    return await response.json()
            elif method.upper() == "PUT":
                async with session.put(url, headers=headers, json=data) as response:
                    return await response.json()
        except Exception as e:
            logging.error(f"Lỗi khi gọi API tới {url}: {e}", exc_info=True)
            return {"success": False, "message": f"Lỗi kết nối API: {str(e)}"}

# --- MCP Server Setup ---
logging.info("Tạo MCP Server cho hệ thống quản lý trường học...")
mcp = FastMCP("school-management-mcp-server")

# --- Authentication Functions ---

@mcp.tool()
async def get_profile(accessToken:str) -> str:
    """
    Lấy thông tin hồ sơ của người dùng hiện tại đã đăng nhập.

    - Dùng khi cần xem chi tiết thông tin cá nhân.
    
    """
    # logging.debug(f"Server nhận token: {token}")
    # import inspect
    # frame = inspect.currentframe()
    # token = frame.f_locals.get("accessToken")


    logging.info("Tạo MCP Server cho hệ thống quản lý trường học... Token=%s", accessToken)
    logging.info("get_profile: accessToken=%s", type(accessToken))

    if not accessToken:
        return json.dumps({"error": "Không có token"}, ensure_ascii=False)
    result = await make_api_request("GET", "/auth/profile", auth_required=True,token=accessToken)
    with open("profile_result.txt", "w", encoding="utf-8") as f:
        f.write(json.dumps(accessToken, ensure_ascii=False, indent=2))

    return json.dumps(result, ensure_ascii=False)

# --- Student Functions ---
@mcp.tool()
async def get_student_notifications(accessToken:str) -> str:
    """
    Xem danh sách thông báo dành riêng cho học sinh.

    - Dùng cho học sinh đã đăng nhập.

    """

    result = await make_api_request("GET", "/student/notifications", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_student_schedule(accessToken:str) -> str:
    """
    Xem lịch học cá nhân của học sinh.

    - Dùng khi học sinh cần xem thời khóa biểu.

    """

    
    result = await make_api_request("GET", "/student/schedule", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def enroll_class(class_id: int,accessToken:str) -> str:
    """
    Đăng ký tham gia một lớp học.

    - Dùng cho học sinh muốn ghi danh vào lớp.
    """

    enroll_data = {"class_id": class_id}
    result = await make_api_request("POST", "/student/enroll", data=enroll_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def cancel_class(class_id: int,accessToken:str) -> str:
    """
    Hủy đăng ký/Hủy tham gia một lớp học.

    - Dùng cho học sinh muốn hủy đăng ký một lớp học đã ghi danh.

    """

    enroll_data = {"class_id": class_id}
    result = await make_api_request("POST", "/student/cancel-enrollment", data=enroll_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_available_classes(accessToken:str) -> str:
    """
    Xem danh sách lớp học còn trống có thể đăng ký.

    - Dùng khi học sinh muốn tìm lớp để tham gia.

    """

    
    result = await make_api_request("GET", "/student/available-classes", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

# --- Teacher Functions ---
@mcp.tool()
async def get_teaching_schedule(accessToken:str) -> str:
    """
    Xem lịch giảng dạy của giáo viên.

    - Dùng khi giáo viên cần xem các buổi dạy của mình.
    """
    
    result = await make_api_request("GET", "/teacher/teaching-schedule", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_teacher_notifications(accessToken:str) -> str:
    """Xem thông báo dành cho giáo viên."""

    
    result = await make_api_request("GET", "/teacher/notifications", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_teacher_students(accessToken:str) -> str:
    """
    Xem danh sách sinh viên thuộc lớp giáo viên đang phụ trách.
    """

    
    result = await make_api_request("GET", "/teacher/students", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_teacher_courses(accessToken:str) -> str:
    """
    Xem danh sách khóa học mà giáo viên được phân công dạy.
    
    Hàm này lấy danh sách khóa học, bao gồm chi tiết như tên khóa, lớp học liên quan, v.v.
    Chỉ dành cho người dùng có vai trò giáo viên và đã đăng nhập (auth_required=True).
    
    Tham số:
    - Không có tham số đầu vào cụ thể.
    
    Kết quả:
    - Danh sách khóa học dưới dạng dictionary hoặc list nếu thành công.
    - Thông báo lỗi nếu thất bại hoặc không có quyền.
    """
    
    result = await make_api_request("GET", "/teacher/courses", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

# --- Manager Functions ---
@mcp.tool()
async def get_system_overview(accessToken:str) -> str:
    """
    Xem thống kê tổng quan của hệ thống (dành cho quản lý).

    - Yêu cầu vai trò: Quản lý.
    - Output: Thống kê số lượng người dùng, lớp học, khóa học, giáo viên, sinh viên.
    """

    if not ACCESS_TOKEN:
        return json.dumps({"success": False, "message": "Vui lòng đăng nhập trước"}, ensure_ascii=False)
    
    result = await make_api_request("GET", "/manager/overview", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def create_class(course_id: int, semester: str, academic_year: str, 
                      max_capacity: int, start_date: str, end_date: str,accessToken:str) -> str:

    """
    Tạo mới một lớp học trong hệ thống (dành cho quản lý).

    """

    
    class_data = {
        "course_id": course_id,
        "semester": semester,
        "academic_year": academic_year,
        "max_capacity": max_capacity,
        "start_date": start_date,
        "end_date": end_date
    }
    
    result = await make_api_request("POST", "/manager/create-class" , data=class_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def update_class(class_id: int, accessToken:str,semester: str = "", academic_year: str = "",
                      max_capacity: int = 0, start_date: str = "", 
                      end_date: str = "", status: str = "",) -> str:
    """
    Cập nhật thông tin một lớp học.

    """
    update_data = {}
    if semester: update_data["semester"] = semester
    if academic_year: update_data["academic_year"] = academic_year
    if max_capacity: update_data["max_capacity"] = max_capacity
    if start_date: update_data["start_date"] = start_date
    if end_date: update_data["end_date"] = end_date
    if status: update_data["status"] = status
    
    result = await make_api_request("PUT", f"/manager/update-class/{class_id}", data=update_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def add_student(username: str, password: str, full_name: str, 
                     email: str, phone_number: str, major: str,accessToken:str) -> str:
    """
    Thêm sinh viên mới vào hệ thống.

    """
    student_data = {
        "username": username,
        "password": password,
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number,
        "major": major
    }
    
    result = await make_api_request("POST", "/manager/add-student", data=student_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def update_student(accessToken:str,student_id: int=0, full_name: str = "", email: str = "",
                        phone_number: str = "", major: str = "") -> str:
    """
    Cập nhật thông tin sinh viên.

    """
    update_data = {}
    if full_name: update_data["full_name"] = full_name
    if email: update_data["email"] = email
    if phone_number: update_data["phone_number"] = phone_number
    if major: update_data["major"] = major
    
    result = await make_api_request("PUT", f"/manager/update-student/{student_id}", data=update_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def add_teacher(accessToken:str,username: str, password: str, full_name: str, 
                     email: str, phone_number: str, department: str) -> str:
    """
    Thêm giáo viên mới vào hệ thống.
    - Mục đích: Quản lý thêm giáo viên.

    """
    teacher_data = {
        "username": username,
        "password": password,
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number,
        "department": department
    }
    
    result = await make_api_request("POST", "/manager/add-teacher", data=teacher_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def update_teacher(accessToken:str,teacher_id: int=0, full_name: str = "", email: str = "",
                        phone_number: str = "", department: str = "") -> str:
    """
    Cập nhật thông tin giáo viên.
    - Mục đích: Quản lý thay đổi hồ sơ giáo viên.

    """
    update_data = {}
    if full_name: update_data["full_name"] = full_name
    if email: update_data["email"] = email
    if phone_number: update_data["phone_number"] = phone_number
    if department: update_data["department"] = department
    
    result = await make_api_request("PUT", f"/manager/update-teacher/{teacher_id}", data=update_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def assign_teacher(accessToken:str,class_id: int, teacher_id: int) -> str:
    """
    Gán giáo viên cho lớp học.
    - Mục đích: Phân công giảng dạy.

    """
    assign_data = {
        "class_id": class_id,
        "teacher_id": teacher_id
    }
    
    result = await make_api_request("POST", "/manager/assign-teacher", data=assign_data, auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_all_users(accessToken:str) -> str:
    """
    Xem danh sách tất cả người dùng trong hệ thống.
    - Mục đích: Quản lý toàn bộ user (sinh viên, giáo viên, quản lý).

    """
    result = await make_api_request("GET", "/manager/all-users", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def get_all_classes(accessToken:str) -> str:
    """
    Xem danh sách tất cả lớp học trong hệ thống.
    - Mục đích: Quản lý toàn bộ lớp học.

    """
    result = await make_api_request("GET", "/manager/all-classes", auth_required=True,token=accessToken)
    return json.dumps(result, ensure_ascii=False)

# --- MCP Server Runner ---
async def run_mcp_stdio_server():
    """Chạy MCP server, lắng nghe kết nối qua standard input/output."""
    async with stdio_server() as (read_stream, write_stream):
        logging.info("MCP Stdio Server: Bắt đầu handshake với client...")
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options()
        )
        logging.info("MCP Stdio Server: Kết thúc hoặc client đã ngắt kết nối.")

if __name__ == "__main__":
    logging.info("Khởi động School Management MCP Server qua stdio...")
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info("\nMCP Server (stdio) đã dừng bởi người dùng.")
    except Exception as e:
        logging.critical(
            f"MCP Server (stdio) gặp lỗi không xử lý được: {e}", exc_info=True
        )
    finally:
        logging.info("MCP Server (stdio) đã thoát.")