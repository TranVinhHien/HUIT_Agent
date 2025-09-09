import uvicorn
from host import app
from dotenv import load_dotenv
import os
load_dotenv()
port = os.getenv("PORT", 9000)
if __name__ == '__main__':
    print("Starting Agent Host FastAPI Server...")
    uvicorn.run(
        "host:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )