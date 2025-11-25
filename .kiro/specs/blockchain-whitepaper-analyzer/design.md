# 设计文档

## 系统架构

### 整体架构

系统采用前后端分离的微服务架构，主要分为以下几层：

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Vue 3)                        │
│  - 用户界面  - 文件上传  - 实时通知  - 数据可视化           │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTPS/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                     API 网关层 (FastAPI)                     │
│  - 路由  - 认证  - 限流  - 请求验证  - API 文档              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        业务逻辑层                            │
│  - 文档管理  - 用户管理  - 订阅管理  - 分析服务              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────┬──────────────────┬──────────────────────┐
│   AI 处理层      │   任务队列层      │    数据层            │
│  - LangGraph     │  - Celery        │  - Supabase          │
│  - OpenAI API    │  - Redis         │  - Chroma            │
│  - RAG 工作流    │  - 异步任务      │  - Storage           │
└──────────────────┴──────────────────┴──────────────────────┘
```

### 技术栈映射

**前端:**
- 框架: Vue 3 + TypeScript + Vite
- UI 库: Element Plus
- 状态管理: Pinia
- HTTP 客户端: Axios
- WebSocket: Socket.io-client
- Markdown 渲染: markdown-it
- 图表: ECharts

**后端:**
- Web 框架: FastAPI
- 异步任务: Celery + Redis
- AI 框架: LangGraph + LangChain
- LLM: OpenAI GPT-4-Turbo / GPT-4o-mini
- 文档解析: Unstructured + PyMuPDF
- 网页抓取: BeautifulSoup4 + Requests / Playwright

**数据存储:**
- 业务数据库: Supabase PostgreSQL
- 向量数据库: Chroma
- 缓存/队列: Redis
- 文件存储: Supabase Storage

**SaaS 基础设施:**
- 认证: Supabase Auth
- 支付: Lemon Squeezy
- 监控: Sentry
- 分析: PostHog

## 核心组件设计

### 1. 文档处理服务 (Document Service)

**职责:** 处理文档上传、解析、向量化

**组件结构:**
```python
class DocumentService:
    - upload_pdf(file, user_id) -> document_id
    - submit_url(url, user_id) -> document_id
    - parse_document(document_id) -> task_id
    - get_document_status(document_id) -> status
    - delete_document(document_id, user_id) -> bool
```

**文档解析流程:**

```
1. 接收文档 (PDF 或 URL)
   ↓
2. 验证格式和权限
   ↓
3. 创建异步解析任务
   ↓
4. 提取文本内容
   - PDF: Unstructured + PyMuPDF
   - 网页: BeautifulSoup4 / Playwright
   ↓
5. 文档结构识别与元素分类
   - 使用 Unstructured 解析为元素列表 (Elements)
   - 识别元素类型: Title (H1/H2/H3), NarrativeText, Table, ListItem
   - 构建文档层级结构树 (标题路径)
   ↓
6. 智能分块 (Semantic Chunking)
   
   【策略一：语义分块 - 按标题分组】
   a) 遍历元素列表，按 Title 元素进行逻辑章节分组
      例如: "2. Tokenomics" 及其后续内容归为一个章节
   
   b) 构建章节路径（面包屑）
      例如: "2. Tokenomics -> 2.1. Token Distribution"
   
   c) 检查章节大小（使用 tiktoken 计算 tokens）
      - 如果章节 ≤ 1000 tokens: 保持完整
      - 如果章节 > 1000 tokens: 使用 RecursiveCharacterTextSplitter 切分
        * chunk_size: 1000 tokens
        * chunk_overlap: 100 tokens
   
   d) 上下文增强 (Contextual Enrichment)
      为每个子块注入章节路径信息:
      格式: "Section: 2. Tokenomics -> 2.1. Token Distribution\n\n{content}"
   
   【策略二：表格特殊处理】
   a) 识别 Table 元素，不进行切割
   
   b) 表格转换
      - Unstructured 提取的 HTML 表格 → Markdown 格式
      - 使用 tabulate 或自定义转换器
   
   c) 表格摘要生成（高级优化）
      - 使用 GPT-4o-mini 生成表格摘要
      - Prompt: "Summarize this table in 2-3 sentences: {table_markdown}"
   
   d) 存储格式
      文本: "Summary: {摘要}\n\nTable:\n{markdown_table}"
      元数据: {"element_type": "table", "section_path": "..."}
   ↓
7. 向量化 (Embedding)
   - 模型: text-embedding-3-large
   - 批量处理: 100 chunks/batch
   - 对表格块和文本块统一向量化
   ↓
8. 存储到 Chroma（单一 Collection）
   - Collection 名称: "documents"（所有文档共享）
   - 全局唯一 ID: f"{document_id}_chunk_{index}"
   - ⭐ 关键元数据（用于多租户隔离）:
     * user_id: 用户 ID（必需，用于数据隔离）
     * document_id: 文档 ID（必需，用于文档隔离）
   - 其他元数据:
     * section_path: 章节路径
     * page_number: 页码
     * chunk_index: 块索引
     * element_type: 元素类型 (text/table)
     * token_count: token 数量
     * created_at: 创建时间
   ↓
9. 更新文档状态为 "已完成"
```

**分块实现示例:**

```python
import re
import tiktoken
from unstructured.partition.pdf import partition_pdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

class SemanticChunker:
    def __init__(self):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=lambda x: len(self.tokenizer.encode(x))
        )
        self.openai = OpenAI()
    
    def parse_document(self, pdf_path):
        """解析文档为元素列表"""
        elements = partition_pdf(pdf_path, strategy="hi_res")
        return elements
    
    def build_sections(self, elements):
        """按标题构建逻辑章节"""
        sections = []
        current_section = {"path": [], "content": [], "tables": []}
        
        for elem in elements:
            if elem.category == "Title":
                # 保存上一个章节
                if current_section["content"] or current_section["tables"]:
                    sections.append(current_section)
                
                # 开始新章节
                current_section = {
                    "path": self._update_path(current_section["path"], elem.text),
                    "content": [],
                    "tables": []
                }
            
            elif elem.category == "Table":
                # 表格单独处理
                current_section["tables"].append(elem)
            
            else:
                # 普通文本内容
                current_section["content"].append(elem.text)
        
        # 添加最后一个章节
        if current_section["content"] or current_section["tables"]:
            sections.append(current_section)
        
        return sections
    
    def chunk_sections(self, sections):
        """对章节进行智能分块"""
        chunks = []
        
        for section in sections:
            section_path = " -> ".join(section["path"])
            
            # 处理文本内容
            text_content = "\n\n".join(section["content"])
            token_count = len(self.tokenizer.encode(text_content))
            
            if token_count <= 1000:
                # 章节足够小，保持完整
                chunks.append({
                    "text": f"Section: {section_path}\n\n{text_content}",
                    "metadata": {
                        "section_path": section_path,
                        "element_type": "text",
                        "token_count": token_count
                    }
                })
            else:
                # 章节过大，需要切分
                sub_chunks = self.splitter.split_text(text_content)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunks.append({
                        "text": f"Section: {section_path}\n\n{sub_chunk}",
                        "metadata": {
                            "section_path": section_path,
                            "element_type": "text",
                            "chunk_index": i,
                            "token_count": len(self.tokenizer.encode(sub_chunk))
                        }
                    })
            
            # 处理表格
            for table in section["tables"]:
                table_markdown = self._html_to_markdown(table.metadata.text_as_html)
                table_summary = self._generate_table_summary(table_markdown)
                
                chunks.append({
                    "text": f"Section: {section_path}\n\nSummary: {table_summary}\n\nTable:\n{table_markdown}",
                    "metadata": {
                        "section_path": section_path,
                        "element_type": "table",
                        "has_summary": True
                    }
                })
        
        return chunks
    
    def _generate_table_summary(self, table_markdown):
        """使用 LLM 生成表格摘要"""
        response = self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Summarize this table in 2-3 sentences:\n\n{table_markdown}"
            }],
            max_tokens=100
        )
        return response.choices[0].message.content
    
    def _html_to_markdown(self, html):
        """将 HTML 表格转换为 Markdown"""
        from bs4 import BeautifulSoup
        import pandas as pd
        
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        df = pd.read_html(str(table))[0]
        return df.to_markdown(index=False)
    
    def _update_path(self, current_path, title):
        """根据标题级别更新章节路径"""
        level = self._infer_title_level(title)
        # 截断到当前层级的父节点，再追加新标题
        new_path = current_path[:level-1]
        new_path.append(title.strip())
        return new_path
    
    def _infer_title_level(self, title: str) -> int:
        """简单推断标题层级（H1/H2/H3...），默认返回 1"""
        # 示例策略：根据前缀编号或 Markdown # 数量判断
        if title.startswith("###"):
            return 3
        if title.startswith("##"):
            return 2
        if title.startswith("#"):
            return 1
        # 类似 "2.1. Token Distribution" 的情况
        if re.match(r"\d+(\.\d+)+", title.strip()):
            return title.count(".") + 1
        return 1
