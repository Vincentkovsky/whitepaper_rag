# Implementation Plan

## Phase 1: Core Infrastructure

- [x] 1. Set up project structure and base interfaces
  - [x] 1.1 Create agent module directory structure
    - Create `backend/app/agent/` directory with `__init__.py`
    - Create subdirectories: `tools/`, `retrieval/`, `tracing/`
    - _Requirements: 2.1, 4.1_
  - [x] 1.2 Define core interfaces and types
    - Create `backend/app/agent/types.py` with IntentType, IntentClassification, ToolSchema, Tool, AgentResponse, AgentStreamEvent, ThoughtStep
    - Create `backend/app/agent/protocols.py` with Protocol definitions
    - _Requirements: 2.1, 3.1_
  - [x] 1.3 Write property test for type serialization round-trip
    - **Property 14: Template Serialization Round-Trip**
    - **Validates: Requirements 5.3**

## Phase 2: Tool Registry and Built-in Tools

- [-] 2. Implement Tool Registry
  - [x] 2.1 Create ToolRegistry class
    - Implement register(), get(), list_tools(), invoke() methods
    - Add error handling for missing tools
    - _Requirements: 2.1_
  - [x] 2.2 Write property test for tool registry round-trip
    - **Property 3: Tool Registry Round-Trip**
    - **Validates: Requirements 2.1**
  - [x] 2.3 Implement document_search tool
    - Create `backend/app/agent/tools/document_search.py`
    - Integrate with existing RAGService.get_relevant_chunks()
    - _Requirements: 2.3_
  - [x] 2.4 Implement web_search tool
    - Create `backend/app/agent/tools/web_search.py`
    - Integrate with Tavily API (with fallback to SerpApi)
    - Add TAVILY_API_KEY to config
    - _Requirements: 2.5_
  - [x] 2.5 Write property test for tool failure resilience
    - **Property 5: Tool Failure Resilience**
    - **Validates: Requirements 2.4**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Hybrid Retrieval

- [ ] 4. Implement BM25 Search
  - [x] 4.1 Create unified tokenizer utility
    - Create `backend/app/agent/retrieval/tokenizer.py`
    - Implement `tokenize(text: str) -> List[str]` function
    - Use jieba for Chinese text detection and segmentation
    - Use whitespace + punctuation split for English
    - Add language detection (simple heuristic: CJK character ratio)
    - **Critical**: This MUST be the single source of truth for both indexing and querying
    - _Requirements: 6.2_
  - [x] 4.2 Create BM25 index service
    - Create `backend/app/agent/retrieval/bm25_service.py`
    - Use the unified tokenizer from 4.1 for both index building and query processing
    - Use rank_bm25 library for BM25Okapi
    - _Requirements: 6.2_
  - [x] 4.3 Implement BM25 index persistence
    - Create `backend/app/agent/retrieval/bm25_store.py`
    - Implement save/load with Pickle serialization
    - Storage path: `backend/app/storage/bm25_indexes/{document_id}.pkl`
    - _Requirements: 6.2_
  - [x] 4.4 Integrate BM25 indexing into document pipeline
    - **Modify existing file**: `backend/app/services/embedding_service.py`
    - Add BM25 index building after embedding generation
    - Call IndexManager.index_document() for atomic dual-store write
    - _Requirements: 6.2_
  - [x] 4.5 Implement dual-store transaction mechanism
    - Create `backend/app/agent/retrieval/index_manager.py`
    - Implement atomic index_document() with rollback on failure
    - Implement atomic delete_document() for both stores
    - Add try-except-rollback pattern for consistency
    - _Requirements: 6.2_
  - [x] 4.6 Create reconciliation script
    - Create `backend/scripts/reconcile_indexes.py`
    - Compare ChromaDB document IDs with BM25 index files
    - Report orphaned entries and missing indexes
    - Optionally auto-fix inconsistencies
    - _Requirements: 6.2_

