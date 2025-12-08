"""
ReAct Agent implementation for the Generic Agentic RAG System.

This module implements the ReAct (Reasoning + Acting) pattern for multi-step
reasoning with tool calling capabilities.

Requirements:
- 2.2: WHEN the Agent determines a tool is needed, THE Agentic_RAG_System SHALL
       invoke the tool with appropriate parameters and incorporate the result into reasoning.
- 3.1: WHEN a user submits a complex question, THE Agentic_RAG_System SHALL
       decompose it into sub-questions and process them sequentially.
- 3.2: WHILE executing a multi-step plan, THE Agentic_RAG_System SHALL
       maintain conversation state across steps.
- 3.3: THE Agentic_RAG_System SHALL limit the maximum number of reasoning steps
       to 10 to prevent infinite loops.
- 3.4: WHEN all sub-questions are answered, THE Agentic_RAG_System SHALL
       synthesize a final comprehensive answer.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import OpenAI

try:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None  # type: ignore

from .types import (
    AgentResponse,
    AgentStreamEvent,
    IntentType,
    ThoughtStep,
)
from .router import IntentRouter
from .tools.registry import ToolRegistry, ToolNotFoundError
from ..core.config import get_settings


from .prompts import REACT_AGENT_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


# Default maximum steps to prevent infinite loops (Requirement 3.3)
DEFAULT_MAX_STEPS = 10


class ReActAgent:
    """
    ReAct Agent implementing reasoning + acting pattern.
    
    The agent follows a loop of:
    1. Think - Analyze the current state and decide what to do
    2. Act - Execute a tool if needed
    3. Observe - Process the tool result
    4. Repeat until answer is ready or max steps reached
    
    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(document_search_tool)
        >>> router = IntentRouter()
        >>> agent = ReActAgent(registry, router, max_steps=10)
        >>> response = await agent.run(
        ...     query="What is the main topic of the document?",
        ...     document_id="doc123",
        ...     user_id="user456",
        ... )
        >>> print(response.answer)
    """
    
    # System prompt is now centralized in prompts.py
    SYSTEM_PROMPT = REACT_AGENT_SYSTEM_PROMPT


    def __init__(
        self,
        tool_registry: ToolRegistry,
        router: Optional[IntentRouter] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        openai_client: Optional[OpenAI] = None,
    ) -> None:
        """
        Initialize the ReAct Agent.
        
        Args:
            tool_registry: Registry of available tools
            router: Intent router for query classification (optional)
            max_steps: Maximum reasoning steps (default: 10, Requirement 3.3)
            openai_client: Optional OpenAI client for LLM calls
        """
        self.tools = tool_registry
        self.router = router
        self.max_steps = max_steps
        self.settings = get_settings()
        
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
    
    async def run(
        self,
        query: str,
        user_id: str,
        stream: bool = False,
    ) -> AgentResponse:
        """
        Execute the agent reasoning loop.
        
        Searches across all documents belonging to the user.
        
        Args:
            query: The user's question
            user_id: ID of the user making the request
            stream: Whether streaming is enabled (affects internal behavior)
            
        Returns:
            AgentResponse with answer, sources, and intermediate steps
        """
        start_time = time.perf_counter()
        
        # Check intent if router is available
        # Only bypass tool usage for very simple greetings (pattern-matched with high confidence)
        if self.router:
            intent = self.router.classify(query)
            if intent.intent == IntentType.DIRECT_ANSWER and intent.confidence >= 0.9:
                # Handle simple greetings directly without tools (pattern-matched only)
                answer = self._generate_direct_answer(query)
                return AgentResponse(
                    answer=answer,
                    sources=[],
                    intermediate_steps=[],
                    model_used=self._get_model_name(),
                    total_latency_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Initialize state for multi-step reasoning (Requirement 3.2)
        intermediate_steps: List[ThoughtStep] = []
        observations: List[str] = []
        sources: List[Dict[str, Any]] = []
        
        # Build tools description for the prompt
        tools_description = self._build_tools_description()
        
        # Build initial conversation history
        conversation_history = self._build_initial_history(
            query=query,
            tools_description=tools_description,
            user_id=user_id,
        )
        
        # ReAct loop with step limit (Requirement 3.3)
        step_count = 0
        final_answer: Optional[str] = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.debug(f"ReAct step {step_count}/{self.max_steps}")
            
            # Get next action from LLM
            llm_response = self._call_llm(conversation_history)
            
            # Parse the response
            parsed = self._parse_llm_response(llm_response)
            
            thought = parsed.get("thought", "")
            action = parsed.get("action")
            action_input = parsed.get("action_input")
            final_answer = parsed.get("final_answer")
            
            # Create thought step
            step = ThoughtStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=None,
            )
            
            # Check if we have a final answer
            if final_answer:
                intermediate_steps.append(step)
                break
            
            # Execute tool if action is specified
            if action:
                observation = self._execute_tool(
                    action=action,
                    action_input=action_input or {},
                    user_id=user_id,
                )
                step.observation = observation
                observations.append(observation)
                
                # Extract sources from tool results
                if action == "document_search" and isinstance(observation, str):
                    try:
                        results = json.loads(observation)
                        if isinstance(results, list):
                            for r in results:
                                if isinstance(r, dict):
                                    sources.append(r)
                    except json.JSONDecodeError:
                        pass
                
                # Add observation to conversation history
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response,
                })
                conversation_history.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })
            else:
                # No action and no final answer - ask LLM to continue
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response,
                })
                conversation_history.append({
                    "role": "user",
                    "content": "Please continue your reasoning or provide a final answer.",
                })
            
            intermediate_steps.append(step)
        
        # If we hit the step limit without a final answer, synthesize one (Requirement 3.4)
        if final_answer is None:
            logger.warning(f"Step limit ({self.max_steps}) reached, synthesizing final answer")
            final_answer = self._synthesize_final_answer(
                query=query,
                observations=observations,
                intermediate_steps=intermediate_steps,
            )
        
        total_latency_ms = (time.perf_counter() - start_time) * 1000
        
        return AgentResponse(
            answer=final_answer,
            sources=sources,
            intermediate_steps=intermediate_steps,
            model_used=self._get_model_name(),
            total_latency_ms=total_latency_ms,
        )
    
    async def stream(
        self,
        query: str,
        user_id: str,
    ) -> AsyncIterator[AgentStreamEvent]:
        """
        Stream agent execution events.
        
        Searches across all documents belonging to the user.
        
        Args:
            query: The user's question
            user_id: ID of the user making the request
            
        Yields:
            AgentStreamEvent for each step of execution
        """
        start_time = time.perf_counter()
        
        # Check intent if router is available
        # Only bypass tool usage for very simple greetings (pattern-matched with high confidence)
        if self.router:
            intent = self.router.classify(query)
            if intent.intent == IntentType.DIRECT_ANSWER and intent.confidence >= 0.9:
                yield AgentStreamEvent(
                    event_type="thinking",
                    content="This is a simple greeting, responding directly.",
                )
                answer = self._generate_direct_answer(query)
                yield AgentStreamEvent(
                    event_type="answer",
                    content=answer,
                    metadata={"latency_ms": (time.perf_counter() - start_time) * 1000},
                )
                return
        
        # Initialize state
        observations: List[str] = []
        sources: List[Dict[str, Any]] = []  # Collect sources from tool results
        
        # Build tools description
        tools_description = self._build_tools_description()
        
        # Build initial conversation history
        conversation_history = self._build_initial_history(
            query=query,
            tools_description=tools_description,
            user_id=user_id,
        )
        
        # ReAct loop
        step_count = 0
        final_answer: Optional[str] = None
        
        while step_count < self.max_steps:
            step_count += 1
            
            # Emit thinking event
            yield AgentStreamEvent(
                event_type="thinking",
                content=f"Step {step_count}: Analyzing...",
                metadata={"step": step_count},
            )
            
            # Get next action from LLM
            llm_response = self._call_llm(conversation_history)
            parsed = self._parse_llm_response(llm_response)
            
            thought = parsed.get("thought", "")
            action = parsed.get("action")
            action_input = parsed.get("action_input")
            final_answer = parsed.get("final_answer")
            
            # Emit thought
            if thought:
                yield AgentStreamEvent(
                    event_type="thinking",
                    content=thought,
                    metadata={"step": step_count},
                )
            
            if final_answer:
                yield AgentStreamEvent(
                    event_type="answer",
                    content=final_answer,
                    metadata={
                        "latency_ms": (time.perf_counter() - start_time) * 1000,
                        "sources": sources,
                    },
                )
                return
            
            # Execute tool if action specified
            if action:
                yield AgentStreamEvent(
                    event_type="tool_call",
                    content=f"Calling {action}",
                    metadata={"tool": action, "input": action_input},
                )
                
                observation = self._execute_tool(
                    action=action,
                    action_input=action_input or {},
                    user_id=user_id,
                )
                observations.append(observation)
                
                yield AgentStreamEvent(
                    event_type="tool_result",
                    content=observation[:500] + "..." if len(observation) > 500 else observation,
                    metadata={"tool": action},
                )
                
                # Extract sources from tool results
                if action in ("web_search", "search_web"):
                    try:
                        results = json.loads(observation) if isinstance(observation, str) else observation
                        if isinstance(results, list):
                            # Use 1-based index matching the citation format [[citation:N]]
                            start_idx = len(sources) + 1  # Continue numbering from previous sources
                            for idx, r in enumerate(results):
                                if isinstance(r, dict):
                                    sources.append({
                                        "documentId": str(start_idx + idx),  # Simple numeric ID: "1", "2", etc.
                                        "chunkId": "",
                                        "title": r.get("title", ""),
                                        "url": r.get("url", ""),
                                        "textSnippet": r.get("content", "")[:200],
                                        "sourceType": "web",
                                    })
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif action == "document_search":
                    try:
                        results = json.loads(observation) if isinstance(observation, str) else observation
                        if isinstance(results, list):
                            start_idx = len(sources) + 1
                            for idx, r in enumerate(results):
                                if isinstance(r, dict):
                                    sources.append({
                                        "documentId": str(start_idx + idx),  # Simple numeric ID
                                        "chunkId": "",
                                        # document_search returns 'section' and 'document_id', but not always 'document_name'
                                        "title": r.get("document_name", r.get("section", r.get("document_id", "Untitled Document"))),
                                        # document_search returns 'text', not 'content'
                                        "textSnippet": r.get("text", r.get("content", ""))[:200],
                                        "sourceType": "pdf",
                                        # document_search returns 'page'
                                        "page": r.get("page", r.get("page_number")),
                                    })
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Update conversation history
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response,
                })
                conversation_history.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })
            else:
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response,
                })
                conversation_history.append({
                    "role": "user",
                    "content": "Please continue your reasoning or provide a final answer.",
                })
        
        # Step limit reached - synthesize answer
        yield AgentStreamEvent(
            event_type="thinking",
            content="Reached step limit, synthesizing final answer...",
        )
        
        final_answer = self._synthesize_final_answer(
            query=query,
            observations=observations,
            intermediate_steps=[],
        )
        
        yield AgentStreamEvent(
            event_type="answer",
            content=final_answer,
            metadata={
                "latency_ms": (time.perf_counter() - start_time) * 1000,
                "sources": sources,
            },
        )

    
    def _build_tools_description(self) -> str:
        """Build a description of available tools for the system prompt."""
        tool_schemas = self.tools.list_tools()
        if not tool_schemas:
            return "No tools available."
        
        descriptions = []
        for schema in tool_schemas:
            params_str = json.dumps(schema.parameters, indent=2) if schema.parameters else "{}"
            descriptions.append(
                f"- {schema.name}: {schema.description}\n"
                f"  Parameters: {params_str}\n"
                f"  Required: {schema.required}"
            )
        
        return "\n".join(descriptions)
    
    def _build_initial_history(
        self,
        query: str,
        tools_description: str,
        user_id: str,
    ) -> List[Dict[str, str]]:
        """Build the initial conversation history for the agent."""
        # Inject current_date for Time Anchor (prevents temporal hallucinations)
        # Use date only (not time) to maximize Prefix Caching effectiveness
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.SYSTEM_PROMPT.format(
            tools_description=tools_description,
            current_date=current_date,
        )
        
        # Add context for the agent
        context = f"""