```

**使用示例:**
```python
chunker = SemanticChunker()

# 0. 获取单一共享 Collection
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("documents")

# 1. 解析文档
elements = chunker.parse_document("whitepaper.pdf")

# 2. 构建章节
sections = chunker.build_sections(elements)

# 3. 智能分块
chunks = chunker.chunk_sections(sections)

# 4. 向量化并存储到单一 Collection
for i, chunk in enumerate(chunks):
    embedding = generate_embedding(chunk["text"])
    
    # ⭐ 添加 user_id 和 document_id 到元数据
    metadata = {
        **chunk["metadata"],
        "user_id": user_id,        # 用户隔离
        "document_id": document_id, # 文档隔离
        "created_at": datetime.now().isoformat()
    }
    
    collection.add(
        documents=[chunk["text"]],
        embeddings=[embedding],
        metadatas=[metadata],
        ids=[f"{document_id}_chunk_{i}"]  # 全局唯一 ID
    )
```

### 2. RAG 查询服务 (RAG Service)

**职责:** 处理用户问答请求

**组件结构:**
```python
class RAGService:
    - query(question, document_id, user_id, model="mini") -> answer
    - get_relevant_chunks(question, document_id, user_id, k=10) -> chunks
    - rerank_chunks(question, chunks) -> ranked_chunks
    - build_context(chunks, max_tokens=2000) -> context
    - generate_answer(question, context, model) -> answer
    - batch_query(document_id, user_id, questions, k=5) -> List[chunks]  # 用于分析服务
```

**RAG 查询流程:**

```
用户问题
   ↓
[缓存检查] → Redis (命中则直接返回)
   ↓ (未命中)
[问题向量化] → text-embedding-3-large
   ↓
[向量检索] → Chroma.query(
                where={"user_id": user_id, "document_id": doc_id},
                n_results=10
              )
   ↓
[重排序] → 按相关性和章节连贯性排序
   ↓
[上下文构建] → 拼接 Top-5 chunks (限制 2000 tokens)
   ↓
[LLM 生成] → GPT-4o-mini (默认) / GPT-4-Turbo (深度模式)
   ↓
[答案后处理] → 添加引用来源 (section_path, page_number)
   ↓
[缓存] → Redis (key: hash(question+doc_id), ttl: 1小时)
   ↓
返回答案
```

**完整实现:**

```python
import json
import hashlib
from typing import List, Dict
from openai import OpenAI
import chromadb

class RAGService:
    def __init__(self, chroma_client, redis_client, openai_client):
        self.chroma = chroma_client
        self.redis = redis_client
        self.openai = openai_client
        self.collection = self.chroma.get_collection("documents")
    
    def query(
        self, 
        question: str, 
        document_id: str, 
        user_id: str,
        model: str = "mini"  # "mini" 或 "turbo"
    ) -> Dict:
        """
        处理用户问答请求
        
        Args:
            question: 用户问题
            document_id: 文档 ID
            user_id: 用户 ID
            model: LLM 模型选择 ("mini" 或 "turbo")
        
        Returns:
            {
                "answer": "...",
                "sources": [...],
                "cached": bool,
                "model_used": "gpt-4o-mini"
            }
        """
        # 1. 检查缓存
        cache_key = self._get_cache_key(question, document_id)
        cached_answer = self.redis.get(cache_key)
        
        if cached_answer:
            return {
                **json.loads(cached_answer),
                "cached": True
            }
        
        # 2. 获取相关上下文
        chunks = self.get_relevant_chunks(
            question=question,
            document_id=document_id,
            user_id=user_id,
            k=10
        )
        
        if not chunks:
            return {
                "answer": "抱歉，我在文档中没有找到相关信息来回答这个问题。",
                "sources": [],
                "cached": False,
                "model_used": None
            }
        
        # 3. 重排序
        ranked_chunks = self.rerank_chunks(question, chunks)
        
        # 4. 构建上下文
        context = self.build_context(ranked_chunks[:5], max_tokens=2000)
        
        # 5. 生成答案
        answer_data = self.generate_answer(question, context, model)
        
        # 6. 添加来源信息
        sources = [
            {
                "section": chunk["metadata"]["section_path"],
                "page": chunk["metadata"].get("page_number"),
                "text": chunk["text"][:200] + "..."
            }
            for chunk in ranked_chunks[:3]
        ]
        
        result = {
            "answer": answer_data["answer"],
            "sources": sources,
            "cached": False,
            "model_used": answer_data["model"]
        }
        
        # 7. 缓存结果
        self.redis.setex(
            cache_key,
            3600,  # 1小时
            json.dumps(result)
        )
        
        return result
    
    def get_relevant_chunks(
        self,
        question: str,
        document_id: str,
        user_id: str,
        k: int = 10
    ) -> List[Dict]:
        """
        检索相关文档块
        
        使用元数据过滤确保多租户隔离
        """
        # 向量化问题
        embedding = self.openai.embeddings.create(
            model="text-embedding-3-large",
            input=question
        ).data[0].embedding
        
        # 向量检索（带多租户过滤）
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where={
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$eq": document_id}}
                ]
            },
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化结果
        chunks = []
        for i in range(len(results["ids"][0])):
            chunks.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        
        return chunks
    
    def rerank_chunks(self, question: str, chunks: List[Dict]) -> List[Dict]:
        """
        重排序检索结果
        
        策略:
        1. 优先考虑相似度（distance 越小越好）
        2. 同一章节的块聚合在一起（保持上下文连贯性）
        3. 表格块优先级略高（通常包含关键数据）
        """
        # 按章节分组
        section_groups = {}
        for chunk in chunks:
            section = chunk["metadata"].get("section_path", "unknown")
            if section not in section_groups:
                section_groups[section] = []
            section_groups[section].append(chunk)
        
        # 计算每个章节的平均相似度
        section_scores = {}
        for section, section_chunks in section_groups.items():
            avg_distance = sum(c["distance"] for c in section_chunks) / len(section_chunks)
            has_table = any(c["metadata"].get("element_type") == "table" for c in section_chunks)
            
            # 表格章节得分加成
            score = avg_distance * (0.9 if has_table else 1.0)
            section_scores[section] = score
        
        # 按章节得分排序
        sorted_sections = sorted(section_scores.items(), key=lambda x: x[1])
        
        # 重新组织块：优先章节的块排在前面
        reranked = []
        for section, _ in sorted_sections:
            section_chunks = sorted(
                section_groups[section],
                key=lambda x: x.get("metadata", {}).get("chunk_index", 0)
            )
            reranked.extend(section_chunks)
        
        return reranked
    
    def build_context(self, chunks: List[Dict], max_tokens: int = 2000) -> str:
        """
        构建上下文字符串
        
        限制 token 数量，避免超出 LLM 上下文窗口
        """
        import tiktoken
        tokenizer = tiktoken.get_encoding("cl100k_base")
        
        context_parts = []
        total_tokens = 0
        
        for chunk in chunks:
            chunk_text = f"[来源: {chunk['metadata']['section_path']}]\n{chunk['text']}\n"
            chunk_tokens = len(tokenizer.encode(chunk_text))
            
            if total_tokens + chunk_tokens > max_tokens:
                break
            
            context_parts.append(chunk_text)
            total_tokens += chunk_tokens
        
        return "\n---\n\n".join(context_parts)
    
    def generate_answer(
        self,
        question: str,
        context: str,
        model: str = "mini"
    ) -> Dict:
        """
        使用 LLM 生成答案
        
        Args:
            question: 用户问题
            context: 检索到的上下文
            model: "mini" (GPT-4o-mini) 或 "turbo" (GPT-4-Turbo)
        """
        model_map = {
            "mini": "gpt-4o-mini",
            "turbo": "gpt-4-turbo"
        }
        
        model_name = model_map.get(model, "gpt-4o-mini")
        
        prompt = f"""
        你是一个专业的区块链白皮书分析助手。基于以下上下文回答用户问题。
        
        要求:
        1. 只基于提供的上下文回答，不要编造信息
        2. 如果上下文中没有相关信息，明确说明
        3. 回答要准确、简洁、专业
        4. 如果涉及技术细节，提供清晰的解释
        
        上下文:
        {context}
        
        用户问题: {question}
        
        回答:
        """
        
        response = self.openai.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3  # 降低随机性，提高准确性
        )
        
        return {
            "answer": response.choices[0].message.content,
            "model": model_name
        }
    
    def batch_query(
        self,
        document_id: str,
        user_id: str,
        questions: List[str],
        k: int = 5
    ) -> List[str]:
        """
        批量查询（用于分析服务）
        
        为多个问题检索相关块，返回去重后的文本列表
        """
        all_chunks = []
        
        for question in questions:
            chunks = self.get_relevant_chunks(
                question=question,
                document_id=document_id,
                user_id=user_id,
                k=k
            )
            all_chunks.extend(chunks)
        
        # 去重（基于 chunk ID）
        unique_chunks = {chunk["id"]: chunk for chunk in all_chunks}.values()
        
        # 返回文本列表
        return [chunk["text"] for chunk in unique_chunks]
    
    def _get_cache_key(self, question: str, document_id: str) -> str:
        """生成缓存键"""
        content = f"{document_id}:{question}"
        return f"qa:{hashlib.md5(content.encode()).hexdigest()}"
