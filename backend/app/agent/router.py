"""
Intent Router for classifying user queries.

This module implements the IntentRouter that classifies user intent
to determine the appropriate processing path (direct answer, document QA,
web search, or complex reasoning).
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

try:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None  # type: ignore

from .types import IntentClassification, IntentType
from ..core.config import get_settings
from .prompts import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_USER_TEMPLATE,
)


class IntentRouter:
    """
    Router that classifies user intent to determine processing path.
    
    Uses a combination of pattern matching for common greetings/small-talk
    and LLM-based classification for ambiguous cases.
    
    Fallback mechanism: If DIRECT_ANSWER confidence < 0.8,
    automatically escalate to DOCUMENT_QA to avoid false negatives.
    """
    
    # Common greeting patterns in English and Chinese
    # Note: Include both ASCII and full-width Chinese punctuation
    GREETING_PATTERNS: List[str] = [
        # English greetings
        r"^(hi|hello|hey|howdy|greetings)[\s!.,?！。，？]*$",
        r"^good\s+(morning|afternoon|evening|night)[\s!.,?！。，？]*$",
        r"^how\s+are\s+you[\s!.,?！。，？]*$",
        r"^what'?s\s+up[\s!.,?！。，？]*$",
        r"^how'?s\s+it\s+going[\s!.,?！。，？]*$",
        r"^nice\s+to\s+meet\s+you[\s!.,?！。，？]*$",
        # Chinese greetings
        r"^你好[\s!.,?！。，？]*$",
        r"^您好[\s!.,?！。，？]*$",
        r"^嗨[\s!.,?！。，？]*$",
        r"^哈喽[\s!.,?！。，？]*$",
        r"^早上好[\s!.,?！。，？]*$",
        r"^下午好[\s!.,?！。，？]*$",
        r"^晚上好[\s!.,?！。，？]*$",
        r"^晚安[\s!.,?！。，？]*$",
        r"^你好吗[\s!.,?！。，？]*$",
        r"^最近怎么样[\s!.,?！。，？]*$",
        r"^在吗[\s!.,?！。，？]*$",
    ]
    
    # Small-talk patterns (non-greeting but still direct answer)
    SMALL_TALK_PATTERNS: List[str] = [
        # English
        r"^(thanks?|thank\s+you|thx)[\s!.,?！。，？]*$",
        r"^(bye|goodbye|see\s+you|later)[\s!.,?！。，？]*$",
        r"^(yes|no|ok|okay|sure|alright)[\s!.,?！。，？]*$",
        r"^(please|sorry|excuse\s+me)[\s!.,?！。，？]*$",
        r"^who\s+are\s+you[\s!.,?！。，？]*$",
        r"^what\s+can\s+you\s+do[\s!.,?！。，？]*$",
        r"^help[\s!.,?！。，？]*$",
        # Chinese
        r"^谢谢[\s!.,?！。，？]*$",
        r"^感谢[\s!.,?！。，？]*$",
        r"^再见[\s!.,?！。，？]*$",
        r"^拜拜[\s!.,?！。，？]*$",
        r"^好的?[\s!.,?！。，？]*$",
        r"^是的?[\s!.,?！。，？]*$",
        r"^不是?[\s!.,?！。，？]*$",
        r"^你是谁[\s!.,?！。，？]*$",
        r"^你能做什么[\s!.,?！。，？]*$",
        r"^帮助[\s!.,?！。，？]*$",
    ]
    
    # Confidence threshold for fallback mechanism
    CONFIDENCE_THRESHOLD = 0.8
    
    def __init__(
        self,
        openai_client: Optional[OpenAI] = None,
        confidence_threshold: float = 0.8,
    ):
        """
        Initialize the IntentRouter.
        
        Args:
            openai_client: Optional OpenAI client for LLM-based classification
            confidence_threshold: Threshold below which DIRECT_ANSWER escalates to DOCUMENT_QA
        """
        self.settings = get_settings()
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger("app.agent.router")
        
        # Initialize LLM client based on provider
        self.provider = (self.settings.llm_provider or "openai").lower()
        
        if self.provider == "openai":
            self.openai = openai_client or (OpenAI() if self.settings.openai_api_key else None)
            self._gemini_client = None
        else:
            self.openai = None
            self._gemini_client = None
            if genai and self.settings.google_api_key:
                self._gemini_client = genai.Client(api_key=self.settings.google_api_key)
        
        # Compile regex patterns for efficiency
        self._greeting_patterns = [re.compile(p, re.IGNORECASE) for p in self.GREETING_PATTERNS]
        self._small_talk_patterns = [re.compile(p, re.IGNORECASE) for p in self.SMALL_TALK_PATTERNS]
    
    def classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentClassification:
        """
        Classify user intent to determine processing path.
        
        Args:
            query: The user's input query
            context: Optional context information (e.g., conversation history)
        
        Returns:
            IntentClassification with intent type, confidence, and reasoning
        
        Note:
            Fallback mechanism: If DIRECT_ANSWER confidence < 0.8,
            automatically escalate to DOCUMENT_QA to avoid false negatives.
        """
        start_time = time.perf_counter()
        query_stripped = query.strip()
        
        # Step 1: Check for pattern-matched greetings/small-talk (high confidence)
        pattern_result = self._check_patterns(query_stripped)
        if pattern_result is not None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                "Intent classified via pattern matching",
                extra={
                    "intent": pattern_result.intent.value,
                    "confidence": pattern_result.confidence,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return pattern_result
        
        # Step 2: Use LLM for ambiguous cases
        llm_result = self._classify_with_llm(query_stripped, context)
        
        # Step 3: Apply fallback mechanism
        if llm_result.intent == IntentType.DIRECT_ANSWER and llm_result.confidence < self.confidence_threshold:
            self.logger.info(
                "Escalating DIRECT_ANSWER to DOCUMENT_QA due to low confidence",
                extra={
                    "original_confidence": llm_result.confidence,
                    "threshold": self.confidence_threshold,
                },
            )
            llm_result = IntentClassification(
                intent=IntentType.DOCUMENT_QA,
                confidence=llm_result.confidence,
                reasoning=f"Escalated from DIRECT_ANSWER (confidence {llm_result.confidence:.2f} < {self.confidence_threshold}): {llm_result.reasoning}",
            )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.logger.info(
            "Intent classified via LLM",
            extra={
                "intent": llm_result.intent.value,
                "confidence": llm_result.confidence,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return llm_result
    
    def _check_patterns(self, query: str) -> Optional[IntentClassification]:
        """
        Check if query matches known greeting or small-talk patterns.
        
        Args:
            query: The user's input query (stripped)
        
        Returns:
            IntentClassification if pattern matched, None otherwise
        """
        # Check greeting patterns
        for pattern in self._greeting_patterns:
            if pattern.match(query):
                return IntentClassification(
                    intent=IntentType.DIRECT_ANSWER,
                    confidence=0.95,
                    reasoning=f"Matched greeting pattern: {query}",
                )
        
        # Check small-talk patterns
        for pattern in self._small_talk_patterns:
            if pattern.match(query):
                return IntentClassification(
                    intent=IntentType.DIRECT_ANSWER,
                    confidence=0.95,
                    reasoning=f"Matched small-talk pattern: {query}",
                )
        
        return None

    
    def _classify_with_llm(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentClassification:
        """
        Use LLM to classify intent for ambiguous queries.
        
        Args:
            query: The user's input query
            context: Optional context information
        
        Returns:
            IntentClassification from LLM analysis
        """
        # Build the classification prompt
        system_prompt = INTENT_CLASSIFICATION_SYSTEM_PROMPT

        user_prompt = INTENT_CLASSIFICATION_USER_TEMPLATE.format(query=query)
        
        if context:
            user_prompt += f"\n\nContext: {context}"
        
        try:
            if self.provider == "gemini" and self._gemini_client:
                return self._classify_with_gemini(system_prompt, user_prompt)
            elif self.openai:
                return self._classify_with_openai(system_prompt, user_prompt)
            else:
                # No LLM available, default to DOCUMENT_QA
                self.logger.warning("No LLM client available, defaulting to DOCUMENT_QA")
                return IntentClassification(
                    intent=IntentType.DOCUMENT_QA,
                    confidence=0.5,
                    reasoning="No LLM available for classification, defaulting to document search",
                )
        except Exception as e:
            self.logger.error(f"LLM classification failed: {e}", exc_info=True)
            # Default to DOCUMENT_QA on error
            return IntentClassification(
                intent=IntentType.DOCUMENT_QA,
                confidence=0.5,
                reasoning=f"Classification error, defaulting to document search: {str(e)}",
            )
    
    def _classify_with_openai(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> IntentClassification:
        """Classify using OpenAI API."""
        import json
        
        response = self.openai.chat.completions.create(
            model=self.settings.openai_model_mini,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        return self._parse_llm_response(content)
    
    def _classify_with_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> IntentClassification:
        """Classify using Gemini API."""
        import json
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        response = self._gemini_client.models.generate_content(
            model=self.settings.gemini_model_flash,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200,
            ),
        )
        
        # Extract text from response
        content = ""
        if hasattr(response, "text") and response.text:
            content = response.text
        elif response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content:
                if hasattr(candidate.content, "parts") and candidate.content.parts:
                    if len(candidate.content.parts) > 0:
                        content = candidate.content.parts[0].text
        
        return self._parse_llm_response(content)
    
    def _parse_llm_response(self, content: str) -> IntentClassification:
        """Parse LLM response into IntentClassification."""
        import json
        
        try:
            # Try to extract JSON from the response
            # Handle cases where LLM wraps JSON in markdown code blocks
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code block
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            data = json.loads(content)
            
            intent_str = data.get("intent", "DOCUMENT_QA").upper()
            intent_map = {
                "DIRECT_ANSWER": IntentType.DIRECT_ANSWER,
                "DOCUMENT_QA": IntentType.DOCUMENT_QA,
                "WEB_SEARCH": IntentType.WEB_SEARCH,
                "COMPLEX_REASONING": IntentType.COMPLEX_REASONING,
                "COMPLEX": IntentType.COMPLEX_REASONING,
            }
            
            intent = intent_map.get(intent_str, IntentType.DOCUMENT_QA)
            confidence = float(data.get("confidence", 0.7))
            reasoning = data.get("reasoning", "LLM classification")
            
            return IntentClassification(
                intent=intent,
                confidence=min(max(confidence, 0.0), 1.0),  # Clamp to [0, 1]
                reasoning=reasoning,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"Failed to parse LLM response: {e}, content: {content[:200]}")
            return IntentClassification(
                intent=IntentType.DOCUMENT_QA,
                confidence=0.5,
                reasoning=f"Failed to parse LLM response, defaulting to document search",
            )
    
    def is_small_talk(self, query: str) -> bool:
        """
        Quick check if a query is small-talk/greeting.
        
        This is a convenience method for cases where you just need
        a boolean answer without full classification.
        
        Args:
            query: The user's input query
        
        Returns:
            True if the query is detected as small-talk/greeting
        """
        query_stripped = query.strip()
        
        # Check greeting patterns
        for pattern in self._greeting_patterns:
            if pattern.match(query_stripped):
                return True
        
        # Check small-talk patterns
        for pattern in self._small_talk_patterns:
            if pattern.match(query_stripped):
                return True
        
        return False