Context:
- User ID: {user_id}
- You will search across all documents belonging to this user
- When using document_search, always include user_id in the action_input

User Question: {query}

Think step by step and decide what to do."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with the given messages."""
        try:
            if self.provider == "gemini" and self._gemini_client:
                return self._call_gemini(messages)
            elif self.openai:
                return self._call_openai(messages)
            else:
                raise RuntimeError("No LLM client available")
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            # Return a fallback response that will trigger final answer synthesis
            return json.dumps({
                "thought": f"LLM call failed: {str(e)}",
                "action": None,
                "action_input": None,
                "final_answer": "I apologize, but I encountered an error while processing your request. Please try again.",
            })
    
    def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        """Call OpenAI API."""
        response = self.openai.chat.completions.create(
            model=self.settings.openai_model_mini,
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    
    def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        """Call Gemini API."""
        # Convert messages to Gemini format
        # Gemini doesn't have a system role, so we prepend it to the first user message
        system_content = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)
        
        # Build the prompt
        if system_content and user_messages:
            first_msg = user_messages[0]
            first_msg["content"] = f"{system_content}\n\n{first_msg['content']}"
        
        # Convert to Gemini contents format
        contents = []
        for msg in user_messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        response = self._gemini_client.models.generate_content(
            model=self.settings.gemini_model_flash,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1000,
            ),
        )
        
        # Extract text from response
        if hasattr(response, "text") and response.text:
            return response.text
        elif response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content:
                if hasattr(candidate.content, "parts") and candidate.content.parts:
                    if len(candidate.content.parts) > 0:
                        return candidate.content.parts[0].text
        return ""
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured format."""
        try:
            # Try to extract JSON from the response
            response = response.strip()
            
            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response = "\n".join(lines)
            
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from within the response
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # If we can't parse JSON, treat the whole response as a thought
            logger.warning(f"Failed to parse LLM response as JSON: {response[:200]}")
            return {
                "thought": response,
                "action": None,
                "action_input": None,
                "final_answer": None,
            }
    
    def _execute_tool(
        self,
        action: str,
        action_input: Dict[str, Any],
        user_id: str,
    ) -> str:
        """
        Execute a tool and return the result as a string.
        
        Requirement 2.4: IF a tool invocation fails, THEN THE Agentic_RAG_System
        SHALL log the error and continue reasoning with available information.
        """
        try:
            # Inject user_id if not provided
            if "user_id" not in action_input:
                action_input["user_id"] = user_id
            
            result = self.tools.invoke(action, **action_input)
            
            # Convert result to string
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
                
        except ToolNotFoundError as e:
            logger.warning(f"Tool not found: {action}")
            return f"Error: Tool '{action}' not found. Available tools: {[t.name for t in self.tools.list_tools()]}"
        except Exception as e:
            # Log error but continue reasoning (Requirement 2.4)
            logger.error(f"Tool execution failed: {action} - {e}", exc_info=True)
            return f"Error executing tool '{action}': {str(e)}"
    
    def _generate_direct_answer(self, query: str) -> str:
        """Generate a direct answer for small-talk/greetings."""
        # Simple pattern-based responses for common greetings
        query_lower = query.lower().strip()
        
        greetings = {
            "hello": "Hello! How can I help you today?",
            "hi": "Hi there! What can I do for you?",
            "hey": "Hey! How can I assist you?",
            "你好": "你好！有什么我可以帮助你的吗？",
            "您好": "您好！请问有什么需要帮助的？",
            "嗨": "嗨！有什么可以帮你的？",
            "how are you": "I'm doing well, thank you for asking! How can I help you?",
            "你好吗": "我很好，谢谢关心！有什么可以帮助你的吗？",
        }
        
        for pattern, response in greetings.items():
            if pattern in query_lower:
                return response
        
        # Default response
        return "Hello! I'm here to help you with questions about your documents. What would you like to know?"
    
    def _synthesize_final_answer(
        self,
        query: str,
        observations: List[str],
        intermediate_steps: List[ThoughtStep],
    ) -> str:
        """
        Synthesize a final answer from all observations.
        
        Requirement 3.4: WHEN all sub-questions are answered, THE Agentic_RAG_System
        SHALL synthesize a final comprehensive answer.
        """
        if not observations:
            return "I was unable to find relevant information to answer your question. Please try rephrasing or provide more context."
        
        # Build a synthesis prompt
        observations_text = "\n\n".join([
            f"Observation {i+1}:\n{obs}"
            for i, obs in enumerate(observations)
        ])
        
        synthesis_prompt = f"""Based on the following observations, provide a comprehensive answer to the user's question.

