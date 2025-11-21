from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional, Protocol, TypedDict

from openai import OpenAI

DEFAULT_DIMENSIONS = ["tech", "econ", "team", "risk"]
MIN_QUESTIONS = 3
MAX_QUESTIONS = 5
ANALYZER_MODEL = "gpt-4-turbo"

FALLBACK_QUERIES: Dict[str, List[str]] = {
    "tech": [
        "项目的共识机制是什么？如何保证安全性？",
        "智能合约或执行环境如何实现扩展性？",
        "核心技术组件是否经过审计或开源？",
    ],
    "econ": [
        "代币的初始分配和解锁计划是什么？",
        "项目通过哪些机制捕获价值？",
        "是否存在通胀/通缩或销毁机制？",
    ],
    "team": [
        "核心成员过往在区块链行业的经验如何？",
        "顾问或投资方有哪些标志性背景？",
        "社区和开发者生态是否活跃？",
    ],
    "risk": [
        "项目在技术上存在哪些潜在风险？",
        "市场竞争与定位有哪些不确定性？",
        "是否面临监管或合规方面的挑战？",
    ],
}

DIMENSION_PROMPTS: Dict[str, str] = {
    "tech": """分析技术架构，重点关注：
1. 共识机制及其创新点
2. 智能合约平台和开发语言
3. 可扩展性方案（Layer 2、分片等）
4. 安全性设计和审计情况
输出 Markdown 格式报告，包含评分 (0-100)。""",
    "econ": """分析经济模型，重点关注：
1. 代币分配和解锁计划
2. 通胀/通缩机制
3. 激励模型和质押机制
4. 价值捕获和代币效用
输出 Markdown 格式报告，包含评分 (0-100)。""",
    "team": """分析团队背景，重点关注：
1. 核心成员的技术和行业经验
2. 顾问团队的影响力
3. 合作伙伴和投资方
4. 社区活跃度和开发进展
输出 Markdown 格式报告，包含评分 (0-100)。""",
    "risk": """评估风险因素，重点关注：
1. 技术风险（安全漏洞、可扩展性瓶颈）
2. 市场风险（竞争对手、市场定位）
3. 监管风险（合规性、法律不确定性）
4. 执行风险（团队能力、路线图可行性）
输出 Markdown 格式报告，包含风险等级 (低/中/高)。""",
}


class AnalysisState(TypedDict, total=False):
    document_id: str
    user_id: str
    dimensions: List[str]
    sub_queries: Dict[str, List[str]]
    retrieved_contexts: Dict[str, str]
    analysis_results: Dict[str, str]
    final_report: Dict


class RAGRetriever(Protocol):
    def get_relevant_chunks(
        self, question: str, document_id: str, user_id: str, k: int = 5
    ) -> List[Dict]:
        ...


def make_generate_sub_queries(openai_client: Optional[OpenAI] = None):
    """Factory to inject OpenAI client dependency into the planner node."""

    client = openai_client or OpenAI()

    def generate_sub_queries(state: AnalysisState) -> Dict[str, Dict[str, List[str]]]:
        """Planner node: produce 3-5 focused questions per dimension."""

        dimensions = _resolve_dimensions(state.get("dimensions"))
        raw_queries = _request_sub_queries(client, dimensions)
        normalized = _normalize_queries(dimensions, raw_queries)
        return {"sub_queries": normalized}

    return generate_sub_queries


def _resolve_dimensions(dimensions: Optional[List[str]]) -> List[str]:
    if not dimensions:
        return DEFAULT_DIMENSIONS.copy()
    cleaned = []
    for dim in dimensions:
        if isinstance(dim, str):
            value = dim.strip().lower()
            if value:
                cleaned.append(value)
    return cleaned or DEFAULT_DIMENSIONS.copy()


def _request_sub_queries(client: OpenAI, dimensions: List[str]) -> Dict[str, List[str]]:
    dimension_text = ", ".join(dimensions)
    user_prompt = (
        "基于区块链白皮书分析需要，针对以下维度生成 3-5 个具体问题，"
        "用于后续检索相关上下文："
        f"\n维度: {dimension_text}\n"
        "返回 JSON，对象的 key 为维度，值为问题数组。"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "你是一名擅长区块链投研的分析师，回答需使用中文。",
            },
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("LLM 返回结果无法解析为 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM 返回的 JSON 不是对象类型")
    return {str(key).lower(): value for key, value in payload.items()}


def _normalize_queries(dimensions: List[str], raw: Dict[str, List[str]]) -> Dict[str, List[str]]:
    normalized: Dict[str, List[str]] = {}
    for dim in dimensions:
        candidate = raw.get(dim, [])
        cleaned = [
            item.strip()
            for item in candidate
            if isinstance(item, str) and item.strip()
        ]
        if len(cleaned) < MIN_QUESTIONS:
            fallback = FALLBACK_QUERIES.get(dim, FALLBACK_QUERIES["tech"])
            for question in fallback:
                if question not in cleaned:
                    cleaned.append(question)
                if len(cleaned) >= MIN_QUESTIONS:
                    break
        normalized[dim] = cleaned[:MAX_QUESTIONS]
    return normalized


