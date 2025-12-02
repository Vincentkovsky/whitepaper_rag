# Requirements Document

## Introduction

本文档定义了 Agentic RAG 系统前端重新设计的需求。该前端将为用户提供一个现代化、响应式的界面，用于与后端 RAG 系统交互，包括文档管理、智能问答、Agent 对话和订阅管理等功能。

## Glossary

- **Frontend**: 基于 React/Vue 等现代框架构建的 Web 客户端应用
- **Agentic_RAG_System**: 后端提供的检索增强生成系统，支持文档问答和 Agent 对话
- **Document**: 用户上传的 PDF 文件或通过 URL 提交的文档
- **Agent_Chat**: 基于 ReAct 模式的智能对话功能，支持工具调用和推理过程展示
- **SSE (Server-Sent Events)**: 服务器推送事件，用于流式传输 Agent 响应
- **Supabase_Auth**: 基于 Supabase 的用户认证服务，支持 Google OAuth
- **Subscription**: 用户订阅计划，决定可用功能和积分额度

## Requirements

### Requirement 1: 用户认证

**User Story:** As a user, I want to sign in with my Google account, so that I can securely access my documents and chat history.

#### Acceptance Criteria

1. WHEN a user visits the application without authentication THEN THE Frontend SHALL display a login page with Google sign-in option
2. WHEN a user clicks the Google sign-in button THEN THE Frontend SHALL initiate Supabase OAuth flow and redirect to Google
3. WHEN authentication succeeds THEN THE Frontend SHALL store the session token and redirect to the dashboard
4. WHEN a user clicks logout THEN THE Frontend SHALL clear the session and redirect to the login page
5. WHEN a session token expires THEN THE Frontend SHALL automatically refresh the token or prompt re-authentication

### Requirement 2: 文档管理

**User Story:** As a user, I want to upload and manage my documents, so that I can query them using the RAG system.

#### Acceptance Criteria

1. WHEN a user uploads a PDF file THEN THE Frontend SHALL send the file to /api/documents/upload and display upload progress
2. WHEN a user submits a URL THEN THE Frontend SHALL send the URL to /api/documents/from-url and show processing status
3. WHEN viewing the document list THEN THE Frontend SHALL display document name, status, and upload date for each document
4. WHEN a document is processing THEN THE Frontend SHALL poll /api/documents/{id}/status and update the status indicator
5. WHEN a user deletes a document THEN THE Frontend SHALL confirm the action and call DELETE /api/documents/{id}
6. IF a document upload fails THEN THE Frontend SHALL display an error message with the failure reason

### Requirement 3: Agent 对话界面

**User Story:** As a user, I want to chat with the AI agent, so that I can get intelligent answers with full transparency on how the answer was derived.

#### Acceptance Criteria

1. WHEN a user selects a document or knowledge base and enters a question THEN THE Frontend SHALL send the query to /api/agent/chat/stream
2. WHEN receiving SSE events THEN THE Frontend SHALL render thinking, tool_call, tool_result, and answer events in real-time
3. WHEN receiving thinking or tool_call events THEN THE Frontend SHALL render them in a collapsible "Thought Process" component with a pulsing indicator
4. WHEN a tool_call involves web_search THEN THE Frontend SHALL display the search query and a "Searching Web" indicator
5. WHEN the answer contains citations (e.g., [[citation:doc_id:chunk_id]]) THEN THE Frontend SHALL render them as clickable interactive badges (e.g., [1])
6. THE Frontend SHALL support Markdown rendering including tables, code blocks, and mathematical formulas (LaTeX)
7. IF an error event is received THEN THE Frontend SHALL display the error message and allow retry
8. WHEN the agent is generating or thinking THEN THE Frontend SHALL display a "Stop Generating" button to allow user interruption
9. Each Agent response SHALL include Thumbs Up and Thumbs Down buttons for user feedback
10. WHEN feedback is clicked THEN THE Frontend SHALL send the feedback to the backend for optimization

### Requirement 4: 订阅与积分管理

