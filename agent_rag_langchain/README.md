### Run RAG Agent
```bash
cd agent_rag_langchain
uv venv
.venv\Scripts\activate
uv run --active app/__main__.py
```
### Test with postman:
- Method: POST
- URL: http://localhost:10002/
- Headers:
    Key: Content-Type; Value: application/json
- Body:
    {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "contextId": "ctx-001",
                "extensions": null,
                "kind": "message",
                "messageId": "msg-001",
                "metadata": null,
                "parts": [
                    {
                        "kind": "text",
                        "metadata":{
                            "role": "public" (root: public if role is invalid or None)
                        },
                        "text": "Thời gian đóng học phí học kì I 2025-2026"
                    }
                ],
                "referenceTaskIds": null,
                "role": "user",
                "taskId": "task-001"
            }
        },
        "id": 1
    }

Notice:
    - contextId, messageId, taskId, metadata.role, text are changeable
    - metadata.role: one of "public" || "admin" || "teacher" || "student" (default "public" if metadata.role is invalid or None)

- Example of response:
{
    "id": 1,
    "jsonrpc": "2.0",
    "result": {
        "artifacts": [
            {
                "artifactId": "682c1cdd-aae6-4186-a5ab-2e122ab6eeb5",
                "name": "rag_result",
                "parts": [
                    {
                        "kind": "text",
                        "text": "Dựa trên thông tin được cung cấp, đây là tóm tắt về thông báo:\n\n**Thông báo này được ban hành bởi:** Trường Đại học Công Thương Thành phố Hồ Chí Minh.\n\n**Ngày ban hành:** 01 tháng 7 năm 2025.\n\n**Nội dung chính:** Về việc thu học phí học kỳ 1 năm học 2025-2026.\n\n**Các thông tin chi tiết:**\n\n*   **Thời gian thu học phí:** Từ ngày 07/07/2025 đến hết ngày 15/08/2025.\n*   **Phương thức đóng:** Sinh viên đóng học phí trực tuyến thông qua cổng thu học phí online của các ngân hàng Vietcombank, Sacombank, Agribank, OCB.\n*   **Mức đóng học phí:** Sinh viên cần truy cập trang web **http://sinhvien.huit.edu.vn/** để biết mức học phí cụ thể."
                    }
                ]
            }
        ],
        "contextId": "ctx-001",
        "history": [
            {
                "contextId": "ctx-001",
                "kind": "message",
                "messageId": "msg-001",
                "parts": [
                    {
                        "kind": "text",
                        "metadata": {
                            "role": "public"
                        },
                        "text": "Thời gian đóng học phí học kì I 2025-2026"
                    }
                ],
                "role": "user",
                "taskId": "task-001"
            },
            {
                "contextId": "ctx-001",
                "kind": "message",
                "messageId": "71237ff4-5d6a-463d-8cff-30bce7055329",
                "parts": [
                    {
                        "kind": "text",
                        "text": "Đang tìm kiếm thông tin..."
                    }
                ],
                "role": "agent",
                "taskId": "task-001"
            },
            {
                "contextId": "ctx-001",
                "kind": "message",
                "messageId": "1362678c-5865-435f-8d24-0079af9fda0b",
                "parts": [
                    {
                        "kind": "text",
                        "text": "Đang xử lý dữ liệu..."
                    }
                ],
                "role": "agent",
                "taskId": "task-001"
            }
        ],
        "id": "task-001",
        "kind": "task",
        "status": {
            "state": "completed",
            "timestamp": "2025-08-15T04:33:39.414231+00:00"
        }
    }
}