```

**使用示例:**

```python
# 初始化服务
rag_service = RAGService(chroma_client, redis_client, openai_client)

# 简单问答（使用 mini 模型，低成本）
result = rag_service.query(
    question="这个项目的共识机制是什么？",
    document_id="doc_uuid",
    user_id="user_uuid",
    model="mini"
)

print(result["answer"])
print(f"来源: {result['sources'][0]['section']}")
print(f"使用模型: {result['model_used']}")
print(f"缓存命中: {result['cached']}")

# 深度问答（使用 turbo 模型，高质量）
result = rag_service.query(
    question="详细分析该项目的经济模型设计及其可持续性",
    document_id="doc_uuid",
    user_id="user_uuid",
    model="turbo"
)
```

**成本优化策略:**

1. **双模型策略**
   - 简单问答: GPT-4o-mini ($0.0006/次)
   - 复杂分析: GPT-4-Turbo ($0.036/次)
   - 让用户选择或自动判断复杂度

2. **激进缓存**
   - 相同问题 1 小时内直接返回缓存
   - 缓存命中率目标: 40%+
   - 节省成本: ~40%

3. **上下文限制**
   - 限制 2000 tokens 上下文
   - 避免超长输入导致成本激增

4. **批量检索优化**
   - `batch_query` 方法支持分析服务
   - 一次检索多个问题，去重后返回

### 3. 分析报告服务 (Analysis Service)

**职责:** 生成多维度分析报告

**⚠️ 性能陷阱警告:**
天真的并行分析设计会将整个白皮书文本发送给每个分析节点，导致：
- 巨大的 token 成本（每个维度都消耗完整文档的 tokens）
- 严重的延迟（LLM 处理大量无关上下文）
- 低质量输出（信息过载导致 LLM 抓不住重点）

**✅ 优化方案: "RAG-in-Graph" (图内 RAG)**

AnalysisService 不是"阅读器"，而是"智能协调器"。它协调 RAG 流程，只将相关上下文发送给分析节点。

**组件结构:**
```python
class AnalysisService:
    - generate_report(document_id, user_id) -> task_id
    - generate_sub_queries(dimensions) -> Dict[str, List[str]]
    - batch_retrieve_contexts(document_id, sub_queries) -> Dict[str, str]
    - analyze_dimension(dimension, context, queries) -> str
    - synthesize_report(analyses) -> Dict
```

**优化的 LangGraph 工作流 (4 步流程):**

```
Plan (规划) → Retrieve (检索) → Analyze (并行分析) → Synthesize (综合)
     ↓              ↓                    ↓                    ↓
  生成子问题      批量 RAG          小上下文分析          合并报告
  (1次 mini)    (无 LLM 调用)      (4次 turbo)         (1次 mini)
```

**完整实现:**

```python
import json
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict

# 状态定义
class AnalysisState(TypedDict):
    document_id: str
    user_id: str
    dimensions: List[str]                  # ["tech", "econ", "team", "risk"]
    sub_queries: Dict[str, List[str]]      # {"tech": ["q1", "q2"], ...}
    retrieved_contexts: Dict[str, str]     # {"tech": "context...", ...}
    analysis_results: Dict[str, str]       # {"tech": "report...", ...}
    final_report: Dict                      # {"report": "...", "score": 90}

# --- 节点 1: 规划 (Planner) ---
# 成本: ~$0.0003 (GPT-4o-mini, 500 tokens)
def make_generate_sub_queries(openai_client):
    def generate_sub_queries(state: AnalysisState) -> Dict:
    """为每个分析维度生成 3-5 个关键问题"""
    dimensions = state["dimensions"]
    
    prompt = f"""
    为区块链白皮书分析生成针对性问题。
    
    分析维度: {dimensions}
    
    为每个维度生成 3-5 个关键问题，用于从白皮书中检索相关信息。
    问题应该具体、可回答，聚焦于该维度的核心要素。
    
    返回 JSON 格式:
    {{
        "tech": ["问题1", "问题2", ...],
        "econ": ["问题1", "问题2", ...],
        ...
    }}
    """
    
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        
        queries = json.loads(response.choices[0].message.content)
        return {"sub_queries": queries}
    
    return generate_sub_queries

# --- 节点 2: 检索 (Retriever) ---
# 成本: ~$0 (仅向量检索，无 LLM 调用)
def make_retrieve_all_contexts(rag_service):
    """通过闭包注入 rag_service，避免依赖全局变量"""
    def retrieve_all_contexts(state: AnalysisState) -> Dict:
        """批量检索所有维度的相关上下文"""
        document_id = state["document_id"]
        user_id = state["user_id"]
        sub_queries = state["sub_queries"]
        
        all_contexts = {}
        
        for dimension, queries in sub_queries.items():
            # 批量 RAG 查询
            all_chunks = []
            for query in queries:
                # 向量检索 (使用之前优化的 where 过滤器)
                chunks = rag_service.get_relevant_chunks(
                    question=query,
                    document_id=document_id,
                    user_id=user_id,
                    k=5
                )
                all_chunks.extend(chunks)
            
            # 去重并合并上下文
            unique_chunks = {chunk["id"]: chunk for chunk in all_chunks}.values()
            context = "\n\n---\n\n".join([
                f"[来源: {c['metadata']['section_path']}]\n{c['text']}"
                for c in unique_chunks
            ])
            
            all_contexts[dimension] = context
        
        return {"retrieved_contexts": all_contexts}
    
    return retrieve_all_contexts