**User Story:** As a user, I want to view my subscription status and remaining credits, so that I can manage my usage.

#### Acceptance Criteria

1. WHEN a user views the subscription page THEN THE Frontend SHALL display current plan, features, and remaining credits
2. WHEN a user selects a plan to upgrade THEN THE Frontend SHALL initiate checkout via /api/subscription/checkout
3. WHEN credits are insufficient THEN THE Frontend SHALL display a clear message with upgrade options
4. WHEN a user has API access feature THEN THE Frontend SHALL allow creating and managing API keys

### Requirement 5: 响应式设计与用户体验

**User Story:** As a user, I want to use the application on any device, so that I can access my documents anywhere.

#### Acceptance Criteria

1. THE Frontend SHALL adapt layout for desktop (>1024px), tablet (768-1024px), and mobile (<768px) viewports
2. ON desktop viewports THE Frontend SHALL employ a Three-Pane Layout (Navigation Sidebar + Chat Area + Evidence Board) to maximize information density and workflow efficiency
3. WHEN loading data THEN THE Frontend SHALL display skeleton loaders or spinners to indicate progress
4. WHEN an API call fails THEN THE Frontend SHALL display a toast notification with error details
5. THE Frontend SHALL support dark mode and light mode themes
6. THE Frontend SHALL provide keyboard navigation for accessibility compliance

### Requirement 6: 对话历史与上下文

**User Story:** As a user, I want to see my conversation history, so that I can continue previous discussions across documents.

#### Acceptance Criteria

1. WHEN a user starts a new conversation THEN THE Frontend SHALL create a new chat session
2. WHEN viewing a knowledge base THEN THE Frontend SHALL display previous conversations that span multiple documents
3. WHEN a user sends a message THEN THE Frontend SHALL append it to the current conversation thread
4. THE Frontend SHALL persist conversation history locally for offline access
5. THE Frontend SHALL automatically generate a short descriptive title for each new conversation
6. THE Frontend SHALL allow users to organize chats into sessions or threads that reference multiple documents simultaneously

### Requirement 7: 前端状态管理与数据序列化

**User Story:** As a developer, I want reliable state management, so that the application behaves predictably.

#### Acceptance Criteria

1. THE Frontend SHALL use a centralized state management solution for global state
2. WHEN serializing state to localStorage THEN THE Frontend SHALL use JSON format
3. WHEN deserializing state from localStorage THEN THE Frontend SHALL validate and parse JSON correctly
4. THE Frontend SHALL implement a pretty-printer for debugging state in development mode

### Requirement 8: 动态证据看板 (Evidence Board)

**User Story:** As a user, I want to verify the agent's answers against the original sources, so that I can trust the information.

#### Acceptance Criteria

1. THE Frontend SHALL provide a split-screen layout or toggleable side panel to display document content alongside the chat
2. WHEN a user clicks a citation badge [1] in the chat THEN THE Frontend SHALL automatically open the corresponding document in the side panel
3. WHEN a citation is clicked THEN THE Frontend SHALL scroll to the specific page containing the cited chunk
4. WHEN a citation is clicked THEN THE Frontend SHALL highlight the relevant text segment visually
5. WHEN the citation source is a PDF THEN THE Frontend SHALL use a PDF viewer component to render it
6. WHEN the citation source is a Web Search result THEN THE Frontend SHALL display the snippet in a readable card format
7. ON mobile devices THEN THE Frontend SHALL open the Evidence Board as a slide-over sheet or tabbed view instead of split-screen

### Requirement 9: 意图路由反馈 (Intent Routing Feedback)

**User Story:** As a user, I want to see what the agent is doing, so that I understand how my question is being processed.

#### Acceptance Criteria

1. WHEN the Router determines the intent type THEN THE Frontend SHALL display an appropriate status indicator (e.g., "Searching documents", "Searching web", "Analyzing")
2. WHEN the agent switches between tools THEN THE Frontend SHALL update the status indicator in real-time
3. THE Frontend SHALL display tool-specific icons for different operations (document search, web search, calculation)
