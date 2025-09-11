# school_mcp_server.py
# This file implements the MCP server for school management system
# It exposes tools corresponding to the described APIs for Student, Teacher, and Admin/Manager
# Tools are async to handle API calls properly

import asyncio
import json
import logging
import os
import aiohttp
from typing import Dict, Any, Optional, List
from google.adk.tools.tool_context import ToolContext
import google.genai.types as types
from dotenv import load_dotenv
from mcp.server.fastmcp.utilities.types import Image
from typing import Annotated
from pydantic import SkipValidation
from google.adk.tools.tool_context import ToolContext
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ImageContent
import numpy as np
import matplotlib.ticker as mticker
from matplotlib import cm

from mcp.server.stdio import stdio_server
import sys
# vẽ biểu đồ thống kê báo cáo tổng quan với department_id là 1 học kì 2 năm học 2024-2025

import matplotlib.pyplot as plt
import io, base64
load_dotenv()
from constants import (
    GENERATED_THUMBNAILS_DIR,
    IMAGE_ROOT_DIR,
    THUMBNAIL_ASSETS_DIR,
    THUMBNAIL_IMAGE_SIZE,
)
import uuid
# --- Logging Setup ---
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "school_mcp_server_activity.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Lấy logger gốc
logger = logging.getLogger()

# Tạo một FileHandler với encoding UTF-8
file_handler = logging.FileHandler(LOG_FILE_PATH, mode="w", encoding="utf-8")

# Tạo một formatter và gán nó cho handler
formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
file_handler.setFormatter(formatter)

# Thêm handler vào logger (clear old handlers if needed)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler(sys.stderr))