# --- 节点 3: 并行分析 (Analyzers) ---
# 成本: ~$0.12 per dimension (GPT-4-Turbo, 3k input + 1k output)
def make_analyze_dimension(openai_client):
    def analyze_dimension(state: AnalysisState, dimension: str) -> Dict:
        """分析单个维度（现在只处理小块相关上下文）"""
        context = state["retrieved_contexts"][dimension]
        queries = state["sub_queries"][dimension]
        
        # 维度特定的分析提示
        dimension_prompts = {
            "tech": """
        分析技术架构，重点关注：
        1. 共识机制及其创新点
        2. 智能合约平台和开发语言
        3. 可扩展性方案（Layer 2、分片等）
        4. 安全性设计和审计情况
        
        输出 Markdown 格式报告，包含评分 (0-100)。
        """,
        "econ": """
        分析经济模型，重点关注：
        1. 代币分配和解锁计划
        2. 通胀/通缩机制
        3. 激励模型和质押机制
        4. 价值捕获和代币效用
        
        输出 Markdown 格式报告，包含评分 (0-100)。
        """,
        "team": """
        分析团队背景，重点关注：
        1. 核心成员的技术和行业经验
        2. 顾问团队的影响力
        3. 合作伙伴和投资方
        4. 社区活跃度和开发进展
        
        输出 Markdown 格式报告，包含评分 (0-100)。
        """,
        "risk": """
        评估风险因素，重点关注：
        1. 技术风险（安全漏洞、可扩展性瓶颈）
        2. 市场风险（竞争对手、市场定位）
        3. 监管风险（合规性、法律不确定性）
        4. 执行风险（团队能力、路线图可行性）
        
        输出 Markdown 格式报告，包含风险等级 (低/中/高)。
        """
    }
        
        prompt = f"""
    基于以下上下文回答问题并生成分析报告。
    
    问题:
    {chr(10).join(f"- {q}" for q in queries)}
    
    上下文:
    {context}
    
    分析要求:
    {dimension_prompts[dimension]}
    """
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        
        report = response.choices[0].message.content
        
        # 更新状态（注意：需要合并而不是覆盖）
        current_results = state.get("analysis_results", {})
        current_results[dimension] = report
        
        return {"analysis_results": current_results}
    
    return analyze_dimension

# 为每个维度创建分析函数
```

> 说明：可在构建 Workflow 时注入共享的 `openai_client` 与 `rag_service`：
> ```python
> openai_client = OpenAI(api_key=OPENAI_API_KEY)
> rag_service = RAGService(...)
> 
> planner_node = make_generate_sub_queries(openai_client)
> retriever_node = make_retrieve_all_contexts(rag_service)
> analyze_dimension_node = make_analyze_dimension(openai_client)
> synthesize_node = make_synthesize_final_report(openai_client)
> 
> def analyze_tech(state): return analyze_dimension_node(state, "tech")
> def analyze_econ(state): return analyze_dimension_node(state, "econ")
> def analyze_team(state): return analyze_dimension_node(state, "team")
> def analyze_risk(state): return analyze_dimension_node(state, "risk")
> ```

# --- 节点 4: 综合 (Synthesizer) ---
# 成本: ~$0.0005 (GPT-4o-mini, 4k input + 500 output)
def make_synthesize_final_report(openai_client):
    def synthesize_final_report(state: AnalysisState) -> Dict:
        """合并所有维度的分析，生成综合报告和评分"""
        reports = state["analysis_results"]
        
        if len(reports) < len(state["dimensions"]):
            # 等待所有分析节点完成后再触发 LLM
            return {}
        
        prompt = f"""
    基于以下各维度的分析报告，生成综合评估。
    
    技术架构分析:
    {reports.get('tech', 'N/A')}
    
    经济模型分析:
    {reports.get('econ', 'N/A')}
    
    团队背景分析:
    {reports.get('team', 'N/A')}
    
    风险评估:
    {reports.get('risk', 'N/A')}
    
    请提供:
    1. 综合评分 (0-100)
    2. 核心优势 (3-5 点)
    3. 主要风险 (3-5 点)
    4. 投资建议 (一段话)
    
    返回 JSON 格式:
    {{
        "overall_score": 85,
        "strengths": ["...", "..."],
        "risks": ["...", "..."],
        "recommendation": "..."
    }}
    """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        
        synthesis = json.loads(response.choices[0].message.content)
        
        final_report = {
            **synthesis,
            "technology_analysis": reports.get("tech"),
            "economics_analysis": reports.get("econ"),
            "team_analysis": reports.get("team"),
            "risk_analysis": reports.get("risk")
        }
        
        return {"final_report": final_report}
    
    return synthesize_final_report

# --- 工作流编排 ---
openai_client = OpenAI(api_key=OPENAI_API_KEY)
rag_service = RAGService(chroma_client, redis_client, openai_client)

planner_node = make_generate_sub_queries(openai_client)
retriever_node = make_retrieve_all_contexts(rag_service)
analyze_dimension_node = make_analyze_dimension(openai_client)
synthesize_node = make_synthesize_final_report(openai_client)

def analyze_tech(state: AnalysisState) -> Dict:
    return analyze_dimension_node(state, "tech")

def analyze_econ(state: AnalysisState) -> Dict:
    return analyze_dimension_node(state, "econ")

def analyze_team(state: AnalysisState) -> Dict:
    return analyze_dimension_node(state, "team")

def analyze_risk(state: AnalysisState) -> Dict:
    return analyze_dimension_node(state, "risk")

workflow = StateGraph(AnalysisState)

# 添加节点
workflow.add_node("planner", planner_node)
workflow.add_node("retriever", retriever_node)
workflow.add_node("analyze_tech", analyze_tech)
workflow.add_node("analyze_econ", analyze_econ)
workflow.add_node("analyze_team", analyze_team)
workflow.add_node("analyze_risk", analyze_risk)
workflow.add_node("synthesizer", synthesize_node)

# 编排流程
workflow.set_entry_point("planner")
workflow.add_edge("planner", "retriever")

# 检索完成后，并行执行所有分析
workflow.add_edge("retriever", "analyze_tech")
workflow.add_edge("retriever", "analyze_econ")
workflow.add_edge("retriever", "analyze_team")
workflow.add_edge("retriever", "analyze_risk")

# 所有分析完成后，进入综合节点（synthesizer 内部会等待所有维度结果）
for node in ["analyze_tech", "analyze_econ", "analyze_team", "analyze_risk"]:
    workflow.add_edge(node, "synthesizer")
workflow.add_edge("synthesizer", END)

# 编译
analysis_graph = workflow.compile()
```

> 说明：`make_retrieve_all_contexts(rag_service)` 通过闭包注入依赖，LangGraph 在单进程 Celery Worker 内执行时无需全局变量或序列化复杂对象；若未来需要跨进程/持久化状态，再切换为将 `rag_service` 放入 `AnalysisState` 的 `services` 字段即可。  
> 综合节点内部通过 `len(reports) < len(dimensions)` 判断，只有在所有分析结果就绪时才触发 LLM 生成，从而避免多次调用造成的额外成本。

**使用示例:**
```python
# 执行分析工作流
result = analysis_graph.invoke({
    "document_id": "doc_uuid",
    "user_id": "user_uuid",
    "dimensions": ["tech", "econ", "team", "risk"]
})

final_report = result["final_report"]
# {
#     "overall_score": 85,
#     "strengths": [...],
#     "risks": [...],
#     "recommendation": "...",
#     "technology_analysis": "...",
#     "economics_analysis": "...",
#     "team_analysis": "...",
#     "risk_analysis": "..."
# }
```

**成本对比:**

| 方案 | Token 消耗 | 成本 | 说明 |
|------|-----------|------|------|
| ❌ 天真并行 | 4 × 30k input + 4 × 1k output | ~$1.32 | 每个维度处理完整文档 |
| ✅ RAG-in-Graph | 1 × 0.5k (规划) + 4 × 3k (分析) + 1 × 4k (综合) | ~$0.48 | 只处理相关上下文 |
| **节省** | **-63%** | **-$0.84** | **每份报告节省 64%** |

