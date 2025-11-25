# whitepaper_rag

激活venv环境
source backend/venv/bin/activate
安装依赖
pip install -r backend/requirements.txt
启动项目
python -m uvicorn backend.app.main:app --reload    

运行测试
pytest

## 环境配置

### 1. 创建 `.env` 文件

在项目根目录创建 `.env`，同时供前后端读取：
```bash
# Supabase (前后端共用)
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key

# LLM API Keys
OPENAI_API_KEY=sk-xxxx
GEMINI_API_KEY=your_google_ai_studio_key

# Redis (可选，用于缓存和 Celery)
REDIS_URL=redis://localhost:6379/0

# ChromaDB (可选，默认使用持久化存储)
# CHROMA_PERSIST_DIRECTORY=backend/app/storage/chromadb  # 默认值
```

### 2. Supabase Auth 配置

- 在 Supabase 控制台开启 Google Provider
- 配置回调地址：
  - 生产环境：`https://<project>.supabase.co/auth/v1/callback`
  - 本地开发：`http://localhost:5173`

### 3. 启动服务

**后端：**
```bash
source backend/venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

**Redis（可选，用于缓存）：**
```bash
# macOS
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:7
```

## 存储说明

### ChromaDB 持久化

默认使用 **持久化存储**，embeddings 保存在 `backend/app/storage/chromadb/`，后端重启后数据不会丢失。

**优点：**
- ✅ 数据持久化，重启不丢失
- ✅ 可以使用外部脚本调试（如 `python backend/debug.py`）
- ✅ 适合生产环境

**可选配置（使用远程 ChromaDB 服务器）：**
```bash
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=false
CHROMA_SERVER_API_KEY=your_api_key  # 可选
```