- [x] 5. Implement Hybrid Retriever
  - [x] 5.1 Create HybridRetriever class
    - Create `backend/app/agent/retrieval/hybrid_retriever.py`
    - Implement vector search using existing ChromaDB
    - Implement BM25 search using BM25Service
    - _Requirements: 6.1, 6.2_
  - [x] 5.2 Implement RRF fusion algorithm
    - Implement _rrf_fusion() method
    - Support configurable vector_weight and bm25_weight
    - Default weights: 0.7 vector, 0.3 BM25
    - _Requirements: 6.3, 6.4_
  - [x] 5.3 Write property test for hybrid search fusion
    - **Property 15: Hybrid Search Fusion**
    - **Validates: Requirements 6.1, 6.2, 6.3**
  - [x] 5.4 Write property test for search weight configuration
    - **Property 16: Search Weight Configuration**
    - **Validates: Requirements 6.4**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Intent Router

- [x] 7. Implement Intent Router
  - [x] 7.1 Create IntentRouter class
    - Create `backend/app/agent/router.py`
    - Implement classify() method using LLM
    - Add confidence threshold (0.8) for fallback mechanism
    - _Requirements: 2.6_
  - [x] 7.2 Implement small-talk detection
    - Create pattern matching for common greetings
    - Add LLM-based classification for ambiguous cases
    - _Requirements: 2.6_
  - [x] 7.3 Write property test for router small-talk bypass
    - **Property 6: Router Small-Talk Bypass**
    - **Validates: Requirements 2.6**

## Phase 5: ReAct Agent

- [x] 8. Implement ReAct Agent core
  - [x] 8.1 Create ReActAgent class
    - Create `backend/app/agent/react_agent.py`
    - Implement reasoning loop with tool calling
    - Integrate with ToolRegistry
    - _Requirements: 2.2, 3.1_
  - [x] 8.2 Implement step limit enforcement
    - Add max_steps parameter (default: 10)
    - Stop execution when limit reached
    - _Requirements: 3.3_
  - [x] 8.3 Write property test for step limit invariant
    - **Property 9: Step Limit Invariant**
    - **Validates: Requirements 3.3**
  - [x] 8.4 Implement state management across steps
    - Maintain conversation history and observations
    - Pass context between reasoning steps
    - _Requirements: 3.2_
  - [x] 8.5 Write property test for state preservation
    - **Property 8: State Preservation Across Steps**
    - **Validates: Requirements 3.2**
  - [x] 8.6 Implement final answer synthesis
    - Synthesize comprehensive answer from all observations
    - _Requirements: 3.4_
  - [x] 8.7 Write property test for final answer synthesis
    - **Property 10: Final Answer Synthesis**
    - **Validates: Requirements 3.4**

- [x] 9. Implement streaming support
  - [x] 9.1 Create async stream generator
    - Implement stream() method returning AsyncIterator[AgentStreamEvent]
    - Emit events for: thinking, tool_call, tool_result, answer
    - _Requirements: 1.1_
  - [x] 9.2 Write property test for stream initiation latency
    - **Property 1: Stream Initiation Latency**
    - **Validates: Requirements 1.1**

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: Execution Tracing

- [x] 11. Implement Execution Tracer
  - [x] 11.1 Create ExecutionTracer class
    - Create `backend/app/agent/tracing/tracer.py`
    - Implement start_span(), end_span(), get_trace()
    - Record latency for each span
    - _Requirements: 8.1, 8.3_
  - [x] 11.2 Implement LangSmith/LangFuse export
    - Implement export_langsmith() method
    - Conform to expected schema
    - _Requirements: 8.1_
  - [x] 11.3 Write property test for trace format compliance
    - **Property 19: Trace Format Compliance**
    - **Validates: Requirements 8.1**
  - [x] 11.4 Write property test for latency metrics recording
    - **Property 21: Latency Metrics Recording**
    - **Validates: Requirements 8.3**

## Phase 7: Remove Domain-Specific Logic

- [x] 12. Refactor RAGService for domain-agnostic operation
  - [x] 12.1 Remove blockchain-specific prompts
    - **Modify existing file**: `backend/app/services/rag_service.py`
    - Update _generate_answer() to use configurable prompts
    - Remove hardcoded "比特币白皮书专家" prompt
    - Replace with PromptTemplate injection
    - _Requirements: 4.2, 4.3_
  - [x] 12.2 Create configurable prompt templates
    - Create `backend/app/agent/prompts.py`
    - Define PromptTemplate class with customizable system/user prompts
    - _Requirements: 4.3_
  - [x] 12.3 Write property test for configurable prompts
    - **Property 11: Configurable Prompts**
    - **Validates: Requirements 4.3**