**分析维度:**
1. **技术架构分析 (tech)**
   - 共识机制
   - 智能合约平台
   - 可扩展性方案
   - 安全性设计

2. **经济模型分析 (econ)**
   - 代币分配
   - 通胀/通缩机制
   - 激励模型
   - 价值捕获

3. **团队背景分析 (team)**
   - 核心成员经历
   - 顾问团队
   - 合作伙伴
   - 社区活跃度

4. **风险评估 (risk)**
   - 技术风险
   - 市场风险
   - 监管风险
   - 竞争风险


### 4. 任务队列服务 (Task Queue)

**职责:** 异步处理耗时任务

**Celery 任务定义:**
```python
@celery.task(bind=True)
def parse_document_task(self, document_id):
    # 更新进度: 0%
    self.update_state(state='PROGRESS', meta={'progress': 0})
    
    # 提取文本: 30%
    text = extract_text(document_id)
    self.update_state(state='PROGRESS', meta={'progress': 30})
    
    # 分块: 50%
    chunks = split_text(text)
    self.update_state(state='PROGRESS', meta={'progress': 50})
    
    # 向量化: 80%
    embeddings = generate_embeddings(chunks)
    self.update_state(state='PROGRESS', meta={'progress': 80})
    
    # 存储: 100%
    store_vectors(embeddings)
    return {'status': 'completed'}

@celery.task
def generate_analysis_task(document_id, user_id):
    # 执行分析工作流（需要用户上下文做多租户隔离）
    result = analysis_service.generate_report(document_id, user_id=user_id)
    return result
```

**任务优先级:**
- 高优先级: 付费用户的任务
- 普通优先级: 免费用户的任务
- 低优先级: 批量分析任务

### 5. 认证与授权服务 (Auth Service)

**职责:** 用户认证、权限控制

**Supabase Auth 集成:**
```python
from supabase import create_client

class AuthService:
    def __init__(self):
        self.supabase = create_client(url, key)
    
    def register(self, email, password):
        return self.supabase.auth.sign_up({
            "email": email,
            "password": password
        })
    
    def login(self, email, password):
        return self.supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
    
    def verify_token(self, token):
        return self.supabase.auth.get_user(token)
```

**FastAPI 中间件:**
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    user = auth_service.verify_token(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

### 6. 订阅管理服务 (Subscription Service)

**职责:** 处理订阅、积分管理

**⭐ 积分制商业模型 (Credit-Based Model)**

不卖"功能"，卖"消耗品"。这是确保盈利的唯一方案。

**订阅计划（积分包）:**
```python
SUBSCRIPTION_PLANS = {
    "free": {
        "price": 0,
        "monthly_credits": 100,  # 足够体验 2-3 份白皮书
        "features": ["basic_qa", "simple_analysis"]
    },
    "basic": {
        "price": 29,
        "monthly_credits": 1500,  # $29 购买 1500 积分
        "features": ["basic_qa", "full_analysis", "export_pdf"]
    },
    "pro": {
        "price": 99,
        "monthly_credits": 6000,  # $99 购买 6000 积分（批量折扣）
        "features": ["basic_qa", "full_analysis", "export_pdf", "api_access", "batch_analysis", "priority_queue"]
    },
    "enterprise": {
        "price": "custom",
        "monthly_credits": "custom",
        "features": ["all", "priority_support", "custom_deployment", "dedicated_resources"]
    }
}
```

**积分价目表（操作成本定价）:**

定价基准：$29 = 1500 积分，即 1 美元 ≈ 52 积分

```python
CREDIT_PRICING = {
    # 操作类型: (预估成本 USD, 积分定价, 说明)
    "document_upload_pdf": {
        "cost_usd": 0.004,
        "credits": 2,
        "description": "上传并向量化 PDF 文档"
    },
    "document_upload_url": {
        "cost_usd": 0.004,
        "credits": 2,
        "description": "抓取并向量化网页内容"
    },
    "qa_mini": {
        "cost_usd": 0.0006,
        "credits": 0.1,  # 极低，鼓励高频使用
        "description": "使用 GPT-4o-mini 的简单问答"
    },
    "qa_turbo": {
        "cost_usd": 0.036,
        "credits": 2,
        "description": "使用 GPT-4-Turbo 的深度问答"
    },
    "analysis_report": {
        "cost_usd": 0.48,
        "credits": 50,  # 主要利润中心（50% 毛利）
        "description": "生成完整的多维度分析报告"
    },
    "export_pdf": {
        "cost_usd": 0.01,
        "credits": 1,
        "description": "导出报告为 PDF"
    },
    "batch_analysis": {
        "cost_usd": 2.40,  # 5份文档
        "credits": 200,  # 批量折扣
        "description": "批量分析（5份文档）"
    }
}
```

**积分检查与消费:**
```python
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
    
    def check_and_consume_credits(
        self, 
        user_id: str, 
        action_type: str
    ) -> tuple[bool, str]:
        """
        检查并消费积分（原子操作）
        
        Returns:
            (success: bool, message: str)
        """
        action_cost = CREDIT_PRICING[action_type]["credits"]
        
        # 使用数据库事务确保原子性
        with self.db.begin():
            # 锁定用户订阅记录（防止并发问题）
            subscription = (
                self.db.execute(
                    select(Subscription)
                    .where(Subscription.user_id == user_id)
                    .with_for_update()
                )
                .scalar_one_or_none()
            )
            
            if not subscription:
                return False, "No active subscription"
            
            # 检查积分余额
            if subscription.current_credits < action_cost:
                return False, f"Insufficient credits. Required: {action_cost}, Available: {subscription.current_credits}"
            
            # 扣除积分
            subscription.current_credits -= action_cost
            subscription.updated_at = datetime.now()
            
            # 记录消费日志
            usage_log = UsageLog(
                user_id=user_id,
                action_type=action_type,
                credits_consumed=action_cost,
                credits_remaining=subscription.current_credits,
                metadata={
                    "cost_usd": CREDIT_PRICING[action_type]["cost_usd"],
                    "description": CREDIT_PRICING[action_type]["description"]
                }
            )
            self.db.add(usage_log)
        
        return True, f"Success. Consumed {action_cost} credits. Remaining: {subscription.current_credits}"
    
    def refund_credits(self, user_id: str, action_type: str) -> None:
        """在任务失败时退还对应积分"""
        action_cost = CREDIT_PRICING[action_type]["credits"]
        with self.db.begin():
            subscription = (
                self.db.execute(
                    select(Subscription)
                    .where(Subscription.user_id == user_id)
                    .with_for_update()
                )
                .scalar_one_or_none()
            )
            if not subscription:
                return
            subscription.current_credits += action_cost
            subscription.updated_at = datetime.now()
            
            refund_log = UsageLog(
                user_id=user_id,
                action_type=f"{action_type}_refund",
                credits_consumed=-action_cost,
                credits_remaining=subscription.current_credits,
                metadata={"reason": "task_failed"}
            )
            self.db.add(refund_log)
    
    def get_credits_balance(self, user_id: str) -> dict:
        """获取用户积分余额"""
        subscription = self.db.query(Subscription).filter_by(user_id=user_id).first()
        if not subscription:
            return {"credits": 0, "plan": "none"}
        
        return {
            "plan": subscription.plan,
            "monthly_credits": subscription.monthly_credits,
            "current_credits": subscription.current_credits,
            "reset_date": subscription.reset_date,
            "usage_percentage": (1 - subscription.current_credits / subscription.monthly_credits) * 100
        }
    
    def reset_monthly_credits(self, user_id: str):
        """每月重置积分（定时任务调用）"""
        subscription = self.db.query(Subscription).filter_by(user_id=user_id).first()
        if subscription and subscription.status == "active":
            subscription.current_credits = subscription.monthly_credits
            subscription.reset_date = datetime.now() + timedelta(days=30)
            self.db.commit()
```

**API 端点中的使用:**
```python
@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile,
    user: User = Depends(get_current_user),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    # 先检查并扣除积分
    success, message = sub_service.check_and_consume_credits(
        user.id, 
        "document_upload_pdf"
    )
    
    if not success:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=message
        )
    
    # 积分扣除成功，开始处理文档
    try:
        document_id = await document_service.upload_pdf(file, user.id)
        task_id = parse_document_task.delay(document_id)
        
        return {
            "document_id": document_id,
            "task_id": task_id,
            "credits_consumed": CREDIT_PRICING["document_upload_pdf"]["credits"],
            "message": message
        }
    except Exception as e:
        # 如果处理失败，退还积分
        sub_service.refund_credits(user.id, "document_upload_pdf")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analysis/generate")
async def generate_analysis(
    request: AnalysisRequest,
    user: User = Depends(get_current_user),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    # 分析报告是主要利润中心，消耗 50 积分
    success, message = sub_service.check_and_consume_credits(
        user.id,
        "analysis_report"
    )
    
    if not success:
        raise HTTPException(status_code=402, detail=message)
    
    # 创建分析任务
    task_id = generate_analysis_task.delay(request.document_id, user.id)
    
    return {
        "task_id": task_id,
        "credits_consumed": 50,
        "message": message
    }
```

**Lemon Squeezy Webhook 处理:**
```python
@app.post("/webhooks/lemonsqueezy")
async def handle_webhook(request: Request):
    payload = await request.json()
    event_type = payload["meta"]["event_name"]
    
    if event_type == "subscription_created":
        user_id = payload["data"]["attributes"]["user_id"]
        plan = payload["data"]["attributes"]["variant_name"]
        subscription_service.activate_subscription(user_id, plan)
    
    elif event_type == "subscription_cancelled":
        user_id = payload["data"]["attributes"]["user_id"]
        subscription_service.cancel_subscription(user_id)
    
    return {"status": "ok"}
```

## 数据模型设计

### Supabase PostgreSQL 表结构

**users 表 (由 Supabase Auth 管理)**
```sql
-- Supabase 自动创建
auth.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    created_at TIMESTAMP,
    ...
)
```

**subscriptions 表（积分制）**
```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL CHECK (plan IN ('free', 'basic', 'pro', 'enterprise')),
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled', 'expired')),
    monthly_credits INTEGER NOT NULL,      -- 每月分配的积分总额
    current_credits DECIMAL(10, 2) NOT NULL DEFAULT 0,  -- 当前剩余积分（支持小数）
    reset_date DATE NOT NULL,              -- 积分重置日期
    lemon_squeezy_subscription_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- 触发器：新用户自动创建免费订阅
CREATE OR REPLACE FUNCTION create_free_subscription()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO subscriptions (user_id, plan, status, monthly_credits, current_credits, reset_date)
    VALUES (NEW.id, 'free', 'active', 100, 100, CURRENT_DATE + INTERVAL '30 days');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION create_free_subscription();
```

**documents 表**
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('pdf', 'url')),
    source_value TEXT NOT NULL,  -- 文件路径或 URL
    title TEXT,
    file_size BIGINT,
    status TEXT NOT NULL CHECK (status IN ('uploading', 'parsing', 'completed', 'failed')),
    error_message TEXT,
    parsed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
