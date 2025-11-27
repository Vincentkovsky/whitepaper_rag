# Blockchain Whitepaper RAG Analyzer

基于 RAG (Retrieval-Augmented Generation) 的区块链白皮书智能分析系统。

## 功能特性

- 📄 **文档上传** - 支持 PDF 上传和 URL 抓取
- 💬 **智能问答** - 基于文档内容的 RAG 问答
- 📊 **深度分析** - 多维度白皮书分析报告
- 🔐 **用户认证** - Supabase Auth 集成
- 📈 **质量评估** - RAGAS 框架评估 RAG 效果

## 技术栈

**后端：** FastAPI + Celery + ChromaDB + OpenAI/Gemini  
**前端：** Vue 3 + TypeScript + Element Plus  
**数据库：** Supabase PostgreSQL + Redis  
**AI：** LangGraph 工作流 + RAG Pipeline

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd blockchain_RAG

# 创建虚拟环境
python -m venv backend/venv
source backend/venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```bash
# Supabase
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# LLM Provider (openai 或 gemini)
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini

# API Keys
OPENAI_API_KEY=sk-xxxx
GEMINI_API_KEY=your_google_ai_studio_key

# Gemini 模型配置
GEMINI_MODEL_PRO=gemini-2.5-pro
GEMINI_MODEL_FLASH=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Redis (可选)
REDIS_URL=redis://localhost:6379/0
```

### 3. 启动服务

**后端：**
```bash
source backend/venv/bin/activate
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

## RAG 评估

使用 RAGAS 框架评估 RAG 管道质量：

```bash
# 运行完整评估（30 个问题）
python backend/evaluate_rag.py

# 快速测试（5 个问题）
python backend/evaluate_rag.py --sample 5

# 跳过 ground truth 评估
python backend/evaluate_rag.py --no-ground-truth
```

**评估指标：**
| 指标 | 说明 | 目标值 |
|------|------|--------|
| Faithfulness | 答案是否忠于上下文 | > 80% |
| Response Relevancy | 答案与问题的相关性 | > 80% |
| Context Precision | 检索上下文的精准度 | > 70% |
| Context Recall | 上下文覆盖率 | > 70% |

## 项目结构

```
blockchain_RAG/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # API 路由
│   │   ├── services/        # 业务逻辑
│   │   │   ├── rag_service.py        # RAG 问答
│   │   │   ├── chunking_service.py   # 文档分块
│   │   │   ├── embedding_service.py  # 向量化
│   │   │   └── evaluation_service.py # RAGAS 评估
│   │   ├── tasks/           # Celery 任务
│   │   └── workflows/       # LangGraph 工作流
│   ├── evaluate_rag.py      # 评估脚本
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/      # Vue 组件
│       └── api.ts           # API 客户端
└── .env                     # 环境配置
```

## 存储说明

### ChromaDB 持久化

默认使用持久化存储，embeddings 保存在 `backend/app/storage/chromadb/`。

**可选：使用远程 ChromaDB 服务器**
```bash
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=false
CHROMA_SERVER_API_KEY=your_api_key
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest backend/tests/test_rag_service.py -v
```

## License

MIT
