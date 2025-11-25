
# Tasks.md

## 1. 文档处理管线

- [x] **doc-service-ingest**
  - [x] 实现 `/api/documents/upload` 与 `/api/documents/from-url` 上传/URL 接口。
  - [x] 做 MIME/大小校验以及 Supabase Auth 用户权限校验。
  - [x] 创建 `parse_document_task` Celery 任务并写入 Redis 队列，记录初始状态。
- [x] **doc-parse-chunk**
  - [x] 使用 Unstructured `partition_pdf`/`partition_html` 解析元素，降级到纯文本解析作为兜底。
  - [x] 依据标题构建章节树、智能分块（1000 tokens/100 overlap）并记录 element_type/token_count。
  - [x] 写入 chunk 元数据到本地存储，为后续 embedding 使用。
- [x] **doc-embed-store**
  - [x] 批量调用 OpenAI embeddings（当前使用 `text-embedding-3-small` 占位）。
  - [x] 将 chunk 与 metadata 写入单一 Chroma collection，确保 user_id/document_id 过滤。
  - [x] 实现删除文档时的向量同步删除及 created_at 记录。
- [x] **doc-storage-supabase**
  - [x] 将 DocumentRepository 切换为 Supabase Postgres + RLS（无配置时回退本地 JSON）。
  - [ ] 统一管理文档状态、用户订阅、积分等实体。
- [x] **doc-chunk-advanced**
  - [x] 引入表格专用处理：HTML→Markdown、GPT 摘要（如不可用则降级）、元数据 `element_type=table`。
  - [x] 使用 tiktoken 计算 token，基于阈值控制分块与 overlap。
  - [x] 构建标题层级树（H1/H2/H3) + page_number 元数据。
- [x] **doc-embed-prod**
  - [x] 改为 text-embedding-3-large，100 chunk/batch 调用。
  - [x] 接入托管 Chroma/向量服务，支持多实例与回滚日志。

## 2. RAG 查询服务

- [x] **rag-cache-layer**
  - [x] 设计 `qa:{md5(document_id+question)}` 缓存 key，TTL 1h。
  - [x] 设计 chunk 检索缓存与分析结果缓存层（24h/永久）。
  - [x] 处理缓存命中/未命中的序列化（json.dumps/loads）。
- [x] **rag-search-flow**
  - [x] 生成问题 embedding，携带 `{user_id, document_id}` metadata 过滤调用 `collection.query`。
  - [x] 实现 rerank：按 distance、章节聚合、表格加权，并保持 chunk_index 顺序。
  - [x] 构建 context（token 限制 2000）并附带来源标记 `[来源: section_path]`。
- [x] **rag-answer-gen**
  - [x] 实现 mini/turbo 双模型策略与温度设置。
  - [x] 输出 answer + sources（section/page/text snippet）并落 Redis 缓存。
  - [x] 缺失上下文时给出兜底回复。
- [x] **rag-redis-integration**
  - [x] 使用 Redis 替换内存 CacheService，提供 QA/Chunk/Analysis 三层缓存。
  - [x] 实现 cache hit/miss metrics 并注入到 RAGService。

## 3. 分析报告 LangGraph

- [x] **analysis-planner**
  - [x] `make_generate_sub_queries(openai_client)` 生成 3-5 子问题，JSON 解析校验。
  - [x] 将维度列表写入状态 `sub_queries`。
- [x] **analysis-retriever**
  - [x] `make_retrieve_all_contexts(rag_service)` 批量获取 chunk、去重、拼 context。
  - [x] 确保合并文本时保持 section_path 标记。
- [x] **analysis-analyzers**
  - [x] `make_analyze_dimension` 共享 `openai_client`，根据维度提示输出 Markdown 报告+评分。
  - [x] 定义 `analyze_tech/econ/team/risk` 包装器，更新 `analysis_results`。
- [x] **analysis-synthesizer**
  - [x] `make_synthesize_final_report` 在所有维度结果齐备后触发 LLM。
  - [x] 输出 JSON（overall_score/strengths/risks/recommendation）并附维度报告。

## 4. 异步任务与队列

- [x] **celery-tasks**
  - [x] `parse_document_task`：多阶段 `update_state`（0/30/50/80/100%）。
  - [x] `generate_analysis_task(document_id, user_id)`：执行工作流，异常上报。
- [x] **task-priority**
  - [x] 为付费/免费/批量任务配置不同 Celery 队列与 concurrency。
  - [x] 失败回滚：调用 `refund_credits`，记录日志并重试策略。