```

**analysis_results 表**
```sql
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    technology_analysis JSONB,
    economics_analysis JSONB,
    team_analysis JSONB,
    risk_analysis JSONB,
    overall_score INTEGER CHECK (overall_score >= 0 AND overall_score <= 100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analysis_document_id ON analysis_results(document_id);
```

**qa_history 表**
```sql
CREATE TABLE qa_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB,  -- 引用来源
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_qa_document_id ON qa_history(document_id);
CREATE INDEX idx_qa_user_id ON qa_history(user_id);
```

**usage_logs 表**
```sql
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'document_upload_pdf',
            'document_upload_url',
            'qa_mini',
            'qa_turbo',
            'analysis_report',
            'export_pdf',
            'batch_analysis'
        ) OR action_type LIKE '%\\_refund' ESCAPE '\'
    ),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_usage_logs_user_id ON usage_logs(user_id);
CREATE INDEX idx_usage_logs_created_at ON usage_logs(created_at);
```

**api_keys 表 (专业版及以上)**
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
```

### Row Level Security (RLS) 策略

```sql
-- 启用 RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE qa_history ENABLE ROW LEVEL SECURITY;

-- 用户只能访问自己的数据
CREATE POLICY "Users can view own documents"
    ON documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own documents"
    ON documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own documents"
    ON documents FOR DELETE
    USING (auth.uid() = user_id);
```


### Chroma 向量数据库结构

**⭐ 多租户架构：单一 Collection + 元数据过滤**

这是构建多租户 RAG 应用的行业标准。核心思想：将所有用户、所有文档的向量存储在一个统一的 Collection 中（名为 `documents`），通过元数据标签进行隔离和过滤。

**优势：**
- 避免 Collection 数量爆炸（Chroma 对大量 Collection 性能下降）
- 简化管理和备份
- 支持跨文档检索（未来功能）
- 更好的资源利用率

```python
# 初始化：创建单一 Collection（应用启动时执行一次）
collection = chroma_client.get_or_create_collection(
    name="documents",  # 固定名称，所有文档共享
    metadata={
        "description": "Multi-tenant document storage",
        "chunking_strategy": "semantic"
    }
)

# 文档块存储 - 文本块示例
collection.add(
    documents=["Section: 2. Tokenomics -> 2.1. Token Distribution\n\n(chunk content...)"],
    embeddings=[embedding_vector],
    metadatas=[{
        "user_id": user_id,              # ⭐ 关键：用户隔离
        "document_id": document_id,       # ⭐ 关键：文档隔离
        "section_path": "2. Tokenomics -> 2.1. Token Distribution",
        "page_number": 3,
        "chunk_index": 0,
        "element_type": "text",
        "token_count": 850,
        "parent_section": "2. Tokenomics",
        "created_at": "2024-01-15T10:30:00Z"
    }],
    ids=[f"{document_id}_chunk_0"]  # 全局唯一 ID
)

# 文档块存储 - 表格块示例
collection.add(
    documents=["Section: 2. Tokenomics -> 2.1. Token Distribution\n\nSummary: This table shows...\n\nTable:\n| Category | Percentage |\n|----------|------------|\n| Team     | 20%        |"],
    embeddings=[embedding_vector],
    metadatas=[{
        "user_id": user_id,              # ⭐ 用户隔离
        "document_id": document_id,       # ⭐ 文档隔离
        "section_path": "2. Tokenomics -> 2.1. Token Distribution",
        "page_number": 4,
        "element_type": "table",
        "has_summary": True,
        "parent_section": "2. Tokenomics",
        "created_at": "2024-01-15T10:30:00Z"
    }],
    ids=[f"{document_id}_table_0"]
)
```

**检索优化：元数据过滤确保数据隔离**
```python
# ⭐ 关键：检索时必须过滤 user_id 和 document_id
results = collection.query(
    query_embeddings=[question_embedding],
    n_results=10,
    where={
        "$and": [
            {"user_id": {"$eq": user_id}},        # 用户隔离
            {"document_id": {"$eq": document_id}}, # 文档隔离
            {
                "$or": [ 
                    {"element_type": {"$eq": "text"}},
                    {"element_type": {"$eq": "table"}}
                ]
            }
        ]
    }
)

# 按 section_path 分组，确保上下文连贯
grouped_results = {}
for result in results:
    section = result["metadata"]["section_path"]
    if section not in grouped_results:
        grouped_results[section] = []
    grouped_results[section].append(result)

# 优先返回同一章节的多个块
context_chunks = []
for section, chunks in grouped_results.items():
    context_chunks.extend(sorted(chunks, key=lambda x: x.get("chunk_index", 0)))
```

