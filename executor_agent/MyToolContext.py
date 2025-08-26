from typing import Dict, Any
from google.adk.tools import ToolContext
from google.adk.events import EventActions 

# --- Custom ToolContext for MCP Server ---
class SimpleToolContext(ToolContext):
    """
    Một phiên bản đơn giản hóa của ToolContext được thiết kế riêng cho MCP server.
    Nó bỏ qua sự cần thiết của một InvocationContext đầy đủ và chỉ làm việc trực tiếp với state.
    """
    def __init__(self, state: Dict[str, Any]):
        # Ghi đè phương thức khởi tạo của lớp cha
        # Chúng ta không gọi super().__init__(...) vì chúng ta không có InvocationContext
        self._state = state
        self._event_actions = EventActions() # Tạo một EventActions rỗng

    @property
    def state(self) -> Dict[str, Any]:
        """Cung cấp quyền truy cập đọc/ghi vào state."""
        return self._state

    @property
    def actions(self) -> EventActions:
        """Cung cấp quyền truy cập vào EventActions."""
        return self._event_actions

    # Bạn có thể để các phương thức khác như list_artifacts, search_memory, v.v.
    # gây ra lỗi NotImplementedError nếu chúng không được sử dụng trong MCP server này,
    # hoặc cung cấp một cài đặt giả nếu cần.
    # Ví dụ:
    async def list_artifacts(self) -> list[str]:
        raise NotImplementedError("list_artifacts không được hỗ trợ trong MCP context này.")

    async def search_memory(self, query: str):
        raise NotImplementedError("search_memory không được hỗ trợ trong MCP context này.")