def make_retrieve_all_contexts(rag_service: RAGRetriever, top_k: int = 5):
    """Factory that injects a RAGService-like dependency for context retrieval."""

    if rag_service is None:
        raise ValueError("rag_service is required for retrieve_all_contexts")

    def retrieve_all_contexts(state: AnalysisState) -> Dict[str, Dict[str, str]]:
        document_id = state.get("document_id")
        user_id = state.get("user_id")
        sub_queries = state.get("sub_queries") or {}

        if not document_id or not user_id:
            raise ValueError("document_id and user_id are required in state")
        if not sub_queries:
            raise ValueError("sub_queries must be populated before retrieval")

        contexts: Dict[str, str] = {}
        for dimension, queries in sub_queries.items():
            collected = _collect_chunks_for_dimension(
                rag_service, queries, document_id, user_id, top_k
            )
            contexts[dimension] = _merge_chunks_with_section_path(collected)
        return {"retrieved_contexts": contexts}

    return retrieve_all_contexts


def _collect_chunks_for_dimension(
    rag_service: RAGRetriever,
    queries: List[str],
    document_id: str,
    user_id: str,
    top_k: int,
) -> List[Dict]:
    unique: Dict[str, Dict] = {}
    for query in queries:
        chunks = rag_service.get_relevant_chunks(
            question=query,
            document_id=document_id,
            user_id=user_id,
            k=top_k,
        ) or []
        for chunk in chunks:
            chunk_id = str(chunk.get("id") or _hash_chunk(chunk))
            if chunk_id not in unique:
                unique[chunk_id] = chunk

    ordered = sorted(
        unique.values(),
        key=lambda c: (
            c.get("metadata", {}).get("section_path", ""),
            int(c.get("metadata", {}).get("chunk_index", 0)),
        ),
    )
    return ordered


def _merge_chunks_with_section_path(chunks: List[Dict]) -> str:
    parts: List[str] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        section = metadata.get("section_path", "unknown")
        text = chunk.get("text", "")
        if not text:
            continue
        parts.append(f"[来源: {section}]\n{text.strip()}")
    return "\n\n---\n\n".join(parts)


def _hash_chunk(chunk: Dict) -> int:
    metadata = chunk.get("metadata", {})
    return hash(
        (
            metadata.get("section_path"),
            metadata.get("chunk_index"),
            chunk.get("text"),
        )
    )


def make_analyze_dimension(openai_client: Optional[OpenAI] = None):
    """Factory that injects OpenAI client for analyzer nodes."""

    client = openai_client or OpenAI()

    def analyze_dimension(
        state: AnalysisState, dimension: str
    ) -> Dict[str, Dict[str, str]]:
        dimension = dimension.lower()
        prompt_template = DIMENSION_PROMPTS.get(dimension)
        if not prompt_template:
            raise ValueError(f"Unsupported analysis dimension: {dimension}")

        contexts = state.get("retrieved_contexts") or {}
        queries = state.get("sub_queries") or {}
        context = contexts.get(dimension)
        question_list = queries.get(dimension)

        if not context or not question_list:
            raise ValueError(f"Missing context or questions for dimension {dimension}")

        prompt = _build_analyzer_prompt(question_list, context, prompt_template)
        response = client.chat.completions.create(
            model=ANALYZER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一名资深的区块链研究员，请提供结构化中文分析。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.3,
        )

        report = response.choices[0].message.content.strip()
        current_results = dict(state.get("analysis_results") or {})
        current_results[dimension] = report
        return {"analysis_results": current_results}

    return analyze_dimension


def make_dimension_analyzers(
    analyze_dimension_fn: Callable[[AnalysisState, str], Dict[str, Dict[str, str]]],
) -> Dict[str, Callable[[AnalysisState], Dict[str, Dict[str, str]]]]:
    """Helper to create LangGraph nodes per dimension with shared analyzer."""

    def _wrap(dimension: str):
        def node(state: AnalysisState) -> Dict[str, Dict[str, str]]:
            return analyze_dimension_fn(state, dimension)

        return node

    return {
        "analyze_tech": _wrap("tech"),
        "analyze_econ": _wrap("econ"),
        "analyze_team": _wrap("team"),
        "analyze_risk": _wrap("risk"),
    }


def _build_analyzer_prompt(queries: List[str], context: str, instructions: str) -> str:
    bullet_questions = "\n".join(f"- {q}" for q in queries)
    return (
        "基于以下上下文回答问题并生成分析报告。\n\n"
        f"问题:\n{bullet_questions}\n\n"
        f"上下文:\n{context}\n\n"
        f"分析要求:\n{instructions}"
    )


def make_synthesize_final_report(openai_client: Optional[OpenAI] = None):
    """Factory for the final synthesizer node using GPT-4o-mini JSON output."""

    client = openai_client or OpenAI()

    def synthesize_final_report(state: AnalysisState) -> Dict[str, Dict]:
        reports = state.get("analysis_results") or {}
        dimensions = state.get("dimensions") or DEFAULT_DIMENSIONS

        if len(reports) < len(dimensions):
            # Wait for all analyzers to finish; LangGraph will re-run when ready
            return {}

        prompt = _build_synthesis_prompt(reports)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是资深投研分析师，请根据输入生成结构化结论。",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
            temperature=0.2,
        )

        payload = response.choices[0].message.content
        synthesis = json.loads(payload)
        final_report = {
            **synthesis,
            "technology_analysis": reports.get("tech"),
            "economics_analysis": reports.get("econ"),
            "team_analysis": reports.get("team"),
            "risk_analysis": reports.get("risk"),
        }
        return {"final_report": final_report}

    return synthesize_final_report


def _build_synthesis_prompt(reports: Dict[str, str]) -> str:
    return f"""
基于以下各维度的分析报告生成综合评估:

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
""".strip()

