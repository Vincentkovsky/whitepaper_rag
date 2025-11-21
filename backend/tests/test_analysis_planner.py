import json

import pytest

from backend.app.workflows.analysis_workflow import (
    DEFAULT_DIMENSIONS,
    make_analyze_dimension,
    make_dimension_analyzers,
    make_generate_sub_queries,
    make_retrieve_all_contexts,
    make_synthesize_final_report,
)


class FakeOpenAI:
    def __init__(self, payload: dict):
        self._payload = payload
        self.chat = self.Chat(self._payload)

    class Chat:
        def __init__(self, payload: dict):
            self.completions = FakeOpenAI.Completions(payload)

    class Completions:
        def __init__(self, payload: dict):
            self._payload = payload

        def create(self, **kwargs):
            return FakeResponse(json.dumps(self._payload))


class FakeResponse:
    def __init__(self, content: str):
        self.choices = [FakeChoice(content)]


class FakeChoice:
    def __init__(self, content: str):
        self.message = FakeMessage(content)


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeOpenAIText:
    def __init__(self, text: str):
        self.text = text
        self.chat = self.Chat(self.text)

    class Chat:
        def __init__(self, text: str):
            self.completions = FakeOpenAIText.Completions(text)

    class Completions:
        def __init__(self, text: str):
            self.text = text

        def create(self, **kwargs):
            return FakeResponse(self.text)


class FakeOpenAIJSON:
    def __init__(self, payload: dict):
        self.payload = payload
        self.chat = self.Chat(self.payload)

    class Chat:
        def __init__(self, payload: dict):
            self.completions = FakeOpenAIJSON.Completions(payload)

    class Completions:
        def __init__(self, payload: dict):
            self.payload = payload

        def create(self, **kwargs):
            return FakeResponse(json.dumps(self.payload))


class FakeRAGService:
    def __init__(self, responses: dict[str, list[dict]]):
        self.responses = responses

    def get_relevant_chunks(self, question: str, document_id: str, user_id: str, k: int = 5):
        return self.responses.get(question, [])


def test_generate_sub_queries_returns_expected_keys():
    payload = {
        "tech": ["问题1", "问题2", "问题3"],
        "econ": ["问题1", "问题2", "问题3"],
    }
    client = FakeOpenAI(payload)
    planner_node = make_generate_sub_queries(client)

    result = planner_node({"dimensions": ["tech", "econ"]})
    assert set(result["sub_queries"].keys()) == {"tech", "econ"}
    assert all(len(queries) == 3 for queries in result["sub_queries"].values())


def test_generate_sub_queries_falls_back_when_llm_missing_dimension():
    payload = {
        "tech": ["问题1", "问题2"],  # 少于最小数量
    }
    client = FakeOpenAI(payload)
    planner_node = make_generate_sub_queries(client)

    result = planner_node({"dimensions": ["tech", "risk"]})
    assert len(result["sub_queries"]["tech"]) >= 3
    # risk 维度完全缺失，应使用 fallback
    assert len(result["sub_queries"]["risk"]) >= 3


def test_generate_sub_queries_defaults_dimensions():
    payload = {dim: [f"{dim}-q{i}" for i in range(6)] for dim in DEFAULT_DIMENSIONS}
    client = FakeOpenAI(payload)
    planner_node = make_generate_sub_queries(client)

    result = planner_node({})
    assert set(result["sub_queries"].keys()) == set(DEFAULT_DIMENSIONS)
    assert all(len(queries) == 5 for queries in result["sub_queries"].values())


def test_retrieve_all_contexts_deduplicates_and_formats():
    chunk = {
        "id": "chunk-1",
        "text": "内容 A",
        "metadata": {"section_path": "1. 技术/共识", "chunk_index": 0},
    }
    responses = {
        "Q1": [chunk, chunk],  # duplicate
        "Q2": [
            {
                "id": "chunk-2",
                "text": "内容 B",
                "metadata": {"section_path": "2. 经济/代币", "chunk_index": 1},
            }
        ],
    }
    rag = FakeRAGService(responses)
    node = make_retrieve_all_contexts(rag)

    state = {
        "document_id": "doc-1",
        "user_id": "user-1",
        "sub_queries": {"tech": ["Q1", "Q2"]},
    }
    result = node(state)
    context = result["retrieved_contexts"]["tech"]
    assert context.count("[来源:") == 2
    assert "内容 A" in context and "内容 B" in context
    assert context.index("内容 A") < context.index("内容 B")


def test_analyze_dimension_updates_results():
    client = FakeOpenAIText("技术报告 #1")
    analyze_fn = make_analyze_dimension(client)
    state = {
        "retrieved_contexts": {"tech": "上下文"},
        "sub_queries": {"tech": ["Q1", "Q2"]},
        "analysis_results": {"econ": "旧报告"},
    }
    result = analyze_fn(state, "tech")
    assert result["analysis_results"]["econ"] == "旧报告"
    assert result["analysis_results"]["tech"] == "技术报告 #1"


def test_dimension_analyzers_invoke_base_function():
    calls = []

    def fake_base(state, dimension):
        calls.append(dimension)
        return {"analysis_results": {dimension: "ok"}}

    analyzers = make_dimension_analyzers(fake_base)
    analyzers["analyze_risk"]({})
    assert calls == ["risk"]


def test_synthesize_final_report_waits_for_all_reports():
    client = FakeOpenAIJSON(
        {
            "overall_score": 90,
            "strengths": ["s1", "s2"],
            "risks": ["r1"],
            "recommendation": "buy",
        }
    )
    synthesize = make_synthesize_final_report(client)
    state_incomplete = {"analysis_results": {"tech": "报告"}, "dimensions": ["tech", "econ"]}
    assert synthesize(state_incomplete) == {}

    state = {
        "analysis_results": {"tech": "报告", "econ": "报告2"},
        "dimensions": ["tech", "econ"],
    }
    result = synthesize(state)
    final = result["final_report"]
    assert final["overall_score"] == 90
    assert final["technology_analysis"] == "报告"

