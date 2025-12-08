# Requirements Document

## Introduction

本文档定义了将现有区块链白皮书分析系统改造为通用 Agentic RAG 系统的需求。改造目标是移除领域特定逻辑（如区块链分析维度），构建一个可处理任意文档类型的智能问答和分析系统，支持 Agent 能力（工具调用、多步推理、自主规划）。

## Glossary

- **Agentic_RAG_System**: 具备自主推理和工具调用能力的检索增强生成系统
- **Agent**: 能够自主规划、执行多步任务、调用工具的 AI 组件
- **Tool**: Agent 可调用的功能模块，如文档检索、网络搜索、计算等
- **RAG_Pipeline**: 检索-增强-生成的处理流程
- **Document**: 用户上传的任意类型文档（PDF、文本等）
- **Chunk**: 文档分割后的文本片段
- **Embedding**: 文本的向量表示
- **Context_Window**: LLM 单次处理的上下文长度限制
- **Router**: 意图分类组件，决定请求的处理路径
- **RRF**: Reciprocal Rank Fusion，混合检索结果融合算法

## Requirements

### Requirement 1: 通用文档问答

**User Story:** As a user, I want to ask questions about any uploaded document, so that I can quickly extract information without reading the entire document.

#### Acceptance Criteria

1. WHEN a user submits a question, THE Agentic_RAG_System SHALL initiate the response stream within 3 seconds and provide visibility into the agent's thought process (e.g., "Searching document...", "Analyzing results...").
2. WHILE processing a question, THE Agentic_RAG_System SHALL use domain-agnostic prompts that do not assume any specific document type.
3. IF the retrieved context does not contain sufficient information, THEN THE Agentic_RAG_System SHALL respond with a clear indication that the information is not available in the document.
4. THE Agentic_RAG_System SHALL support questions in both Chinese and English languages.

### Requirement 2: Agent 工具调用能力

**User Story:** As a user, I want the system to autonomously use tools to answer complex questions, so that I can get comprehensive answers that may require multiple steps.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL provide a tool registry that allows registration of callable tools with name, description, and parameter schema.
2. WHEN the Agent determines a tool is needed, THE Agentic_RAG_System SHALL invoke the tool with appropriate parameters and incorporate the result into reasoning.
3. THE Agentic_RAG_System SHALL include a built-in document_search tool for retrieving relevant chunks from uploaded documents.
4. IF a tool invocation fails, THEN THE Agentic_RAG_System SHALL log the error and continue reasoning with available information.
5. THE Agentic_RAG_System SHALL include a built-in web_search tool (via Tavily or SerpApi) to answer questions requiring real-time information not present in the documents.
6. THE Agentic_RAG_System SHALL utilize a Router mechanism to classify user intent and avoid tool calls for small-talk or self-contained logic queries.

### Requirement 3: 多步推理与规划

**User Story:** As a user, I want the system to break down complex questions into steps, so that I can get accurate answers to multi-part questions.

#### Acceptance Criteria

1. WHEN a user submits a complex question, THE Agentic_RAG_System SHALL decompose it into sub-questions and process them sequentially.
2. WHILE executing a multi-step plan, THE Agentic_RAG_System SHALL maintain conversation state across steps.
3. THE Agentic_RAG_System SHALL limit the maximum number of reasoning steps to 10 to prevent infinite loops.
4. WHEN all sub-questions are answered, THE Agentic_RAG_System SHALL synthesize a final comprehensive answer.

### Requirement 4: 移除领域特定逻辑

**User Story:** As a developer, I want to remove blockchain-specific analysis logic, so that the system can be used for any document type.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL NOT contain hardcoded analysis dimensions (tech, econ, team, risk).
2. THE Agentic_RAG_System SHALL NOT contain blockchain-specific prompts or terminology in core components.
3. THE Agentic_RAG_System SHALL use configurable prompt templates that can be customized per use case.
4. WHEN the analysis_workflow module is removed, THE Agentic_RAG_System SHALL maintain all existing RAG query functionality.

### Requirement 5: 可扩展的分析框架

**User Story:** As a developer, I want to define custom analysis workflows, so that I can adapt the system to different domains without modifying core code.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL provide an AnalysisTemplate interface for defining custom analysis workflows.
2. WHEN an AnalysisTemplate is registered, THE Agentic_RAG_System SHALL make it available for document analysis.
3. THE Agentic_RAG_System SHALL support loading AnalysisTemplate definitions from configuration files in JSON or YAML format.
4. IF no custom template is specified, THEN THE Agentic_RAG_System SHALL use a default general-purpose analysis template.

### Requirement 6: 混合检索

**User Story:** As a user, I want the system to use both semantic and keyword search, so that I can get more accurate and comprehensive retrieval results.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL support vector-based semantic search using embeddings.
2. THE Agentic_RAG_System SHALL support keyword-based search using BM25 algorithm.
3. WHEN performing a search, THE Agentic_RAG_System SHALL combine results from both vector and keyword search using Reciprocal Rank Fusion (RRF) algorithm.
4. THE Agentic_RAG_System SHALL allow configuration of the weight ratio between vector and keyword search results with a default of 0.7:0.3.
5. IF keyword search returns no results, THEN THE Agentic_RAG_System SHALL fall back to vector-only search.

### Requirement 7: API 兼容性

**User Story:** As a frontend developer, I want the API to remain backward compatible, so that existing integrations continue to work.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL maintain the existing /api/qa endpoint with the same request and response schema.
2. THE Agentic_RAG_System SHALL add new agent-specific endpoints under /api/agent/ prefix.
3. WHEN a deprecated endpoint is called, THE Agentic_RAG_System SHALL return a deprecation warning header while still processing the request.
4. THE Agentic_RAG_System SHALL document all API changes in an OpenAPI specification.

### Requirement 8: 可观测性与调试

**User Story:** As a developer, I want to trace the agent's reasoning steps and tool outputs, so that I can debug hallucinations and logic errors.

#### Acceptance Criteria

1. THE Agentic_RAG_System SHALL log the full trace of the agent's execution graph in LangSmith or LangFuse compatible format.
2. WHEN the API request includes a trace parameter, THE Agentic_RAG_System SHALL return an intermediate_steps field showing tool inputs and outputs.
3. THE Agentic_RAG_System SHALL record latency metrics for each tool invocation and reasoning step.
4. IF an agent execution exceeds the step limit, THEN THE Agentic_RAG_System SHALL log the full execution trace for debugging purposes.
