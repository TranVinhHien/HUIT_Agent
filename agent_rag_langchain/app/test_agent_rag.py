import requests
import json

def send_post_request(role, text, url="http://localhost:10002/"):
    # Tạo JSON body với các giá trị role và text có thể thay đổi
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "contextId": "ctx-001",
                "extensions": None,
                "kind": "message",
                "messageId": "msg-001",
                "metadata": None,
                "parts": [
                    {
                        "kind": "text",
                        "metadata": {
                            "role": role
                        },
                        "text": text
                    }
                ],
                "referenceTaskIds": None,
                "role": "user",
                "taskId": "task-001"
            }
        },
        "id": 1
    }

    # Gửi yêu cầu POST
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Kiểm tra lỗi HTTP
        return response.json()  # Trả về phản hồi dạng JSON
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gửi yêu cầu: {e}")
        return None

def extract_artifact_text(response):
    # Trích xuất các giá trị text từ result.artifacts[].parts[].text
    if not response or "result" not in response or "artifacts" not in response["result"]:
        return []
    
    text_values = []
    for artifact in response["result"]["artifacts"]:
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and "text" in part:
                text_values.append(part["text"])
    
    return text_values

def print_text_as_bullets(text_values):
    # In các giá trị text dưới dạng gạch đầu dòng
    if not text_values:
        print("Không tìm thấy giá trị text trong artifacts.")
        return
    
    print("Các giá trị text trong artifacts:")
    for text in text_values:
        print(f"- {text}")

def test_post_request():
    # Trường hợp kiểm thử 1: role = "teacher", text = "Giới thiệu sơ lược khoa cơ khí"
    role = "teacher"
    text = "Giới thiệu sơ lược khoa cơ khí"
    print(f"\nKiểm thử với role = {role}, text = {text}")
    result = send_post_request(role, text)
    if result:
        text_values = extract_artifact_text(result)
        print_text_as_bullets(text_values)

    # Trường hợp kiểm thử 2: role = "student", text = "Thông tin về khoa điện"
    role = "public"
    text = "Giới thiệu sơ lược khoa cơ khí"
    print(f"\nKiểm thử với role = {role}, text = {text}")
    result = send_post_request(role, text)
    if result:
        text_values = extract_artifact_text(result)
        print_text_as_bullets(text_values)

if __name__ == "__main__":
    test_post_request()