**删除文档时的处理：**
```python
def delete_document_vectors(document_id: str, user_id: str):
    """删除指定文档的所有向量"""
    collection = chroma_client.get_collection("documents")
    
    # 方法1: 通过 where 过滤删除（推荐）
    collection.delete(
        where={
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"document_id": {"$eq": document_id}}
            ]
        }
    )
    
    # 方法2: 如果需要精确控制，先查询再删除
    # results = collection.get(
    #     where={"$and": [
    #         {"user_id": {"$eq": user_id}},
    #         {"document_id": {"$eq": document_id}}
    #     ]},
    #     include=[]  # 只获取 IDs
    # )
    # collection.delete(ids=results["ids"])
```

**跨文档检索（未来功能）：**
```python
# 检索用户所有文档中的相关内容
results = collection.query(
    query_embeddings=[question_embedding],
    n_results=20,
    where={
        "user_id": {"$eq": user_id}  # 只过滤用户，不限制文档
    }
)
```

## API 设计

### RESTful API 端点

**认证相关**
```
POST   /api/auth/register          # 注册
POST   /api/auth/login             # 登录
POST   /api/auth/logout            # 登出
POST   /api/auth/reset-password    # 重置密码
GET    /api/auth/me                # 获取当前用户信息
```

**文档管理**
```
POST   /api/documents/upload       # 上传 PDF
POST   /api/documents/from-url     # 从 URL 创建文档
GET    /api/documents              # 获取文档列表
GET    /api/documents/{id}         # 获取文档详情
DELETE /api/documents/{id}         # 删除文档
GET    /api/documents/{id}/status  # 获取解析状态
```

**问答功能**
```
POST   /api/qa/query               # 提问
GET    /api/qa/history/{doc_id}    # 获取问答历史
```

**分析报告**
```
POST   /api/analysis/generate      # 生成分析报告
GET    /api/analysis/{id}          # 获取分析报告
GET    /api/analysis/{id}/export   # 导出报告 (PDF/Markdown)
```

**订阅管理**
```
GET    /api/subscription           # 获取订阅信息
POST   /api/subscription/checkout  # 创建支付链接
GET    /api/subscription/usage     # 获取使用情况
```

**API 密钥 (专业版)**
```
POST   /api/api-keys               # 创建 API 密钥
GET    /api/api-keys               # 获取密钥列表
DELETE /api/api-keys/{id}          # 删除密钥
```

**WebSocket 端点**
```
WS     /ws/tasks/{task_id}         # 任务进度推送
```

### API 请求/响应示例

**上传文档**
```http
POST /api/documents/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

file: [binary data]

Response:
{
    "document_id": "uuid",
    "task_id": "celery_task_id",
    "status": "parsing",
    "message": "Document uploaded successfully"
}
```

**提问**
```http
POST /api/qa/query
Content-Type: application/json
Authorization: Bearer {token}

{
    "document_id": "uuid",
    "question": "这个项目的共识机制是什么？"
}

Response:
{
    "answer": "该项目采用 PoS (Proof of Stake) 共识机制...",
    "sources": [
        {
            "chunk_id": "doc_uuid_chunk_5",
            "page": 3,
            "text": "We implement a Proof of Stake..."
        }
    ],
    "cached": false
}
```


## 前端架构设计

### 页面结构

```
/                           # 首页 (营销页面)
/login                      # 登录
/register                   # 注册
/dashboard                  # 用户仪表板
/documents                  # 文档列表
/documents/:id              # 文档详情 + 问答界面
/documents/:id/analysis     # 分析报告页面
/subscription               # 订阅管理
/settings                   # 用户设置
/api-keys                   # API 密钥管理 (专业版)
```

### 状态管理 (Pinia)

```typescript
// stores/auth.ts
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: null,
    isAuthenticated: false
  }),
  actions: {
    async login(email: string, password: string) {},
    async logout() {},
    async fetchUser() {}
  }
})

// stores/documents.ts
export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    documents: [],
    currentDocument: null,
    uploadProgress: 0
  }),
  actions: {
    async uploadDocument(file: File) {},
    async fetchDocuments() {},
    async deleteDocument(id: string) {}
  }
})

// stores/subscription.ts
export const useSubscriptionStore = defineStore('subscription', {
  state: () => ({
    plan: 'free',
    quota: 3,
    usage: 0
  }),
  actions: {
    async fetchSubscription() {},
    async createCheckout(plan: string) {}
  }
})
```


### 核心组件

**DocumentUploader.vue**
```vue
<template>
  <el-upload
    drag
    :action="uploadUrl"
    :headers="headers"
    :on-progress="handleProgress"
    :on-success="handleSuccess"
  >
    <el-icon><upload-filled /></el-icon>
    <div>拖拽 PDF 文件到此处或点击上传</div>
  </el-upload>
  
  <el-input
    v-model="url"
    placeholder="或输入白皮书网页 URL"
  />
  <el-button @click="submitUrl">从 URL 导入</el-button>
</template>
```

**ChatInterface.vue**
```vue
<template>
  <div class="chat-container">
    <div class="messages">
      <div v-for="msg in messages" :key="msg.id" :class="msg.role">
        <div class="content">{{ msg.content }}</div>
        <div v-if="msg.sources" class="sources">
          <el-tag v-for="src in msg.sources">页 {{ src.page }}</el-tag>
        </div>
      </div>
    </div>
    
    <el-input
      v-model="question"
      placeholder="询问关于白皮书的问题..."
      @keyup.enter="sendQuestion"
    />
  </div>
</template>
```

**AnalysisReport.vue**
```vue
<template>
  <div class="report">
    <el-card>
      <h2>综合评分: {{ report.overall_score }}/100</h2>
      <el-progress :percentage="report.overall_score" />
    </el-card>
    
    <el-tabs>
      <el-tab-pane label="技术架构">
        <markdown-renderer :content="report.technology_analysis" />
      </el-tab-pane>
      <el-tab-pane label="经济模型">
        <markdown-renderer :content="report.economics_analysis" />
      </el-tab-pane>
      <el-tab-pane label="团队背景">
        <markdown-renderer :content="report.team_analysis" />
      </el-tab-pane>
      <el-tab-pane label="风险评估">
        <markdown-renderer :content="report.risk_analysis" />
      </el-tab-pane>
    </el-tabs>
    
    <el-button @click="exportPDF">导出 PDF</el-button>
  </div>
</template>
```


## 性能优化策略

### 1. 缓存策略

**Redis 缓存层次:**
```python
# L1: 问答缓存 (1小时)
cache_key = f"qa:{document_id}:{hash(question)}"
cached_answer = redis.get(cache_key)
if cached_answer:
    return cached_answer

# L2: 向量检索缓存 (24小时)
cache_key = f"chunks:{document_id}:{hash(question)}"
cached_chunks = redis.get(cache_key)

# L3: 分析报告缓存 (永久，直到文档更新)
cache_key = f"analysis:{document_id}"
```

### 2. 批量处理

**向量化批处理:**
```python
# 批量生成 embeddings
batch_size = 100
for i in range(0, len(chunks), batch_size):
    batch = chunks[i:i+batch_size]
    embeddings = openai.embeddings.create(
        model="text-embedding-3-large",
        input=batch
    )
```

### 3. 异步处理

**所有耗时操作异步化:**
- 文档解析: Celery 任务
- 向量化: Celery 任务
- 分析报告生成: Celery 任务
- 大文件上传: 分片上传

### 4. 数据库优化

**索引策略:**
```sql
-- 复合索引
CREATE INDEX idx_documents_user_status ON documents(user_id, status);
CREATE INDEX idx_qa_document_created ON qa_history(document_id, created_at DESC);

-- 分区表 (usage_logs 按月分区)
CREATE TABLE usage_logs_2024_01 PARTITION OF usage_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```


## 安全设计

### 1. 认证与授权

**JWT Token 管理:**
```python
# Supabase 自动处理 JWT
# Token 有效期: 1小时
# Refresh Token 有效期: 30天
```