- [-] 13. Remove analysis_workflow.py
  - [x] 13.1 Delete blockchain-specific workflow
    - **Delete file**: `backend/app/workflows/analysis_workflow.py`
    - Remove related imports and dependencies
    - _Requirements: 4.1_
  - [x] 13.2 Update task queue references
    - **Modify existing file**: `backend/app/tasks/document_tasks.py`
    - Remove enqueue_generate_analysis function
    - Remove imports from analysis_workflow
    - _Requirements: 4.4_
  - [x] 13.3 Update QA routes
    - **Modify existing file**: `backend/app/api/routes/qa.py`
    - Remove or deprecate /api/qa/analysis/* endpoints
    - Keep /api/qa/query endpoint functional
    - _Requirements: 4.4_

## Phase 8: Extensible Analysis Framework

- [x] 14. Implement Analysis Template system
  - [x] 14.1 Create AnalysisTemplate model
    - Create `backend/app/agent/templates/analysis_template.py`
    - Define AnalysisTemplate with name, description, dimensions, prompts, output_schema
    - _Requirements: 5.1_
  - [x] 14.2 Implement template registry
    - Create template registration and retrieval
    - Support loading from JSON/YAML files
    - _Requirements: 5.2, 5.3_
  - [x] 14.3 Write property test for template lifecycle
    - **Property 13: Analysis Template Lifecycle**
    - **Validates: Requirements 5.1, 5.2**
  - [x] 14.4 Create default general-purpose template
    - Create `backend/app/agent/templates/default.yaml`
    - Generic analysis dimensions (summary, key_points, questions)
    - _Requirements: 5.4_

- [ ] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 9: API Layer

- [x] 16. Create Agent API endpoints
  - [x] 16.1 Create agent router
    - Create `backend/app/api/routes/agent.py`
    - Add POST /api/agent/chat endpoint
    - Add POST /api/agent/chat/stream endpoint (SSE)
    - _Requirements: 7.2_
  - [x] 16.2 Implement trace parameter support
    - Add optional trace query parameter
    - Include intermediate_steps in response when trace=true
    - _Requirements: 8.2_
  - [x] 16.3 Write property test for intermediate steps inclusion
    - **Property 20: Intermediate Steps Inclusion**
    - **Validates: Requirements 8.2**

- [x] 17. Register agent router in main app
  - **Modify existing file**: `backend/app/main.py`
  - Import and include agent router
  - _Requirements: 7.2_

## Phase 10: Configuration and Integration

- [x] 18. Update configuration
  - [x] 18.1 Add new config options
    - Add TAVILY_API_KEY for web search
    - Add AGENT_MAX_STEPS (default: 10)
    - Add VECTOR_WEIGHT, BM25_WEIGHT for hybrid search
    - Add ROUTER_CONFIDENCE_THRESHOLD (default: 0.8)
    - _Requirements: 2.5, 3.3, 6.4, 2.6_
  - [x] 18.2 Update Settings class
    - **Modify existing file**: `backend/app/core/config.py`
    - Add new fields: tavily_api_key, agent_max_steps, vector_weight, bm25_weight, router_confidence_threshold
    - _Requirements: 2.5, 3.3, 6.4_

- [x] 19. Final integration
  - [x] 19.1 Wire up all components
    - Create AgentService that orchestrates Router, Agent, Retriever, Tracer
    - Add dependency injection in API routes
    - _Requirements: 1.1, 2.2, 3.1_
  - [x] 19.2 Write property test for bilingual support
    - **Property 2: Bilingual Query Support**
    - **Validates: Requirements 1.4**
  - [x] 19.3 Write property test for tool result incorporation
    - **Property 4: Tool Result Incorporation**
    - **Validates: Requirements 2.2**
  - [x] 19.4 Write property test for complex query decomposition
    - **Property 7: Complex Query Decomposition**
    - **Validates: Requirements 3.1**

- [x] 20. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