- [x] **task-observability**
  - [x] 任务入队/完成日志、Prometheus 指标、SLA 报警。

## 5. 订阅与积分

- [x] **subscription-checkout**
  - [x] 定义 `SUBSCRIPTION_PLANS`、Lemon Squeezy webhook 处理、Supabase RLS。
  - [x] API：`/api/subscription`, `/api/subscription/checkout`, `/api/subscription/usage`。
- [x] **credit-ledger**
  - [x] `CREDIT_PRICING` SKU、`check_and_consume_credits` 事务及 `usage_logs` 记录。
  - [x] `refund_credits` 退还逻辑及 `_refund` 日志，月度重置 `reset_monthly_credits`。

## 6. FastAPI 接口层

- [x] **api-documents**
  - [x] 上传、列表、详情、删除、状态查询端点与 `get_current_user` 依赖。
  - [x] 上传失败时触发积分回滚。
- [x] **api-qa-analysis**
  - [x] `/api/qa/query`（限流、缓存标记、历史记录）、`/api/qa/history/{doc_id}`。
  - [x] `/api/analysis/generate` 创建任务并扣减 50 积分，暴露任务状态查询。
- [x] **api-subscription**
  - [x] `/api/subscription`、`/api/api-keys` CRUD、验证 plan 权限。

## 7. 前端实现

- [x] **frontend-uploader**
  - [x] `DocumentUploader` 组件（Element Plus Upload+URL input）。
  - [x] 展示上传进度、成功状态、错误提示。
- [x] **frontend-chat**
  - [x] 聊天消息列表、引用 Tag、输入框回车发送。
  - [x] 显示缓存命中、队列状态提示。
- [x] **frontend-analysis**
  - [x] `AnalysisReport` Tab + Markdown 渲染 + 进度条。
  - [x] 导出按钮调用 `/api/analysis/{id}/export`。

## 8. 基础设施与安全

- [ ] **infra-deploy**
  - [ ] Docker Compose services（api/worker/redis/chroma/frontend）。
  - [ ] Railway/Vercel 环境变量清单。
- [ ] **security-rls**
  - [ ] Supabase RLS policy（documents/analysis_results/qa_history）。
  - [ ] FastAPI JWT 校验、RateLimiter、API Key 验证。
- [x] **monitoring**
  - [x] Sentry 集成（可配置 DSN，默认关闭）。
  - [x] 统一结构化日志与 `logging.yaml`。
  - [x] Prometheus `/metrics` 端点、HTTP/任务指标。
- [ ] **security-hardening**
  - [ ] JWT 校验、RateLimiter、API Key 验证以及日志脱敏。
- [x] **logging-foundation**
  - [x] 引入 `logging.yaml` + `dictConfig`，按环境切换 console/JSON/RotatingFileHandler。
  - [x] 实现 `ContextFilter` + `contextvars` 注入 `request_id/user_id/document_id/task_id`。
  - [x] 添加 `PIIRedactingFilter` 与采样策略，确保敏感信息脱敏并减少噪音。
  - [x] 将 `backend.log` 纳入 `.gitignore` 并记录日志保留/归档策略。
- [x] **logging-instrumentation**
  - [x] HTTP 中间件记录请求/响应/耗时并暴露 `log_errors_total` 指标。
  - [x] DocumentService/RAGService/Celery 任务关键路径输出结构化业务事件日志。
  - [x] 外部依赖（OpenAI/Gemini/Supabase/Chroma）调用封装统一记录 latency/重试/错误码。
  - [x] ERROR 日志触发 Prometheus Counter + Alertmanager（可由 Prometheus 规则对接）。

## 9. 成本与风险

- [ ] **cost-model**
  - [ ] LLM token 成本估算、缓存命中率目标、批量 embedding。
- [ ] **risk-mitigation**
  - [ ] 技术/业务风险表，监控指标及应对策略（队列积压、PDF 失败、支付问题）。

## 10. 测试

- [x] **tests-backend-documents**
  - [x] 使用 FastAPI TestClient 编写 `/api/documents/upload` e2e 测试。
  - [x] 通过 Settings/ENV 注入禁用文档管线，避免 Celery/OpenAI 依赖。
- [ ] **tests-rag-analysis**
  - [ ] 覆盖 RAG Service 缓存命中/未命中、重排序、answer 兜底等路径。
  - [ ] LangGraph 工作流的 planner/retriever/analyzer/synthesizer 单元 + 集成测试。
- [x] **tests-subscription-credit**
  - [x] 订阅扣费、退款、LemonSqueezy webhook、API Key 权限校验。