API_BASE_URL = "https://ai-api.bitech.vn/api"
async def make_api_request(
    method: str,
    endpoint: str,
    *,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
    auth_required: bool = True,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """Thực hiện HTTP request đến API, hỗ trợ query params cho GET."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if token:
        token = token.strip('"').replace('"', '')
        if isinstance(token, bytes):
            token = token.decode("utf-8", errors="ignore")
    
    if auth_required:
        if not token:
            logging.warning(f"Yêu cầu xác thực cho endpoint '{endpoint}' nhưng không tìm thấy token.")
            return {"success": False, "message": "Lỗi xác thực: Bạn chưa đăng nhập hoặc phiên đã hết hạn. Vui lòng sử dụng tool 'login'."}
        headers["Authorization"] = f"Bearer {token}"
    
    logging.debug(f"Thực hiện request: {method.upper()} {url} với params={params}, data={data}, auth_required={auth_required}, token={'***' if token else None}")
    
    async with aiohttp.ClientSession() as session:
        try:
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params or {}) as response:
                    return await response.json()
            elif method.upper() == "POST":
                async with session.post(url, headers=headers, json=data or {}) as response:
                    return await response.json()
            elif method.upper() == "PUT":
                async with session.put(url, headers=headers, json=data or {}) as response:
                    return await response.json()
            else:
                raise ValueError(f"Phương thức không hỗ trợ: {method}")
        except Exception as e:
            logging.error(f"Lỗi khi gọi API tới {url}: {e}", exc_info=True)
            return {"success": False, "message": f"Lỗi kết nối API: {str(e)}"}

# Tool function to save image as artifact and conditionally save locally
# async def _image_save_func(image_bytes: bytes, file_extension: str, tool_context: ToolContext) -> Dict[str, Any]:
#     """Saves image bytes as an ADK artifact and conditionally saves a copy locally."""
#     logger.debug("Entering _image_save_func (artifact save version)...")

#     # Determine mime type and ensure extension format
#     if file_extension and not file_extension.startswith('.'):
#         file_extension = '.' + file_extension
#     mime_type = f"image/{file_extension.lstrip('.')}" if file_extension else "image/png"
#     # Make filename unique for the artifact itself and local copy
#     filename = f"generated_image_{uuid.uuid4()}{file_extension if file_extension else '.png'}" 

#     # --- Conditional Local Save Logic  --- 
#     if GENERATED_THUMBNAILS_DIR:
#         save_dir = GENERATED_THUMBNAILS_DIR
#         try:
#             os.makedirs(save_dir, exist_ok=True)
#             # Use the unique filename generated above for local copy consistency
#             local_path = os.path.join(save_dir, filename) 
            
#             logger.info(f"Attempting to save image locally to: {local_path} (SAVE_IMAGES_LOCALLY is True)")
#             with open(local_path, "wb") as f:
#                 f.write(image_bytes)
#             logger.info(f"Successfully saved image locally to: {local_path}")
#         except Exception as e:
#             # Log error but don't stop the main process
#             logger.warning(f"Local file save failed (path: {save_dir}): {e}", exc_info=False)
#     else:
#         logger.debug("Local image saving skipped (SAVE_IMAGES_LOCALLY is False).")
# --- MCP Server Setup ---
logging.info("Tạo MCP Server cho hệ thống quản lý trường học...")
mcp = FastMCP("school-management-mcp-server")

# --- Student Tools ---

@mcp.tool()
async def get_student_gpa_by_semester(token: str, semester: Optional[str] = None, academic_year: Optional[str] = None) -> Dict:
    """
    Dùng để thống kê điểm trung bình theo học kỳ
    Tính GPA của sinh viên theo học kỳ/năm học.
    So sánh điểm sinh viên với điểm trung bình lớp.
    Phân loại học lực (Xuất sắc, Giỏi, Khá, Trung bình, Yếu).
    Hiển thị chi tiết từng môn học với điểm và xếp hạng so với lớp.
    
    Args:
        token: Token xác thực (required).
        semester: Học kỳ (optional) chỉ nhận 3 tham số hãy từ prompt người dùng chọn tham số Args hợp lý là HOCKY1 | HOCKY2 | HOCKYHE .
        academic_year: Năm học (optional).
    """
    import uuid

    params = {}
    if semester:
        params['semester'] = semester
    if academic_year:
        params['academic_year'] = academic_year

    # Gọi API backend
    data = await make_api_request("GET", "/student/gpa-by-semester", params=params, token=token)

    if not data or not data.get("success", False):
        return {
            "success": False,
            "message": "Không lấy được dữ liệu GPA.",
            "payload": data
        }

    result = data["data"]
    student_gpa = result.get("student_gpa")
    courses = result.get("courses", [])
    summary = result.get("summary", {})

    if not courses:
        return {
            "success": True,
            "message": "Chưa có dữ liệu điểm.",
            "chart_base64": None,
            "filepath": None,
            "artifact_filename": None,
            "artifact_version": None,
            "summary": summary
        }

    # === VẼ CHART ===
    import matplotlib.pyplot as plt
    import numpy as np
    import base64, io, os

    uid = uuid.uuid4().hex[:8]
    filename = f"student_gpa_{semester or 'all'}_{uid}.png"
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)

    # Dữ liệu điểm
    course_names = [c["course_code"] for c in courses]
    student_scores = [c["student_score"] for c in courses]
    class_avgs = [c["class_average"] for c in courses]

    # --- Vẽ biểu đồ ---
    fig = plt.figure(figsize=(16, 8))
    gs = fig.add_gridspec(2, 2)

    # 1. Bar chart: điểm từng môn
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(course_names))
    width = 0.35
    ax1.bar(x - width/2, student_scores, width, label="Điểm sinh viên", color="#3498db")
    ax1.bar(x + width/2, class_avgs, width, label="Trung bình lớp", color="#2ecc71")
    ax1.set_xticks(x)
    ax1.set_xticklabels(course_names, rotation=30, ha="right")
    ax1.set_ylabel("Điểm")
    ax1.set_title("So sánh điểm từng môn với trung bình lớp")
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # 2. Radar chart: phân tích điểm
    ax2 = fig.add_subplot(gs[0, 1], polar=True)
    labels = course_names
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    student_scores_radar = student_scores + student_scores[:1]
    class_avgs_radar = class_avgs + class_avgs[:1]

    ax2.plot(angles, student_scores_radar, "o-", linewidth=2, label="Sinh viên", color="#e74c3c")
    ax2.fill(angles, student_scores_radar, alpha=0.25, color="#e74c3c")

    ax2.plot(angles, class_avgs_radar, "o-", linewidth=2, label="Trung bình lớp", color="#2ecc71")
    ax2.fill(angles, class_avgs_radar, alpha=0.25, color="#2ecc71")

    ax2.set_xticks(angles[:-1])
    ax2.set_xticklabels(labels)
    ax2.set_title("Radar chart: So sánh sinh viên vs lớp")
    ax2.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))

    # 3. Pie chart: học lực
    ax3 = fig.add_subplot(gs[1, :])
    categories = ["Xuất sắc", "Giỏi", "Khá", "Trung bình", "Yếu"]
    colors = ["#9b59b6", "#2980b9", "#27ae60", "#f39c12", "#e74c3c"]

    classification = summary.get("gpa_classification", "Chưa xếp loại")
    explode = [0.1 if c == classification else 0 for c in categories]
    values = [1 if c == classification else 0 for c in categories]

    ax3.pie(values, labels=categories, autopct=lambda p: f"{classification}" if p > 0 else "",
            colors=colors, startangle=140, explode=explode, shadow=True)
    ax3.set_title(f"Học lực: {classification} (GPA {student_gpa})")

    plt.suptitle(f"GPA học kỳ {semester or ''} - {academic_year or ''}", fontsize=16, fontweight="bold")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    image_bytes = buf.getvalue()

    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Lưu local
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return {
        "success": True,
        "message": "Biểu đồ GPA học kỳ.",
        "chart_base64": img_base64,
        "filepath": filepath,
        "artifact_filename": filename,
        "artifact_version": None,
        "summary": summary
    }

@mcp.tool()
async def get_student_course_progress(token: str) -> Dict:
    """
    Dùng để thống kê tiến độ học tập của sinh viên
    So sánh số môn đã học vs tổng số môn trong khoa.
    Phân loại: Đã hoàn thành, Đang học, Còn lại.
    Tính % hoàn thành theo tín chỉ.
    Hiển thị chi tiết từng môn theo trạng thái.
    
    Args:
        token: Token xác thực (required).
    """
    # Gọi API
    data = await make_api_request("GET", "/student/course-progress", token=token)

    if not data or not data.get("success", False):
        return {
            "success": False,
            "message": "Lấy dữ liệu tiến độ học tập thất bại.",
            "payload": data
        }

    progress_summary = data["data"].get("progress_summary", {})
    completed_courses = data["data"].get("completed_courses", [])
    current_courses = data["data"].get("current_courses", [])
    remaining_courses = data["data"].get("remaining_courses", [])

    if not progress_summary:
        return {
            "success": True,
            "message": "Không có dữ liệu tiến độ học tập.",
            "chart_base64": None,
            "filepath": None,
            "artifact_filename": None,
            "artifact_version": None,
            "summary": data["data"]
        }

    # Tạo filename duy nhất
    uid = uuid.uuid4().hex[:8]
    filename = f"student_course_progress_{uid}.png"
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)

    # Vẽ biểu đồ
    total_courses = progress_summary.get("total_courses", 0)
    completed_count = progress_summary.get("completed_courses", 0)
    current_count = progress_summary.get("current_courses", 0)
    remaining_count = progress_summary.get("remaining_courses", 0)

    total_credits = progress_summary.get("total_credits_required", 0)
    completed_credits = progress_summary.get("completed_credits", 0)
    current_credits = progress_summary.get("current_credits", 0)
    passed_credits = progress_summary.get("passed_credits", 0)
    remaining_credits = total_credits - (completed_credits + current_credits)

    # Pie chart: courses by status
    labels = ["Hoàn thành", "Đang học", "Còn lại"]
    sizes = [completed_count, current_count, remaining_count]
    colors = ["#2ecc71", "#3498db", "#e74c3c"]

    # Bar chart: credits progress
    categories = ["Tín chỉ yêu cầu", "Hoàn thành", "Đang học", "Còn lại"]
    values = [total_credits, completed_credits, current_credits, max(remaining_credits, 0)]
    bar_colors = ["#7f8c8d", "#2ecc71", "#3498db", "#e74c3c"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Pie
    wedges, texts, autotexts = axes[0].pie(
        sizes, labels=labels, autopct="%1.1f%%",
        startangle=140, colors=colors, textprops={'fontsize': 10}
    )
    axes[0].set_title("Tỷ lệ môn học theo trạng thái", fontsize=13, fontweight="bold")

    # Bar
    axes[1].bar(categories, values, color=bar_colors, edgecolor="k")
    axes[1].set_title("Tiến độ tín chỉ", fontsize=13, fontweight="bold")
    axes[1].set_ylabel("Số tín chỉ")
    for i, v in enumerate(values):
        axes[1].text(i, v + 0.5, str(v), ha="center", fontsize=9)

    plt.suptitle(
        f"Tiến độ học tập - {progress_summary.get('department', '')}",
        fontsize=14, fontweight="bold"
    )

    # Save
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    image_bytes = buf.getvalue()

    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return {
        "success": True,
        "message": "Biểu đồ tiến độ học tập.",
        "chart_base64": img_base64,
        "filepath": filepath,
        "artifact_filename": filename,
        "artifact_version": None,
        "summary": progress_summary
    }
# --- Teacher Tools ---

@mcp.tool()
async def get_teacher_class_enrollment_statistics(token: str, semester: Optional[str] = None, academic_year: Optional[str] = None) -> Dict:
    """
    Dùng để thống kê tuyển sinh lớp học
    Danh sách chi tiết sinh viên trong từng lớp.
    Phân loại lớp: Đầy, Gần đầy, Vừa đủ, Thiếu sinh viên.
    Tỷ lệ sử dụng sức chứa từng lớp.
    Thống kê tổng quan: Lớp đầy vs thiếu sinh viên.
    
    Args:
        token: Token xác thực (required).
        semester: Học kỳ (optional) chỉ nhận 3 tham số hãy từ prompt người dùng chọn tham số Args hợp lý là HOCKY1 | HOCKY2 | HOCKYHE .
        academic_year: Năm học (optional).
    """
    params = {}
    if semester:
        params['semester'] = semester
    if academic_year:
        params['academic_year'] = academic_year
    # Gọi API
    
    data = await make_api_request("GET", "/teacher/class-enrollment-statistics", params=params, token=token)

    if not data or not data.get("success", False):
        return {
            "success": False,
            "message": "Lấy dữ liệu thống kê lớp thất bại.",
            "payload": data
        }

    stats = data["data"]
    classes = stats.get("class_statistics", [])
    overall = stats.get("overall_statistics", {})

    if not classes:
        return {
            "success": True,
            "message": "Không có dữ liệu lớp học.",
            "chart_base64": None,
            "filepath": None,
            "artifact_filename": None,
            "artifact_version": None,
            "summary": overall
        }

    # Chuẩn bị file local
    uid = uuid.uuid4().hex[:8]
    filename = f"class_enrollment_{uid}.png"
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)

    # ========== CASE 1: chỉ 1 lớp ==========
    if len(classes) == 1:
        c = classes[0]
        info = c["class_info"]
        estats = c["enrollment_stats"]

        enrolled = estats["current_enrollment"]
        capacity = estats["max_capacity"]
        available = estats["available_slots"]

        fig, ax = plt.subplots(figsize=(6, 6))
        wedges, texts, autotexts = ax.pie(
            [enrolled, available],
            labels=["Đã đăng ký", "Còn trống"],
            autopct="%1.1f%%",
            colors=["#3498db", "#ecf0f1"],
            startangle=90,
            wedgeprops=dict(width=0.4, edgecolor="w")
        )
        ax.set_title(f"Sức chứa lớp {info['course_code']} - {info['course_name']}", fontsize=14, fontweight="bold")

        # Chèn text trung tâm
        ax.text(0, 0, f"{enrolled}/{capacity}", ha="center", va="center", fontsize=12, fontweight="bold")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        image_bytes = buf.getvalue()
        img_base64 = base64.b64encode(image_bytes).decode("utf-8")

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return {
            "success": True,
            "message": f"Biểu đồ sức chứa lớp {info['course_code']}",
            "chart_base64": img_base64,
            "filepath": filepath,
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": estats
        }

    # ========== CASE 2: nhiều lớp ==========
    else:
        import numpy as np

        # Bar chart: enrollment per class
        labels = [c["class_info"]["course_code"] for c in classes]
        enrolled = [c["enrollment_stats"]["current_enrollment"] for c in classes]
        capacity = [c["enrollment_stats"]["max_capacity"] for c in classes]

        x = np.arange(len(labels))
        width = 0.35

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Bar chart: enrolled vs capacity
        ax1 = axes[0]
        ax1.bar(x - width/2, enrolled, width, label="Đã đăng ký", color="#3498db")
        ax1.bar(x + width/2, capacity, width, label="Sức chứa", color="#95a5a6", alpha=0.7)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=30, ha="right")
        ax1.set_ylabel("Số SV")
        ax1.set_title("So sánh tuyển sinh / sức chứa")
        ax1.legend()
        ax1.grid(axis="y", linestyle="--", alpha=0.5)

        # Pie chart: class status distribution
        ax2 = axes[1]
        statuses = [c["enrollment_stats"]["enrollment_status"] for c in classes]
        from collections import Counter
        status_counts = Counter(statuses)
        labels_pie = list(status_counts.keys())
        values_pie = list(status_counts.values())
        colors = ["#2ecc71", "#f1c40f", "#3498db", "#e74c3c"]

        wedges, texts, autotexts = ax2.pie(
            values_pie,
            labels=labels_pie,
            autopct="%1.1f%%",
            colors=colors[:len(values_pie)],
            startangle=90
        )
        ax2.set_title("Tỷ lệ trạng thái lớp")

        plt.suptitle(f"Tuyển sinh các lớp ({semester or ''} - {academic_year or ''})", fontsize=15, fontweight="bold")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        image_bytes = buf.getvalue()
        img_base64 = base64.b64encode(image_bytes).decode("utf-8")

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return {
            "success": True,
            "message": "Biểu đồ tuyển sinh nhiều lớp.",
            "chart_base64": img_base64,
            "filepath": filepath,
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": overall
        }
@mcp.tool()
async def get_teacher_student_grades_analysis(token: str, class_id: Optional[int] = None, semester: Optional[str] = None, academic_year: Optional[str] = None) -> Dict:
    """
    Dùng để thống kê điểm chi tiết từng lớp học.
    Phân bố điểm theo grade (A, B, C, D, F).
    Điểm trung bình, cao nhất, thấp nhất của lớp.
    Tỷ lệ đậu/rớt, xếp hạng sinh viên.
    
    Args:
        token: Token xác thực (required).
        class_id: ID lớp học (optional).
        semester: Học kỳ (optional) chỉ nhận 3 tham số hãy từ prompt người dùng chọn tham số Args hợp lý là HOCKY1 | HOCKY2 | HOCKYHE .
        academic_year: Năm học (optional).
    """
    import uuid
    from statistics import mean, median

    params = {}
    if class_id:
        params['class_id'] = class_id
    if semester:
        params['semester'] = semester
    if academic_year:
        params['academic_year'] = academic_year

    # Gọi API
    data = await make_api_request("GET", "/teacher/student-grades-analysis", params=params, token=token)

    # Nếu API lỗi, chuyển nguyên về cho caller xử lý
    if not data or not data.get("success", False):
        return {
            "success": False,
            "message": "Lấy dữ liệu phân tích điểm thất bại.",
            "payload": data
        }

    analyses = data["data"].get("class_grade_analysis", [])
    if not analyses:
        return {
            "success": True,
            "message": "Không có lớp phù hợp / dữ liệu điểm rỗng.",
            "chart_base64": None,
            "filepath": None,
            "artifact_filename": None,
            "artifact_version": None,
            "summary": data["data"]
        }

    # Tạo filename duy nhất
    uid = uuid.uuid4().hex[:8]
    filename = f"class_grades_{class_id or 'multi'}_{uid}.png"
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)

    # CHART for single class
    if len(analyses) == 1:
        item = analyses[0]
        class_info = item["class_info"]
        grade_stats = item.get("grade_statistics")
        student_grades = item.get("student_grades", [])

        # Collect numerical scores if có
        scores = [s["score"] for s in student_grades if s.get("score") is not None]

        # Prepare grade distribution data (A,B,C,D,F)
        grade_order = ["A", "B", "C", "D", "F"]
        grade_counts = {g: 0 for g in grade_order}
        if grade_stats and grade_stats.get("grade_distribution"):
            for g in grade_stats["grade_distribution"]:
                grade_counts[g["grade"]] = g["count"]
        else:
            # fallback from student_grades
            for s in student_grades:
                g = s.get("grade")
                if g:
                    grade_counts[g] = grade_counts.get(g, 0) + 1

        # Create figure: histogram (left) + grade bar (right) + stats box below
        fig = plt.figure(constrained_layout=True, figsize=(12, 6))
        gs = fig.add_gridspec(2, 3)
        ax_hist = fig.add_subplot(gs[:, :2])   # left two columns (vertical span)
        ax_bar = fig.add_subplot(gs[0, 2])     # top-right
        ax_text = fig.add_subplot(gs[1, 2])    # bottom-right (text summary)
        ax_text.axis("off")

        # Histogram of scores
        if scores:
            bins = min(10, max(5, len(set(scores))))
            ax_hist.hist(scores, bins=bins, edgecolor="white", linewidth=1.0, alpha=0.9)
            ax_hist.axvline(mean(scores), color="red", linestyle="--", label=f"Mean: {mean(scores):.2f}")
            ax_hist.axvline(median(scores), color="orange", linestyle="-.", label=f"Median: {median(scores):.2f}")
            ax_hist.set_xlabel("Điểm", fontsize=11)
            ax_hist.set_ylabel("Số sinh viên", fontsize=11)
            ax_hist.set_title(f"Phân bố điểm: {class_info.get('course_code','')} - {class_info.get('course_name','')}", fontsize=13, fontweight="bold")
            ax_hist.legend()
            ax_hist.grid(axis="y", linestyle="--", alpha=0.5)
        else:
            ax_hist.text(0.5, 0.5, "Không có dữ liệu điểm để vẽ histogram", ha="center", va="center", fontsize=12)
            ax_hist.set_xticks([])
            ax_hist.set_yticks([])

        # Grade bar (counts)
        grades = grade_order
        counts = [grade_counts[g] for g in grades]
        bar_colors = ["#2ecc71", "#3498db", "#f1c40f", "#e67e22", "#e74c3c"]
        ax_bar.barh(grades[::-1], counts[::-1], color=bar_colors[::-1], edgecolor="k", height=0.6)
        ax_bar.set_title("Phân bố grade (A-F)", fontsize=12)
        for i, v in enumerate(counts[::-1]):
            ax_bar.text(v + 0.1, i, str(v), va="center", fontsize=10)

        # Stats text box
        stats_lines = []
        if grade_stats:
            stats_lines.append(f"Tổng sinh viên có điểm: {grade_stats.get('total_students', len(scores))}")
            stats_lines.append(f"Điểm trung bình: {grade_stats.get('average_score', (mean(scores) if scores else 'N/A'))}")
            stats_lines.append(f"Điểm cao nhất: {grade_stats.get('highest_score', (max(scores) if scores else 'N/A'))}")
            stats_lines.append(f"Điểm thấp nhất: {grade_stats.get('lowest_score', (min(scores) if scores else 'N/A'))}")
            stats_lines.append(f"Tỉ lệ đậu (>=4.0): {grade_stats.get('pass_rate', 'N/A')}%")
        else:
            # fallback
            stats_lines.append(f"Tổng sinh viên có điểm: {len(scores)}")
            stats_lines.append(f"Điểm trung bình: {mean(scores):.2f}" if scores else "Điểm trung bình: N/A")
            stats_lines.append(f"Điểm cao nhất: {max(scores)}" if scores else "Điểm cao nhất: N/A")
            stats_lines.append(f"Điểm thấp nhất: {min(scores)}" if scores else "Điểm thấp nhất: N/A")
            stats_lines.append(f"Tỉ lệ đậu (>=4.0): {round(sum(1 for s in scores if s>=4.0)/len(scores)*100,1)}%" if scores else "Tỉ lệ đậu: N/A")

        ax_text.text(0, 0.95, f"LỚP: {class_info.get('course_code','')} - {class_info.get('course_name','')}", fontsize=11, fontweight="bold")
        for i, line in enumerate(stats_lines):
            ax_text.text(0, 0.7 - i*0.18, line, fontsize=10)
        # finish
        plt.suptitle(f"Phân tích điểm chi tiết - {class_info.get('semester','')} {class_info.get('academic_year','')}", fontsize=14, fontweight="bold")

        # Save figure
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        image_bytes = buf.getvalue()

        img_base64 = base64.b64encode(image_bytes).decode("utf-8")

        response = {
            "success": True,
            "message": f"Biểu đồ phân tích điểm cho lớp {class_info.get('course_code','')}",
            "chart_base64": img_base64,
            "filepath": filepath,
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": item.get("grade_statistics") or {}
        }
        # Lưu local copy
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return response

    # CHART for multiple classes
    else:
        # Filter out classes with no grade_statistics
        valid = [it for it in analyses if it.get("grade_statistics") and it["grade_statistics"].get("total_students",0) > 0]
        if not valid:
            # fallback: still try to draw boxplot using available student_grades if any
            all_scores = []
            labels = []
            for it in analyses:
                sg = it.get("student_grades", [])
                scs = [s["score"] for s in sg if s.get("score") is not None]
                if scs:
                    all_scores.append(scs)
                    labels.append(f"{it['class_info'].get('course_code','')}")
            if not all_scores:
                return {
                    "success": True,
                    "message": "Không có dữ liệu điểm để vẽ cho các lớp.",
                    "chart_base64": None,
                    "filepath": None,
                    "artifact_filename": None,
                    "artifact_version": None,
                    "summary": data["data"]
                }
            # Draw simple boxplot
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.boxplot(all_scores, labels=labels, patch_artist=True)
            ax.set_title("Phân bố điểm theo lớp (boxplot)", fontsize=14, fontweight="bold")
            ax.set_ylabel("Điểm")
            ax.grid(axis="y", linestyle="--", alpha=0.5)
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150)
            plt.close(fig)
            buf.seek(0)
            image_bytes = buf.getvalue()
            img_base64 = base64.b64encode(image_bytes).decode("utf-8")
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            return {
                "success": True,
                "message": "Boxplot phân bố điểm cho các lớp (dữ liệu thô).",
                "chart_base64": img_base64,
                "filepath": filepath,
                "artifact_filename": filename,
                "artifact_version": None,
                "summary": data["data"]
            }

        # Build grade matrix (grades x classes)
        grade_order = ["A", "B", "C", "D", "F"]
        class_labels = [it["class_info"].get("course_code", f"class_{i}") for i, it in enumerate(valid)]
        matrix = []
        for it in valid:
            gd = {g["grade"]: g["count"] for g in it["grade_statistics"].get("grade_distribution", [])}
            matrix.append([gd.get(g, 0) for g in grade_order])

        # transpose matrix to get grade rows
        import numpy as np
        mat = np.array(matrix)  # shape (n_classes, n_grades)

        # Grouped bar chart for grade distribution across classes
        n_classes = len(class_labels)
        n_grades = len(grade_order)
        x = np.arange(n_classes)
        width = 0.12 if n_grades > 4 else 0.15

        fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2, 1]})
        ax1, ax2 = axes

        # For each grade, plot bars offset
        palette = ["#2ecc71", "#3498db", "#f1c40f", "#e67e22", "#e74c3c"]
        for i, grade in enumerate(grade_order):
            offsets = x + (i - (n_grades-1)/2) * width
            ax1.bar(offsets, mat[:, i], width=width, label=grade, color=palette[i], edgecolor="k")
            # annotate values on top if bars not too cramped
            for xi, val in zip(offsets, mat[:, i]):
                if val > 0:
                    ax1.text(xi, val + 0.05, str(int(val)), ha="center", va="bottom", fontsize=9)

        ax1.set_xticks(x)
        ax1.set_xticklabels(class_labels, rotation=30, ha="right")
        ax1.set_ylabel("Số sinh viên (count)")
        ax1.set_title(f"Phân bố grade theo lớp ({semester or ''} - {academic_year or ''})", fontsize=14, fontweight="bold")
        ax1.legend(title="Grade")
        ax1.grid(axis="y", linestyle="--", alpha=0.5)

        # Boxplot of score distributions (ax2)
        score_lists = []
        label_for_scores = []
        for it in valid:
            scs = [s["score"] for s in it.get("student_grades", []) if s.get("score") is not None]
            if scs:
                score_lists.append(scs)
                label_for_scores.append(it["class_info"].get("course_code", ""))
        if score_lists:
            ax2.boxplot(score_lists, labels=label_for_scores, patch_artist=True)
            ax2.set_ylabel("Điểm")
            ax2.set_title("Phân bố điểm (Boxplot) cho các lớp có dữ liệu", fontsize=12)
            ax2.grid(axis="y", linestyle="--", alpha=0.5)
        else:
            ax2.text(0.5, 0.5, "Không có dữ liệu score chi tiết để vẽ boxplot", ha="center", va="center")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        image_bytes = buf.getvalue()
        img_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Save local
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return {
            "success": True,
            "message": "Biểu đồ phân tích điểm cho nhiều lớp.",
            "chart_base64": img_base64,
            "filepath": filepath,
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": data["data"]
        }
# --- Admin/Manager Tools ---
def _encode_image(image) -> ImageContent:
    """
    Encodes a PIL Image to a format compatible with ImageContent.
    """
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    img_obj = Image(data=img_bytes, format="png")
    return img_obj.to_image_content()
@mcp.tool()
async def get_manager_department_personnel_statistics( token: str, department_id: Optional[int] = None, department_name: Optional[str] = "" ) -> Dict:
    """
    Dùng để vẽ biểu đồ thống kê nhân sự theo khoa
    Tổng số SV/GV theo từng khoa.
    Tỷ lệ SV/GV, phân bố chuyên ngành.
    Số lượng khóa học, lớp học đang hoạt động.
    So sánh giữa các khoa.
    
    Args:
        token: Token xác thực (required).
        department_id: ID khoa (optional).
        department_Name: Tên khoa (optional).
    - Nếu nhiều khoa: grouped bars (SV vs GV) + line ratio (SV/GV).
    - Nếu 1 khoa: composite figure (donut majors, SV vs GV, KPI bars).
    """




    filename = "department_personnel_chart.png"

    # Gọi API
    params = {}
    if department_id:
        params["department_id"] = department_id
    elif department_name:
        params["department_name"] = department_name

    data = await make_api_request("GET", "/manager/department-personnel-statistics", params=params, token=token)

    # Kiểm tra dữ liệu trả về
    if not data or not data.get("success", False):
        return {"success": False, "message": "Lấy dữ liệu thất bại", "detail": data}

    departments = data["data"].get("department_personnel_statistics", [])
    overall_summary = data["data"].get("overall_summary", {})

    # Trường hợp không có dữ liệu
    if not departments:
        return {
            "success": True,
            "message": "Không có dữ liệu khoa",
            "chart_base64": "",
            "filepath": "",
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": overall_summary
        }

    # Chuẩn chỉnh style chung
    plt.rcParams.update({
        "font.size": 11,
        "figure.facecolor": "white",
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.grid": False
    })

    # ---------- NHIỀU KHOA: grouped bar + ratio ----------
    if len(departments) > 1:
        dept_names = [d["department_info"]["department_name"] for d in departments]
        students = [d["student_statistics"].get("total_students", 0) for d in departments]
        teachers = [d["teacher_statistics"].get("total_teachers", 0) for d in departments]
        ratios = [
            round(
                d["teacher_statistics"].get("student_teacher_ratio",
                                           (s / t if t > 0 else 0)
                                           ), 1
            ) for d, s, t in zip(departments, students, teachers)
        ]

        n = len(dept_names)
        x = np.arange(n)
        width = 0.35

        fig, ax = plt.subplots(figsize=(max(10, n * 1.8), 6))
        cmap = cm.get_cmap("tab10")
        bar_students = ax.bar(x - width / 2, students, width=width, label="Sinh viên", color=cmap(0), alpha=0.95)
        bar_teachers = ax.bar(x + width / 2, teachers, width=width, label="Giảng viên", color=cmap(1), alpha=0.95)

        # Annotate counts on bars
        def annotate_bars(rects, ax_local, fmt=int, yoffset=6):
            for rect in rects:
                h = rect.get_height()
                if h > 0:
                    ax_local.annotate(
                        f"{fmt(h)}",
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, yoffset),
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                        fontsize=10,
                        color="#222"
                    )
        annotate_bars(bar_students, ax)
        annotate_bars(bar_teachers, ax)

        ax.set_xticks(x)
        ax.set_xticklabels(dept_names, rotation=30, ha="right")
        ax.set_ylabel("Số lượng người")
        title = f"Thống kê nhân sự theo khoa"
        ax.set_title(f"{title} ({overall_summary.get('total_departments', len(departments))} khoa)")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.legend(frameon=True)

        # Secondary axis for ratio (SV/GV)
        ax2 = ax.twinx()
        ax2.plot(x, ratios, color=cmap(2), marker="o", linewidth=2, label="Tỉ lệ SV/GV")
        for i, r in enumerate(ratios):
            ax2.annotate(f"{r}", xy=(x[i], ratios[i]), xytext=(0, 8), textcoords="offset points", ha="center", va="bottom", fontsize=10, color=cmap(2))
        ax2.set_ylabel("Tỉ lệ SV/GV")
        ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=False))

        # Combined legend
        lines, labs = ax.get_legend_handles_labels()
        lines2, labs2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labs + labs2, loc="upper left", frameon=True)

        plt.tight_layout()

    # ---------- 1 KHOA: composite figure (donut + SV-GV + KPI) ----------
    else:
        dept = departments[0]
        dept_name = dept["department_info"].get("department_name", "Khoa")
        sv = dept["student_statistics"].get("total_students", 0)
        gv = dept["teacher_statistics"].get("total_teachers", 0)
        ratio = round(dept["teacher_statistics"].get("student_teacher_ratio", (sv / gv if gv > 0 else 0)), 1)

        # major distribution
        major_dist_list = dept["student_statistics"].get("major_distribution", [])
        # convert list->dict if needed
        if isinstance(major_dist_list, list):
            maj_dict = {}
            for item in major_dist_list:
                key = item.get("major") if isinstance(item, dict) else str(item)
                val = item.get("count", 0) if isinstance(item, dict) else 0
                maj_dict[key] = maj_dict.get(key, 0) + val
        elif isinstance(major_dist_list, dict):
            maj_dict = major_dist_list
        else:
            maj_dict = {}

        # prepare top-N majors
        sorted_maj = sorted(maj_dict.items(), key=lambda x: x[1], reverse=True)
        top_n = 6
        labels = [m for m, c in sorted_maj[:top_n]]
        sizes = [c for m, c in sorted_maj[:top_n]]
        other = sum(c for m, c in sorted_maj[top_n:])
        if other > 0:
            labels.append("Khác")
            sizes.append(other)
        if not labels:
            labels = ["Không có dữ liệu"]
            sizes = [1]

        # Academic KPIs
        academic = dept.get("academic_statistics", {})
        total_courses = academic.get("total_courses", 0)
        total_credits = academic.get("total_credits_offered", 0)
        active_classes = academic.get("active_classes_current_semester", 0)
        current_enrollments = academic.get("current_enrollments", 0)

        # Build figure with GridSpec: left donut, top-right SV/GV, bottom-right KPIs
        fig = plt.figure(figsize=(12, 8), constrained_layout=True)
        gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 1, 1])

        ax_pie = fig.add_subplot(gs[:, 0])
        ax_sv_gv = fig.add_subplot(gs[0, 1:])
        ax_kpi = fig.add_subplot(gs[1, 1:])

        # Donut pie (majors)
        cmap = cm.get_cmap("tab20")
        colors = [cmap(i) for i in range(len(labels))]
        wedges, texts, autotexts = ax_pie.pie(
            sizes,
            labels=labels,
            autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
            startangle=90,
            pctdistance=0.75,
            textprops={"fontsize": 10}
        )
        # make donut
        centre_circle = plt.Circle((0, 0), 0.45, fc="white")
        ax_pie.add_artist(centre_circle)
        ax_pie.set_title(f"Phân bố chuyên ngành\n{dept_name}", fontsize=14, fontweight="bold")

        # SV vs GV bar
        ax_sv_gv.bar(["Sinh viên", "Giảng viên"], [sv, gv], color=[cm.get_cmap("tab10")(0), cm.get_cmap("tab10")(1)], width=0.5)
        for i, val in enumerate([sv, gv]):
            ax_sv_gv.annotate(f"{int(val)}", xy=(i, val), xytext=(0, 8), textcoords="offset points", ha="center", va="bottom", fontsize=11)
        ax_sv_gv.set_ylabel("Số lượng")
        ax_sv_gv.set_title(f"Số lượng SV & GV (Tỉ lệ: {ratio})", fontsize=12)

        # KPI horizontal bars
        kpis = {
            "Số khoá học": total_courses,
            "Tổng tín chỉ": total_credits,
            "Lớp đang hoạt động": active_classes,
            "Tổng đăng ký": current_enrollments
        }
        k_labels = list(kpis.keys())
        k_values = list(kpis.values())
        y_pos = np.arange(len(k_labels))
        ax_kpi.barh(y_pos, k_values, height=0.6, color=cm.get_cmap("Pastel1").colors[:len(k_labels)])
        for i, v in enumerate(k_values):
            ax_kpi.annotate(f"{int(v)}", xy=(v, y_pos[i]), xytext=(6, -4), textcoords="offset points", ha="left", va="center", fontsize=10)
        ax_kpi.set_yticks(y_pos)
        ax_kpi.set_yticklabels(k_labels)
        ax_kpi.invert_yaxis()
        ax_kpi.set_xlabel("Giá trị")
        ax_kpi.set_title("Chỉ số học thuật - hiện tại", fontsize=12)

    # Lưu ảnh vào buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160)
    plt.close("all")
    buf.seek(0)
    image_bytes = buf.getvalue()
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Lưu file local
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    response = {
        "success": True,
        "message": "Biểu đồ nhân sự các khoa",
        "chart_base64": img_base64,
        "filepath": filepath,
        "artifact_filename": filename,
        "artifact_version": None,
        "summary": overall_summary
    }
    return response

@mcp.tool()
async def get_manager_class_offering_statistics(token: str, department_id: Optional[int] = None, department_name: Optional[str] = "" ,semester: Optional[str] = None, academic_year: Optional[str] = None) -> Dict:
    """
    Dùng để vẽ biểu đồ thống kê lớp học theo khoa/học kỳ
    Số lớp mở theo từng khoa trong học kỳ.
    Tỷ lệ sử dụng sức chứa, lớp thiếu/đầy sinh viên.
    Phân bố trạng thái lớp học.
    Lọc theo học kỳ/năm học.
    
    Args:
        token: Token xác thực (required).
        department_id: ID khoa (optional).
        department_Name: Tên khoa (optional).
        semester: Học kỳ (optional) chỉ nhận 3 tham số hãy từ prompt người dùng chọn tham số Args hợp lý là HOCKY1 | HOCKY2 | HOCKYHE .
        academic_year: Năm học (optional).
    - Nhiều khoa: stacked bar (trạng thái lớp) + enrollment vs capacity subplot.
    - 1 khoa: donut (phân bố trạng thái) + KPI bars + SV/GV.
    """

    filename = "class_offering_chart.png"

    # Gọi API
    params = {}
    if department_id:
        params['department_id'] = department_id
    elif department_name:
        params['department_name'] = department_name
    if semester:
        params['semester'] = semester
    if academic_year:
        params['academic_year'] = academic_year

    data = await make_api_request("GET", "/manager/class-offering-statistics", params=params, token=token)

    # Validate
    if not data or not data.get("success", False):
        return {"success": False, "message": "Lấy dữ liệu thất bại", "detail": data}

    departments = data["data"].get("class_offering_statistics", [])
    overall_summary = data["data"].get("overall_summary", {})

    # No data
    if not departments:
        return {
            "success": True,
            "message": "Không có dữ liệu lớp học",
            "chart_base64": "",
            "filepath": "",
            "artifact_filename": filename,
            "artifact_version": None,
            "summary": overall_summary
        }

    # style chung
    plt.rcParams.update({
        "font.size": 11,
        "figure.facecolor": "white",
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
    })

    # helper: lấy count theo status (thông thường status là "Mở đăng ký","Đang học","Hoàn thành")
    def get_status_counts(d):
        dist = d.get("class_summary", {}).get("status_distribution", [])
        status_map = {item.get("status"): item.get("count", 0) for item in dist}
        # fallback: nếu keys là enum-like, giữ nguyên
        return status_map

    # --- NHIỀU KHOA: stacked bar + enrollment subplot ---
    if len(departments) > 1:
        dept_names = [d["department_info"].get("department_name", f"Khoa {i}") for i, d in enumerate(departments)]
        # statuses to show in stacked order
        common_statuses = ["Mở đăng ký", "Đang học", "Hoàn thành"]
        # build matrix counts [status][dept]
        counts_by_status = {s: [] for s in common_statuses}
        enrollments = []
        capacities = []
        utilizations = []
        for d in departments:
            status_map = get_status_counts(d)
            # if status_map is empty, try to infer from keys
            if not status_map:
                # safety: look at class_summary.total_classes maybe
                for s in common_statuses:
                    counts_by_status[s].append(0)
            else:
                for s in common_statuses:
                    counts_by_status[s].append(status_map.get(s, 0))
            en = d.get("enrollment_summary", {}).get("total_enrollment", 0)
            cp = d.get("enrollment_summary", {}).get("total_capacity", 0)
            util = d.get("enrollment_summary", {}).get("utilization_rate",
                                                      round((en / cp * 100) if cp > 0 else 0, 1))
            enrollments.append(en)
            capacities.append(cp)
            utilizations.append(util)

        n = len(dept_names)
        x = np.arange(n)
        fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(max(10, n * 1.6), 8), gridspec_kw={"height_ratios": [3, 1]})

        # stacked bars
        bottom = np.zeros(n)
        cmap = cm.get_cmap("Set2")
        color_map = {"Mở đăng ký": "#4CAF50", "Đang học": "#2196F3", "Hoàn thành": "#FFC107"}
        bars = []
        for status in common_statuses:
            vals = np.array(counts_by_status[status])
            b = ax_top.bar(x, vals, bottom=bottom, label=f"{status} ({vals.sum()})", color=color_map.get(status), edgecolor="none")
            # annotate each segment if >0
            for xi, h, bot in zip(x, vals, bottom):
                if h > 0:
                    ax_top.text(xi, bot + h / 2, f"{int(h)}", ha="center", va="center", fontsize=9, color="#111")
            bottom += vals
            bars.append(b)

        ax_top.set_xticks(x)
        ax_top.set_xticklabels(dept_names, rotation=30, ha="right")
        ax_top.set_ylabel("Số lớp")
        ax_top.set_title(f"Phân bố trạng thái lớp học theo khoa ({semester or ''} - {academic_year or ''})")
        ax_top.grid(axis="y", linestyle="--", alpha=0.4)
        ax_top.legend(frameon=True, ncol=3, bbox_to_anchor=(1.0, 1.05))

        # enrollment vs capacity bars in bottom subplot + utilization line
        width = 0.35
        ax_bot.bar(x - width/2, enrollments, width=width, label="Tổng đăng ký", color="#6CA0DC")
        ax_bot.bar(x + width/2, capacities, width=width, label="Tổng sức chứa", color="#C5D6E8", alpha=0.9)
        ax_bot.set_xticks(x)
        ax_bot.set_xticklabels([], rotation=30)  # hide duplicate labels
        ax_bot.set_ylabel("Số lượng")
        ax_bot.grid(axis="y", linestyle="--", alpha=0.3)
        # utilization line (secondary axis)
        ax2 = ax_bot.twinx()
        ax2.plot(x, utilizations, color="#D65A31", marker="o", label="Tỉ lệ sử dụng (%)", linewidth=2)
        for xi, val in zip(x, utilizations):
            ax2.text(xi, val + 1.5, f"{val:.0f}%", ha="center", va="bottom", fontsize=9, color="#D65A31")
        ax2.set_ylabel("Tỉ lệ sử dụng (%)")
        # combined legend for bottom
        lines1, labs1 = ax_bot.get_legend_handles_labels()
        lines2, labs2 = ax2.get_legend_handles_labels()
        ax_bot.legend(lines1 + lines2, labs1 + labs2, loc="upper center", ncol=3, frameon=True)

        plt.tight_layout()

    # --- 1 KHOA: donut + KPI panels ---
    else:
        dept = departments[0]
        dept_name = dept["department_info"].get("department_name", "Khoa")
        status_map = get_status_counts(dept)
        # fallback statuses order
        labels = []
        sizes = []
        # Prefer canonical order
        for s in ["Mở đăng ký", "Đang học", "Hoàn thành"]:
            if status_map.get(s, 0) > 0:
                labels.append(s)
                sizes.append(status_map.get(s, 0))
        # If none found, take whatever keys exist
        if not labels:
            for k, v in status_map.items():
                labels.append(k)
                sizes.append(v)
        if not labels:
            labels = ["Không có dữ liệu"]
            sizes = [1]

        enrollment_summary = dept.get("enrollment_summary", {})
        total_enrollment = enrollment_summary.get("total_enrollment", 0)
        total_capacity = enrollment_summary.get("total_capacity", 0)
        utilization = enrollment_summary.get("utilization_rate", round((total_enrollment / total_capacity * 100) if total_capacity > 0 else 0, 1))
        full = enrollment_summary.get("full_classes", 0)
        under = enrollment_summary.get("under_enrolled_classes", 0)
        well = enrollment_summary.get("well_enrolled_classes", 0)
        total_classes = dept.get("class_summary", {}).get("total_classes", sum(sizes))

        # layout: left donut, right top: SV/GV, right bottom: KPI bars
        fig = plt.figure(figsize=(12, 7), constrained_layout=True)
        gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 1, 1])
        ax_pie = fig.add_subplot(gs[:, 0])
        ax_sv_gv = fig.add_subplot(gs[0, 1:])
        ax_kpi = fig.add_subplot(gs[1, 1:])

        # Donut
        cmap = cm.get_cmap("tab20")
        color_palette = [cmap(i) for i in range(len(labels))]
        wedges, texts, autotexts = ax_pie.pie(
            sizes,
            labels=labels,
            autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
            startangle=90,
            pctdistance=0.75,
            colors=color_palette,
            textprops={"fontsize": 11}
        )
        centre = plt.Circle((0, 0), 0.45, color="white")
        ax_pie.add_artist(centre)
        ax_pie.set_title(f"Phân bố trạng thái lớp - {dept_name}\nTổng lớp: {total_classes}", fontsize=14, fontweight="bold")

        # SV vs GV if available (we can derive from class_details counts or API)
        # Try to infer from class_details total enrollment per class vs capacity
        sv_total = sum([c.get("current_enrollment", 0) for c in dept.get("class_details", [])]) if dept.get("class_details") else total_enrollment
        # teachers count unknown here (not returned in class_offering endpoint), skip if not available
        # show enrollment vs capacity bars
        ax_sv_gv.bar(["Tổng đăng ký", "Tổng sức chứa"], [total_enrollment, total_capacity], color=["#6CA0DC", "#C5D6E8"])
        ax_sv_gv.set_title(f"Đăng ký vs Sức chứa (Tỉ lệ: {utilization}%)", fontsize=12)
        for i, val in enumerate([total_enrollment, total_capacity]):
            ax_sv_gv.text(i, val + max(1, val * 0.02), f"{int(val)}", ha="center", va="bottom", fontsize=10)

        # KPI bars (full / well / under)
        k_labels = ["Đầy", "Vừa đủ/Khá", "Thiếu sinh viên"]
        k_values = [full, well, under]
        y_pos = np.arange(len(k_labels))
        ax_kpi.barh(y_pos, k_values, color=["#2ca02c", "#f0ad4e", "#d62728"])
        for i, v in enumerate(k_values):
            ax_kpi.text(v + 0.5, y_pos[i], f"{int(v)}", va="center", fontsize=10)
        ax_kpi.set_yticks(y_pos)
        ax_kpi.set_yticklabels(k_labels)
        ax_kpi.invert_yaxis()
        ax_kpi.set_title("Tình trạng lớp (KPI)", fontsize=12)

        plt.suptitle(f"Thống kê lớp học - {dept_name} ({semester or ''} {academic_year or ''})", fontsize=15, fontweight="bold")

    # Lưu ảnh vào buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160)
    plt.close("all")
    buf.seek(0)
    image_bytes = buf.getvalue()
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Lưu file local
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    response = {
        "success": True,
        "message": "Biểu đồ thống kê lớp học theo khoa",
        "chart_base64": img_base64,
        "filepath": filepath,
        "artifact_filename": filename,
        "artifact_version": None,
        "summary": overall_summary
    }
    return response
@mcp.tool()
async def get_manager_comprehensive_system_report(token: str, semester: Optional[str] = None, academic_year: Optional[str] = None) -> Dict:
    """
    Dùng để vẽ báo cáo tổng quan toàn hệ thống (tổng SV, GV, khoa, lớp).
    Thống kê theo học kỳ hiện tại.
    Chỉ số sức khỏe hệ thống (0-100 điểm).
    Phát hiện vấn đề: Lớp không có GV, SV/GV không có khoa.
    
    Args:
        token: Token xác thực (required).
        semester: Học kỳ (optional) chỉ nhận 3 tham số hãy từ prompt người dùng chọn tham số Args hợp lý là HOCKY1 | HOCKY2 | HOCKYHE .
        academic_year: Năm học (optional).
    """
    import matplotlib.gridspec as gridspec

    filename: str = "comprehensive_system_report.png"
    params = {}
    if semester:
        params['semester'] = semester
    if academic_year:
        params['academic_year'] = academic_year

    # Gọi API
    data = await make_api_request("GET", "/manager/comprehensive-system-report", params=params, token=token)
    if not data or not data.get("success"):
        # Trả nguyên lỗi nếu api lỗi
        return data

    payload = data.get("data", {}) or {}
    system = payload.get("system_overview", {})
    stats = payload.get("current_semester_stats", {})
    departments = payload.get("department_breakdown", []) or []
    perf = payload.get("academic_performance", {}) or {}
    health = payload.get("system_health_indicators", {}) or {}
    meta = payload.get("report_metadata", {}) or {}

    # --- Prepare data safe getters ---
    total_students = system.get("total_students", 0)
    total_teachers = system.get("total_teachers", 0)
    total_departments = system.get("total_departments", 0)
    total_courses = system.get("total_courses", 0)
    overall_ratio = system.get("overall_student_teacher_ratio", 0)

    current_enrollments = stats.get("total_enrollments", 0)
    enrollment_change = stats.get("enrollment_change", None)  # could be None
    prev_enrollments = current_enrollments - (enrollment_change or 0)

    # Figure layout: 3 rows x 2 cols (top full-width, others split)
    fig = plt.figure(figsize=(14, 12))
    gs = gridspec.GridSpec(3, 2, height_ratios=[1.0, 0.9, 0.9], hspace=0.45, wspace=0.35)

    # -------------------------
    # Top: Overview totals bar (full width)
    # -------------------------
    ax_overview = fig.add_subplot(gs[0, :])
    categories = ["Sinh viên", "Giảng viên", "Khoa", "Khóa học"]
    values = [total_students, total_teachers, total_departments, total_courses]
    colors = ["#4CAF50", "#2196F3", "#6C5CE7", "#FFB86B"]
    bars = ax_overview.bar(categories, values, color=colors, edgecolor="black", linewidth=0.6)
    ax_overview.set_title(f"Báo cáo tổng quan hệ thống — {meta.get('report_period','')}".strip(), fontsize=16, fontweight="bold")
    ax_overview.grid(axis="y", linestyle="--", alpha=0.5)
    ax_overview.set_ylabel("Số lượng", fontsize=12)

    # Annotate bars
    for b in bars:
        h = b.get_height()
        ax_overview.text(b.get_x() + b.get_width() / 2, h + max(values)*0.01, f"{int(h):,}", ha="center", va="bottom", fontsize=10)

    # Small subtitle with ratio
    ax_overview.text(0.995, 0.02, f"SV/GV trung bình: {overall_ratio}", transform=ax_overview.transAxes,
                     ha="right", va="bottom", fontsize=10, bbox=dict(boxstyle="round", facecolor="#f0f0f0", alpha=0.6))

    # -------------------------
    # Middle-left: Student-Teacher ratio per department (horizontal bar)
    # -------------------------
    ax_ratio = fig.add_subplot(gs[1, 0])
    if departments:
        # sort by ratio desc, show top N
        sorted_depts = sorted(departments, key=lambda d: d.get("student_teacher_ratio", 0), reverse=True)
        top_n = sorted_depts[:10]
        names = [d.get("department_name", "") for d in top_n]
        ratios = [d.get("student_teacher_ratio", 0) for d in top_n]

        y_pos = range(len(names))[::-1]  # reverse for nice order
        ax_ratio.barh(y_pos, ratios, align="center", color="#5DA5FF", edgecolor="black")
        ax_ratio.set_yticks(y_pos)
        ax_ratio.set_yticklabels(names, fontsize=10)
        ax_ratio.set_xlabel("Tỷ lệ SV/GV", fontsize=11)
        ax_ratio.set_title("Tỷ lệ SV/GV theo khoa (cao → thấp)", fontsize=12, fontweight="semibold")
        ax_ratio.grid(axis="x", linestyle="--", alpha=0.4)

        # Annotate values
        for i, v in enumerate(ratios):
            ax_ratio.text(v + max(ratios)*0.01 if max(ratios) > 0 else v + 0.1, y_pos[i], f"{v}", va="center", fontsize=9)
    else:
        ax_ratio.text(0.5, 0.5, "Không có dữ liệu khoa", ha="center", va="center", fontsize=12)
        ax_ratio.set_title("Tỷ lệ SV/GV theo khoa", fontsize=12)

    # -------------------------
    # Middle-right: Grade distribution (pie or bar)
    # -------------------------
    ax_grade = fig.add_subplot(gs[1, 1])
    grade_dist = perf.get("grade_distribution", [])
    if grade_dist:
        labels = [g.get("grade") for g in grade_dist]
        counts = [g.get("count", 0) for g in grade_dist]
        # sort by grade order A,B,C,D,F if present
        order = ["A", "B", "C", "D", "F"]
        ordered = sorted(zip(labels, counts), key=lambda x: (order.index(x[0]) if x[0] in order else 999))
        labels, counts = zip(*ordered)
        colors_p = ["#2ecc71", "#3498db", "#f1c40f", "#e67e22", "#e74c3c"][:len(labels)]

        ax_grade.pie(counts, labels=labels, autopct=lambda p: f"{p:.0f}%" if p > 0 else "", startangle=90, colors=colors_p, textprops={"fontsize": 10})
        ax_grade.set_title("Phân bố điểm (đã chấm)", fontsize=12, fontweight="semibold")
        # show total graded
        total_graded = perf.get("total_graded_enrollments", 0)
        ax_grade.text(0.5, -0.12, f"Tổng số SV đã chấm: {total_graded}", ha="center", va="center", transform=ax_grade.transAxes, fontsize=10)
    else:
        ax_grade.text(0.5, 0.5, "Không có dữ liệu điểm", ha="center", va="center", fontsize=12)
        ax_grade.set_title("Phân bố điểm", fontsize=12)

    # -------------------------
    # Bottom-left: System health indicators (bar)
    # -------------------------
    ax_health = fig.add_subplot(gs[2, 0])
    health_keys = [
        ("unassigned_classes", "Lớp chưa có GV"),
        ("students_without_department", "SV chưa có khoa"),
        ("teachers_without_department", "GV chưa có khoa"),
        ("under_enrolled_classes", "Lớp thiếu SV")
    ]
    h_labels = []
    h_vals = []
    for key, label in health_keys:
        h_labels.append(label)
        h_vals.append(health.get(key, 0))

    bars_h = ax_health.barh(range(len(h_labels))[::-1], h_vals[::-1], color=["#ff6b6b", "#ffbe76", "#74b9ff", "#ffeaa7"], edgecolor="black")
    ax_health.set_yticks(range(len(h_labels))[::-1])
    ax_health.set_yticklabels(h_labels[::-1], fontsize=10)
    ax_health.set_xlabel("Số lượng", fontsize=11)
    ax_health.set_title("Chỉ số sức khỏe hệ thống", fontsize=12, fontweight="semibold")
    for i, v in enumerate(h_vals[::-1]):
        ax_health.text(v + max(h_vals)*0.01 if max(h_vals) > 0 else v + 0.1, i, f"{int(v)}", va="center", fontsize=9)

    # draw small health score badge
    health_score = health.get("health_score", None)
    if health_score is not None:
        ax_health.text(1.02, 0.5, f"Health Score\n{health_score}", transform=ax_health.transAxes, ha="left", va="center",
                       fontsize=12, fontweight="bold", bbox=dict(facecolor="#f7f7f7", edgecolor="#cccccc"))

    # -------------------------
    # Bottom-right: Enrollment trend (prev vs current) + trend label
    # -------------------------
    ax_trend = fig.add_subplot(gs[2, 1])
    try:
        prev_val = int(prev_enrollments or 0)
        curr_val = int(current_enrollments or 0)
    except Exception:
        prev_val = 0
        curr_val = current_enrollments or 0

    bar_positions = [0, 1]
    vals = [prev_val, curr_val]
    labels_tr = ["Kỳ trước", "Kỳ hiện tại"]
    trend_colors = ["#bbbbbb", "#4CAF50" if curr_val >= prev_val else "#e74c3c"]
    bars_tr = ax_trend.bar(bar_positions, vals, color=trend_colors, edgecolor="black")
    ax_trend.set_xticks(bar_positions)
    ax_trend.set_xticklabels(labels_tr, fontsize=11)
    ax_trend.set_ylabel("Số đăng ký", fontsize=11)
    ax_trend.set_title(f"Xu hướng đăng ký: {stats.get('enrollment_trend', '')}", fontsize=12, fontweight="semibold")
    for b in bars_tr:
        ax_trend.text(b.get_x() + b.get_width()/2, b.get_height() + max(vals)*0.01 if max(vals) > 0 else b.get_height() + 0.1,
                      f"{int(b.get_height()):,}", ha="center", va="bottom", fontsize=10)

    # Small note area (center bottom) with report info
    fig.text(0.5, 0.005,
             f"Tạo bởi: {meta.get('generated_by','-')} | Thời gian: {meta.get('generated_at','-')} | Kỳ: {meta.get('report_period','-')}",
             ha="center", fontsize=9, color="#666666")

    plt.tight_layout(rect=[0, 0.03, 1, 0.97])

    # Save image to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    image_bytes = buf.getvalue()

    # Encode base64 for safe JSON transport
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Save local copy
    os.makedirs(GENERATED_THUMBNAILS_DIR, exist_ok=True)
    filepath = os.path.join(GENERATED_THUMBNAILS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    response = {
        "success": True,
        "message": "Báo cáo tổng quan hệ thống (kèm biểu đồ)",
        "chart_base64": img_base64,
        "filepath": filepath,
        "artifact_filename": filename,
        "artifact_version": None,   # sẽ được callback cập nhật khi lưu artifact
        "summary": payload
    }
    return response

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