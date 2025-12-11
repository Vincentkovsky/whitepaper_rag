"""RAG Evaluation Service using RAGAS framework."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    ContextPrecision,
    ContextRecall,
)

from ..core.config import get_settings


@dataclass
class EvaluationSample:
    """A single evaluation sample."""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None


@dataclass
class EvaluationResult:
    """Evaluation results with metrics."""
    faithfulness: float
    response_relevancy: float
    context_precision: float
    context_recall: Optional[float]
    overall_score: float
    sample_count: int
    timestamp: str
    details: List[Dict[str, Any]]
    answer_model: str = ""
    judge_model: str = ""
    embedding_model: str = ""


class RAGEvaluationService:
    """Service for evaluating RAG pipeline quality using RAGAS."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger("app.services.evaluation")
        self._llm = None
        self._embeddings = None

    def _get_llm(self):
        """Get LLM wrapper for RAGAS (requires langchain). Uses Gemini 2.5 Pro as judge."""
        if self._llm is None:
            if self.settings.llm_provider == "gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI
                # Use Gemini 2.5 Pro as the judge model for better evaluation quality
                llm = ChatGoogleGenerativeAI(
                    model=self.settings.gemini_model_pro,  # gemini-2.5-pro
                    google_api_key=self.settings.google_api_key,
                )
            else:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=self.settings.openai_model_turbo,  # gpt-4-turbo for judge
                    api_key=self.settings.openai_api_key,
                )
            self._llm = LangchainLLMWrapper(llm)
        return self._llm

    def _get_embeddings(self):
        """Get embeddings wrapper for RAGAS (requires langchain)."""
        if self._embeddings is None:
            if self.settings.embedding_provider == "gemini":
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                embeddings = GoogleGenerativeAIEmbeddings(
                    model=f"models/{self.settings.gemini_embedding_model}",
                    google_api_key=self.settings.google_api_key,
                )
            else:
                from langchain_openai import OpenAIEmbeddings
                embeddings = OpenAIEmbeddings(
                    model=self.settings.embedding_model_openai,
                    api_key=self.settings.openai_api_key,
                )
            self._embeddings = LangchainEmbeddingsWrapper(embeddings)
        return self._embeddings

    def evaluate_samples(
        self,
        samples: List[EvaluationSample],
        include_ground_truth: bool = False,
    ) -> EvaluationResult:
        """
        Evaluate a list of RAG samples.
        
        Args:
            samples: List of EvaluationSample objects
            include_ground_truth: Whether to include context_recall (requires ground_truth)
        
        Returns:
            EvaluationResult with metrics
        """
        # Build RAGAS dataset
        ragas_samples = []
        for sample in samples:
            ragas_sample = SingleTurnSample(
                user_input=sample.question,
                response=sample.answer,
                retrieved_contexts=sample.contexts,
            )
            if include_ground_truth and sample.ground_truth:
                ragas_sample.reference = sample.ground_truth
            ragas_samples.append(ragas_sample)

        dataset = EvaluationDataset(samples=ragas_samples)

        # Select metrics
        metrics = [
            Faithfulness(),
            ResponseRelevancy(strictness= 1),
            ContextPrecision(),
        ]
        if include_ground_truth:
            metrics.append(ContextRecall())

        # Run evaluation
        self.logger.info(f"Running RAGAS evaluation on {len(samples)} samples")
        
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=self._get_llm(),
            embeddings=self._get_embeddings(),
        )

        # Extract scores (fill NaN with 0 before calculating mean)
        df = result.to_pandas()
        
        if "faithfulness" in df:
            faithfulness = df["faithfulness"].fillna(0.0).mean()
        else:
            faithfulness = 0.0
        
        if "response_relevancy" in df:
            response_relevancy = df["response_relevancy"].fillna(0.0).mean()
        else:
            response_relevancy = 0.0
        
        if "context_precision" in df:
            context_precision = df["context_precision"].fillna(0.0).mean()
        else:
            context_precision = 0.0
        
        if "context_recall" in df and include_ground_truth:
            context_recall = df["context_recall"].fillna(0.0).mean()
        else:
            context_recall = None

        # Calculate overall score
        scores = [faithfulness, response_relevancy, context_precision]
        if context_recall is not None:
            scores.append(context_recall)
        overall_score = sum(scores) / len(scores)

        # Build details
        details = df.to_dict(orient="records")

        # Get model names for report
        if self.settings.llm_provider == "gemini":
            judge_model = self.settings.gemini_model_pro
            embedding_model = self.settings.gemini_embedding_model
        else:
            judge_model = self.settings.openai_model_turbo
            embedding_model = self.settings.embedding_model_openai

        return EvaluationResult(
            faithfulness=round(faithfulness, 4),
            response_relevancy=round(response_relevancy, 4),
            context_precision=round(context_precision, 4),
            context_recall=round(context_recall, 4) if context_recall else None,
            overall_score=round(overall_score, 4),
            sample_count=len(samples),
            timestamp=datetime.utcnow().isoformat(),
            details=details,
            judge_model=judge_model,
            embedding_model=embedding_model,
        )

    def evaluate_from_rag_service(
        self,
        rag_service,
        document_id: str,
        user_id: str,
        test_questions: List[str],
        ground_truths: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Evaluate RAG service with test questions.
        
        Args:
            rag_service: RAGService instance
            document_id: Document to query
            user_id: User ID for access control
            test_questions: List of test questions
            ground_truths: Optional list of expected answers
        
        Returns:
            EvaluationResult
        """
        samples = []
        
        # Clear chunk cache for fresh retrieval during evaluation
        from .cache_service import chunks_cache_key
        
        for i, question in enumerate(test_questions):
            # Clear cache for this question to ensure fresh retrieval
            cache_key = chunks_cache_key(document_id, question)
            try:
                rag_service.cache.delete(cache_key)
            except Exception:
                pass  # Cache might not be available
            
            # Get RAG response (fresh, not cached)
            chunks = rag_service.get_relevant_chunks(
                question=question,
                document_id=document_id,
                user_id=user_id,
                k=5,
            )
            
            # Debug: log chunk retrieval
            print(f"[{i+1}/{len(test_questions)}] Q: {question[:40]}... -> {len(chunks)} chunks")
            
            if not chunks:
                print(f"  ⚠️ No chunks retrieved! Check document_id={document_id}, user_id={user_id}")
            
            reranked = rag_service.rerank_chunks(question, chunks) if chunks else []
            context = rag_service.build_context(reranked[:5]) if reranked else ""
            
            answer_data = rag_service._generate_answer(
                question=question,
                context=context,
                model="mini",
                temperature=0.2,
            )
            
            sample = EvaluationSample(
                question=question,
                answer=answer_data["answer"],
                contexts=[c["text"] for c in reranked[:5]],
                ground_truth=ground_truths[i] if ground_truths and i < len(ground_truths) else None,
            )
            samples.append(sample)
            
            self.logger.debug(f"Collected sample for: {question[:50]}...")

        # Get answer model name from rag_service
        if hasattr(rag_service, 'model_map'):
            answer_model = rag_service.model_map.get("mini", "unknown")
        else:
            answer_model = "unknown"

        result = self.evaluate_samples(
            samples=samples,
            include_ground_truth=bool(ground_truths),
        )
        result.answer_model = answer_model
        return result

    def evaluate_from_agent(
        self,
        user_id: str,
        test_questions: List[str],
        ground_truths: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Evaluate Agent with test questions.
        
        Uses ReActAgent for multi-step reasoning and tool calling.
        Extracts contexts from AgentResponse.sources for RAGAS evaluation.
        
        Note: Agent searches across ALL user documents, no document_id needed.
        
        Args:
            user_id: User ID for access control
            test_questions: List of test questions
            ground_truths: Optional list of expected answers
        
        Returns:
            EvaluationResult
        """
        from ..agent.react_agent import ReActAgent
        from .agent_service import AgentService
        import asyncio
        
        # Use AgentService which properly initializes all tools
        agent_service = AgentService()
        samples = []
        answer_model = "unknown"
        
        for i, question in enumerate(test_questions):
            print(f"[{i+1}/{len(test_questions)}] Q: {question[:50]}...")
            
            try:
                # agent_service.chat() is async
                response = asyncio.get_event_loop().run_until_complete(
                    agent_service.chat(
                        query=question,
                        user_id=user_id,
                    )
                )
                
                # Extract contexts from sources
                contexts = []
                for source in response.sources:
                    if isinstance(source, dict) and "text" in source:
                        contexts.append(source["text"])
                    elif isinstance(source, str):
                        contexts.append(source)
                
                answer_model = response.model_used
                
                sample = EvaluationSample(
                    question=question,
                    answer=response.answer,
                    contexts=contexts,
                    ground_truth=ground_truths[i] if ground_truths and i < len(ground_truths) else None,
                )
                samples.append(sample)
                
                print(f"  ✓ Answer: {response.answer[:60]}...")
                print(f"  📚 Sources: {len(contexts)} chunks")
                
            except Exception as e:
                self.logger.error(f"Agent evaluation failed for question: {question[:50]}...: {e}")
                print(f"  ❌ Error: {e}")
                # Add empty sample to maintain alignment with ground_truths
                samples.append(EvaluationSample(
                    question=question,
                    answer=f"Error: {str(e)}",
                    contexts=[],
                    ground_truth=ground_truths[i] if ground_truths and i < len(ground_truths) else None,
                ))
        
        result = self.evaluate_samples(
            samples=samples,
            include_ground_truth=bool(ground_truths),
        )
        result.answer_model = answer_model
        return result

    def save_results(self, result: EvaluationResult, output_path: Path) -> None:
        """Save evaluation results to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "models": {
                "answer_model": result.answer_model,
                "judge_model": result.judge_model,
                "embedding_model": result.embedding_model,
            },
            "metrics": {
                "faithfulness": result.faithfulness,
                "response_relevancy": result.response_relevancy,
                "context_precision": result.context_precision,
                "context_recall": result.context_recall,
                "overall_score": result.overall_score,
            },
            "sample_count": result.sample_count,
            "timestamp": result.timestamp,
            "details": result.details,
        }
        
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.logger.info(f"Saved evaluation results to {output_path}")