**API 密钥认证 (专业版):**
```python
def verify_api_key(api_key: str):
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    record = db.query(ApiKey).filter_by(key_hash=key_hash).first()
    if not record or record.expires_at < datetime.now():
        raise HTTPException(401, "Invalid API key")
    return record.user_id
```

### 2. 限流策略

**基于 Redis 的滑动窗口限流:**
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/api/qa/query")
@limiter.limit("10/minute")  # 每分钟 10 次
async def query(request: Request):
    pass
```

**订阅计划限流:**
```python
RATE_LIMITS = {
    "free": "5/minute",
    "basic": "20/minute",
    "pro": "100/minute",
    "enterprise": "1000/minute"
}
```

### 3. 数据安全

**文件存储加密:**
```python
# Supabase Storage 自动加密
# 使用 AES-256 加密
```

**敏感数据脱敏:**
```python
# 日志中隐藏敏感信息
logger.info(f"User {user_id[:8]}... uploaded document")
```

**SQL 注入防护:**
```python
# 使用 ORM 参数化查询
db.query(Document).filter(Document.id == document_id).first()
```


## 监控与日志

### 0. 后端日志设计规范

**设计目标**
- 诊断：快速定位请求/任务失败原因（入参、上下文、依赖调用结果）。
- 运营：量化文档解析成功率、平均耗时、积分扣费异常等业务指标。
- 审计：关键信息落盘，满足合规/付费纠纷追溯，同时避免泄露敏感数据。

**日志分层**

| 层级 | 说明 | 关键字段 |
| --- | --- | --- |
| HTTP 入口 | FastAPI 中间件记录请求/响应 | request_id、path、status、latency、user_id |
| 领域事件 | Service/Repository 中的业务日志 | document_id、action、credits_delta、status |
| 任务日志 | Celery worker 每个阶段 | task_id、stage、progress、duration |
| 外部依赖 | OpenAI/Gemini/Supabase/Redis/Chroma 调用 | provider、operation、latency、retry_count |

**架构与格式**
- 使用 `logging.config.dictConfig` 加载统一配置文件（`backend/app/logging.yaml`），按环境切换 Handler：
  - Dev：彩色 console + 简单格式，级别 DEBUG。
  - Prod：JSONFormatter（结构化）输出到 stdout + `RotatingFileHandler` (`backend.log`)，级别 INFO。
- Logger 命名：`app.api`, `app.services.document`, `app.tasks.parse`, 方便按模块过滤。
- 统一字段：`ts`, `level`, `logger`, `message`, `request_id`, `user_id`, `document_id`, `task_id`, `duration_ms`, `error_code`.
- 高频日志支持采样（例如成功的健康检查只保留 10%）。

**上下文注入**
- HTTP：中间件生成 `request_id`（UUID4），从 `Authorization` 解析 `user_id`，放入 `contextvars`; 使用自定义 `ContextFilter` 自动注入每条日志。
- Celery：任务启动时生成/继承 `task_id`，并写入 `logging.LoggerAdapter`.
- RAG/文档处理：调用链传递 `document_id`、`sku`、`credits_tx_id`，确保退款/扣费能对应日志。

**输出与保留**
- 本地开发：`backend.log` 采用 10MB x 5 轮转。
- 生产建议：stdout → Loki/ELK，保留 14 天；错误级别及关键业务事件额外写入 `logs/events.log`。
- 采用 `PIIRedactingFilter` 清洗邮箱、token、API key（通过正则/配置项）。

**告警与指标联动**
- 日志级别 ≥ ERROR 时同时打点 Prometheus Counter `log_errors_total{module=...}`，用于 Alertmanager 告警。
- 关键业务事件（例如退款、积分不足）以 INFO 级别输出并追加 `event_type` 字段，方便后续查询。

**编码规范**
- 严禁 `print`，统一 `logger`.
- `logger.exception` 只用于真正的异常链，普通错误用 `logger.error(..., exc_info=False)`.
- 在 try/except 中先记录 `error_code`+`reason`，再抛出业务异常，避免重复日志。

### 1. 错误追踪 (Sentry)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)
```

### 2. 应用日志

```python
import logging
from logging.handlers import RotatingFileHandler

# 结构化日志
logger = logging.getLogger("blockchain_rag")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    "app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### 3. 性能监控

**关键指标:**
- API 响应时间
- LLM API 调用延迟
- 文档解析时间
- 向量检索时间
- 缓存命中率
- 任务队列长度

**监控实现:**
```python
from prometheus_client import Counter, Histogram

# 请求计数
request_count = Counter('api_requests_total', 'Total API requests')

# 响应时间
response_time = Histogram('api_response_seconds', 'API response time')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    request_count.inc()
    response_time.observe(duration)
    
    return response
```


## 部署架构

### Docker Compose 配置

```yaml
version: '3.8'

services:
  # FastAPI 应用
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${SUPABASE_URL}
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
      - chroma
  
  # Celery Worker
  worker:
    build: ./backend
    command: celery -A app.celery worker --loglevel=info
    environment:
      - DATABASE_URL=${SUPABASE_URL}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
  
  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  # Chroma
  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma
  
  # Vue 前端
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://api:8000

volumes:
  redis_data:
  chroma_data:
```

### 生产环境部署

**后端 (Railway/Render):**
```bash
# 环境变量
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
OPENAI_API_KEY=sk-xxx
REDIS_URL=redis://xxx
LEMON_SQUEEZY_API_KEY=xxx
SENTRY_DSN=xxx
```

**前端 (Vercel):**
```bash
# 环境变量
VITE_API_URL=https://api.yourdomain.com
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
```


## 成本估算

### LLM API 成本

**OpenAI 定价 (2024):**
- GPT-4-Turbo: $10/1M input tokens, $30/1M output tokens
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
- text-embedding-3-large: $0.13/1M tokens

**单次分析成本估算:**
```
文档向量化 (50页白皮书):
- 约 30,000 tokens
- 成本: $0.004

单次问答:
- 输入: 2,000 tokens (上下文) + 50 tokens (问题)
- 输出: 500 tokens
- 成本: $0.036 (GPT-4-Turbo) 或 $0.0006 (GPT-4o-mini)

完整分析报告:
- 4个维度分析，每个约 3,000 tokens 输入，1,000 tokens 输出
- 成本: $0.48 (GPT-4-Turbo)

月度成本 (1000 用户，平均每人 5 份白皮书):
- 向量化: 5000 * $0.004 = $20
- 问答 (平均 10 次/文档): 50000 * $0.0006 = $30 (使用 mini)
- 分析报告: 5000 * $0.48 = $2,400
- 总计: ~$2,500/月
```

### 基础设施成本

**月度估算:**
- Railway/Render (后端): $20-50
- Vercel (前端): $0 (Hobby) / $20 (Pro)
- Supabase: $0 (Free) / $25 (Pro)
- Redis Cloud: $0 (Free 30MB) / $10 (1GB)
- Sentry: $0 (Free) / $26 (Team)
- 总计: $20-131/月 (不含 LLM)

## 风险与缓解

### 技术风险

**风险 1: LLM API 成本失控**
- 缓解: 实施严格的缓存策略，使用混合模型策略
- 监控: 实时追踪 API 调用成本

**风险 2: PDF 解析失败率高**
- 缓解: 多解析器组合，提供人工审核入口
- 监控: 记录解析失败率和原因

**风险 3: 向量数据库性能瓶颈**
- 缓解: 设计抽象层，预留迁移到 Qdrant/Pinecone 的方案
- 监控: 查询延迟和吞吐量

**风险 4: 任务队列积压**
- 缓解: 动态扩展 Celery Worker，实施优先级队列
- 监控: 队列长度和任务等待时间

### 业务风险

**风险 5: 用户增长超预期导致成本激增**
- 缓解: 实施配额限制，优化成本结构
- 监控: 用户增长率和单用户成本

**风险 6: 支付集成问题**
- 缓解: 完善 Webhook 处理和错误重试机制
- 监控: 支付成功率和失败原因