User Question: {query}

{observations_text}

Please synthesize these observations into a clear, coherent answer. If the observations don't fully answer the question, acknowledge what information is missing."""

        messages = [
            {"role": "system", "content": "You are a helpful assistant that synthesizes information into clear answers."},
            {"role": "user", "content": synthesis_prompt},
        ]
        
        try:
            response = self._call_llm(messages)
            # The synthesis response should be plain text, not JSON
            # Try to extract just the answer if it's in JSON format
            try:
                parsed = json.loads(response)
                if "final_answer" in parsed and parsed["final_answer"]:
                    return parsed["final_answer"]
                elif "answer" in parsed and parsed["answer"]:
                    return parsed["answer"]
            except json.JSONDecodeError:
                pass
            
            # Ensure we return a non-empty response
            if response and response.strip():
                return response
            
            # Fallback to observations summary
            return f"Based on my search, here's what I found:\n\n{observations_text}"
        except Exception as e:
            logger.error(f"Failed to synthesize final answer: {e}")
            # Return a basic summary of observations
            return f"Based on my search, here's what I found:\n\n{observations_text}"
    
    def _get_model_name(self) -> str:
        """Get the name of the model being used."""
        if self.provider == "gemini":
            return self.settings.gemini_model_flash
        return self.settings.openai_model_mini
