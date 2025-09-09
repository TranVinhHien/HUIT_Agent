# A2A HUIT

## Setup and Deployment

### Prerequisites

Before running the application locally, ensure you have the following installed:

1. **uv:** The Python package management tool used in this project. Follow the installation guide: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
2. **python 3.13** Python 3.13 is required to run a2a-sdk 
3. **set up .env** 

Create a `.env` file in each  of the directory with your Google API Key:
## Run the Agents

You will need to run each agent in a separate terminal window. The first time you run these commands, `uv` will create a virtual environment and install all necessary dependencies before starting the agent.

### Terminal 1: Run Text2SQL Agent
```bash
cd agent_T2SQL_langchain
uv venv
.venv\Scripts\activate
uv run --active app/__main__.py
```
```bash
cd agent_T2SQL_langchain
.venv\Scripts\activate
uv run --active app/__main__.py
```
### Terminal 2: Run executor Agent
```bash
cd executor_agent
uv venv
.venv\Scripts\activate
uv run --active .   
```
```bash
cd executor_agent
.venv\Scripts\activate
uv run --active .    
```
### Terminal 3: Run RAG Agent
```bash
cd agent_rag_langchain
uv venv
.venv\Scripts\activate
uv run --active app/__main__.py

```
```bash
cd agent_rag_langchain
.venv\Scripts\activate
uv run --active app/__main__.py
  
```

### Terminal 4: Run Host Agent
```bash
cd agent_host_adk
uv venv
.venv\Scripts\activate
uv run uvicorn host:app --host 0.0.0.0 --port 9000 --reload      
```
```bash
cd agent_host_adk
.venv\Scripts\activate
uv run uvicorn host:app --host 0.0.0.0 --port 9000 --reload      
```

### Terminal 5: Run chart Agent
```bash
cd agent_chart
uv venv
.venv\Scripts\activate
uv run --active .   
```
```bash
cd agent_chart
.venv\Scripts\activate
uv run --active .    
```

## Interact with the Host Agent

sudo docker-compose down -v --rmi all
sudo docker-compose build --no-cache
sudo docker-compose up



Once all agents are running, the host agent will begin the scheduling process. You can view the interaction in the terminal output of the `host_agent`.
run all sub agent before run host agent
## References
- https://github.com/google/a2a-python
- https://codelabs.developers.google.com/intro-a2a-purchasing-concierge#1

Trước khi run host agent bạn phải tạo ra csdl mysql với cấu hình:
MONGO_URI = "mysql+pymysql://root:12345@172.26.127.95/session_db" 

Sau đó thực hiện chạy host agent với lệnh như trên
"# TrienKhaiAgent" 
