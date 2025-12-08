"""
Web Search Tool for the Agent.

Provides web search functionality using Tavily API with fallback to SerpApi.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..types import Tool, ToolSchema
from ...core.config import get_settings


logger = logging.getLogger("app.agent.tools.web_search")

TAVILY_API_URL = "https://api.tavily.com/search"
SERPAPI_URL = "https://serpapi.com/search"


class WebSearchError(Exception):
    """Raised when web search fails."""
    pass


def _search_tavily(
    query: str,
    api_key: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """Search using Tavily API.
    
    Args:
        query: The search query
        api_key: Tavily API key
        max_results: Maximum number of results to return
        
    Returns:
        List of search results with title, url, and content
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                })
            
            return results
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Tavily API error: {e.response.status_code}")
        raise WebSearchError(f"Tavily API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        raise WebSearchError(f"Tavily search failed: {e}")


def _search_serpapi(
    query: str,
    api_key: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """Search using SerpApi as fallback.
    
    Args:
        query: The search query
        api_key: SerpApi API key
        max_results: Maximum number of results to return
        
    Returns:
        List of search results with title, url, and content
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                SERPAPI_URL,
                params={
                    "api_key": api_key,
                    "q": query,
                    "num": max_results,
                    "engine": "google",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "content": item.get("snippet", ""),
                    "score": 1.0 - (len(results) * 0.1),  # Approximate score based on position
                })
            
            return results[:max_results]
            
    except httpx.HTTPStatusError as e:
        logger.error(f"SerpApi error: {e.response.status_code}")
        raise WebSearchError(f"SerpApi error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"SerpApi search failed: {e}")
        raise WebSearchError(f"SerpApi search failed: {e}")


def create_web_search_tool(
    tavily_api_key: Optional[str] = None,
    serpapi_key: Optional[str] = None,
) -> Tool:
    """Create a web_search tool instance.
    
    Args:
        tavily_api_key: Tavily API key (optional, will use settings if not provided)
        serpapi_key: SerpApi key for fallback (optional, will use settings if not provided)
        
    Returns:
        A Tool instance configured for web search
    """
    settings = get_settings()
    _tavily_key = tavily_api_key or getattr(settings, "tavily_api_key", None)
    _serpapi_key = serpapi_key or getattr(settings, "serpapi_key", None)
    
    def web_search(
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search the web for information.
        
        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 5)
            
        Returns:
            List of search results with title, url, and content
        """
        logger.debug(f"Web search: query='{query[:50]}...', max_results={max_results}")
        
        # Try Tavily first
        if _tavily_key:
            try:
                results = _search_tavily(query, _tavily_key, max_results)
                logger.info(f"Tavily search returned {len(results)} results")
                return results
            except WebSearchError as e:
                logger.warning(f"Tavily failed, trying fallback: {e}")
        
        # Fallback to SerpApi
        if _serpapi_key:
            try:
                results = _search_serpapi(query, _serpapi_key, max_results)
                logger.info(f"SerpApi search returned {len(results)} results")
                return results
            except WebSearchError as e:
                logger.error(f"SerpApi fallback also failed: {e}")
                raise
        
        # No API keys configured
        error_msg = "No web search API keys configured (TAVILY_API_KEY or SERPAPI_KEY)"
        logger.error(error_msg)
        raise WebSearchError(error_msg)
    
    schema = ToolSchema(
        name="web_search",
        description=(
            "Search the web for real-time information not present in the documents. "
            "Use this tool when you need current information, facts from the internet, "
            "or when the document doesn't contain the needed information. "
            "Fuzzy Data Processing Principle: If precise historical data (e.g., 'exactly one year ago') "
            "is not available after 2-3 search attempts, DO NOT keep searching. "
            "Instead, use the closest available data point (e.g., 'early 2023' or 'last reported figure') "
            "and explicitly state this approximation in your final answer."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find information on the web",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
            },
        },
        required=["query"],
    )
    
    return Tool(schema=schema, handler=web_search)
