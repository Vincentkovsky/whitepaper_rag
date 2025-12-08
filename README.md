# Prism 🌈

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![React](https://img.shields.io/badge/react-18.0+-61DAFB.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-009688.svg)

**Prism** is an advanced AI-powered research assistant and RAG (Retrieval-Augmented Generation) platform. It combines a powerful **ReAct Agent** with document intelligence and real-time web search to provide accurate, cited, and reasoning-backed answers to complex queries.

---

## ✨ Key Features

### 🧠 Intelligent Agentic Workflow
- **ReAct Architecture**: Utilizes a custom-built Reason+Act loop to break down complex questions into sub-tasks (Thought → Action → Observation).
- **Tool Use**: Autonomous dynamic tool selection between **Document Search** (internal knowledge) and **Web Search** (real-time internet data).
- **Streaming Thoughts**: Visualizes the agent's "thinking process" in real-time via Server-Sent Events (SSE).

### 📚 RAG & Document Intelligence
- **PDF Ingestion**: Upload and parse technical documents, whitepapers, and reports.
- **True Hybrid Search**: Combines **Vector Search** (ChromaDB semantic embeddings) + **BM25** (keyword-based ranking) for maximum recall.
- **Intelligent Reranking**: Section-aware algorithm that boosts core sections (Abstract, Introduction, Conclusion) and respects document structure.
- **Context-Aware**: Intelligently blends retrieved context with LLM knowledge.

### 🔍 Interactive Citations
- **Source Transparency**: Every fact is backed by a verified source (Web or PDF).
- **Rich Tooltips**: Hover over citations `[1]` to see the exact source title, URL, page number, and relevant text snippet.
- **Click-to-Nav**: Direct links to external URLs or internal document viewers.

### 🎨 Modern Frontend Experience
- **Fluid UI**: Built with React, Tailwind CSS, and Framer Motion for smooth animations.
- **Latex & Markdown**: Full support for rendering complex mathematical formulas ($E=mc^2$) and structured tables.
- **Chat Management**: Persistent conversation history and session management.

### 📄 Document Management
- **Multi-format Upload**: Support for PDF documents with automatic parsing and indexing.
- **Smart Organization**: Documents are automatically chunked and embedded for efficient retrieval.
- **User Isolation**: Each user has their own document workspace with secure access controls.

### 💳 Subscription & Admin
- **Subscription Tiers**: Flexible subscription management for different user tiers.
- **Admin Dashboard**: Comprehensive admin panel for user management and system monitoring.
- **Usage Analytics**: Track API usage, document uploads, and query patterns.

---

## 🛠️ Technical Architecture

### Backend Stack
- **Framework**: FastAPI (Async Python)
- **LLM Orchestration**: Custom Agent implementation (Lightweight, non-LangChain dependent core)
- **Vector Store**: ChromaDB (Local persistence)
- **Auth**: JWT / OAuth
- **Task Queue**: Celery + Redis (for background document processing)

### Frontend Stack
- **Core**: React 18 + Vite
- **Styling**: Tailwind CSS + Typography plugin
- **State Management**: Zustand
- **Streaming**: Native EventSource for SSE handling
- **Markdown**: `react-markdown`, `remark-math`, `rehype-katex`

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 16+
- Docker (optional, for Redis)
- LLM API Key (OpenAI or Gemini)

### 1. Environment Configuration
Create a `.env` file in the root directory:

```bash
# Core Config
PROJECT_ROOT=/absolute/path/to/project

# LLM Providers
OPENAI_API_KEY=sk-xxxx
GEMINI_API_KEY=your_key

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
> **Note**: For background tasks like document indexing, ensure Redis is running (`brew install redis` or via Docker).

### 3. Frontend Setup
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Dev Server
npm run dev
```

---

## 📂 Project Structure

```
Prism/
├── backend/
│   ├── app/
│   │   ├── agent/              # Agent Logic (ReAct loop, Tools, Prompts)
│   │   ├── api/
│   │   │   └── routes/         # API Endpoints
│   │   │       ├── agent.py    # Chat streaming & agentic workflow
│   │   │       ├── auth.py     # Authentication (login, register, OAuth)
│   │   │       ├── documents.py # Document upload & management
│   │   │       ├── qa.py       # Q&A endpoints
│   │   │       ├── admin.py    # Admin panel APIs
│   │   │       └── subscription.py # Subscription management
│   │   ├── services/           # Core Services
│   │   │   ├── rag_service.py  # RAG orchestration
│   │   │   ├── llm_client.py   # LLM provider abstraction
│   │   │   └── storage_service.py # File & vector storage
│   │   └── tools/              # Agent Tools (Web Search, Doc Search)
│   └── storage/                # ChromaDB + uploaded files
├── frontend/
│   ├── src/
│   │   ├── components/         # Reusable UI Components
│   │   ├── pages/
│   │   │   ├── ChatWorkbench.tsx  # Main chat interface
│   │   │   ├── Documents.tsx      # Document library
│   │   │   ├── Subscription.tsx   # Subscription management
│   │   │   └── admin/             # Admin dashboard
│   │   ├── services/           # API Clients & SSE Handler
│   │   ├── stores/             # Zustand state management
│   │   └── utils/              # Parsers (Citation, Markdown)
└── README.md
```

---

## 🔧 Development Notes

### Citation System
- **Backend Format**: The agent generates citations as `[[citation:1]]`, `[[citation:2]]` etc.
- **Frontend Parsing**: `citationParser.ts` extracts citations and replaces them with numbered badges `[1]` `[2]`.
- **Metadata Lookup**: Citations are matched with source data (title, URL, snippet) via `documentId` key.

### Streaming Architecture
The `/chat/stream` endpoint uses Server-Sent Events (SSE) for real-time updates:

```typescript
// Event Types
"thinking"     → Agent reasoning step (thought, action, observation)
"tool_use"     → Tool execution (web_search, document_search)
"answer"       → Final response with citations metadata
"error"        → Error messages
```

### API Routes Overview

| Route | Method | Description |
|-------|--------|-------------|
| `/api/auth/register` | POST | Create new user account |
| `/api/auth/login` | POST | Login with email/password |
| `/api/auth/google/login` | GET | OAuth2 login flow |
| `/api/documents/upload` | POST | Upload PDF document |
| `/api/documents` | GET | List user documents |
| `/api/chat/stream` | POST | Streaming chat endpoint |
| `/api/qa/ask` | POST | Non-streaming Q&A |
| `/api/admin/users` | GET | Admin: list users |
| `/api/subscription/status` | GET | Check subscription status |

### Testing

```bash
# Frontend tests (React components, Markdown rendering)
cd frontend && npm test

# Backend tests (if configured)
cd backend && pytest
```

---

## 🚢 Deployment

### Production Checklist
- [ ] Set production environment variables (`OPENAI_API_KEY`, `REDIS_URL`)
- [ ] Configure CORS allowed origins in `backend/app/main.py`
- [ ] Set up persistent storage for ChromaDB (avoid ephemeral containers)
- [ ] Enable SSL/TLS for API endpoints
- [ ] Set up monitoring (error tracking, performance metrics)

### Recommended Stack
- **Backend**: Railway / Render / AWS Lambda
- **Frontend**: Vercel / Netlify
- **Database**: Managed PostgreSQL (if adding SQL features)
- **Redis**: Redis Cloud / AWS ElastiCache
- **Storage**: S3 / CloudFlare R2 (for uploaded documents)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License
MIT © 2024 Prism Team
