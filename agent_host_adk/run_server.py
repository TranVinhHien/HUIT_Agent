import uvicorn
from host import app

if __name__ == '__main__':
    print("Starting Agent Host FastAPI Server...")
    uvicorn.run(
        "host:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )