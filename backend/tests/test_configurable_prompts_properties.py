import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for configurable prompts.

**Feature: generic-agentic-rag, Property 11: Configurable Prompts**
"""

from unittest.mock import MagicMock, patch
from hypothesis import given, strategies as st, settings, assume

from app.agent.prompts import (
    PromptTemplate,
    PromptTemplateRegistry,
    DEFAULT_QA_TEMPLATE,
    CHINESE_QA_TEMPLATE,
    get_prompt_registry,
)
from app.services.rag_service import RAGService


# Custom strategies for generating valid prompt templates
printable_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
                            "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
                            "\x7f{}"  # Exclude braces to avoid format string issues
    ),
    min_size=1,
    max_size=200
)

valid_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != "")


@st.composite
def prompt_template_strategy(draw):
    """Generate valid PromptTemplate instances with proper format placeholders."""
    name = draw(valid_name_strategy)
    description = draw(printable_text)
    
    # Generate system prompt without format placeholders
    system_prompt = draw(printable_text)
    
    # User prompt must contain {context} and {question} placeholders
    prefix = draw(printable_text)
    suffix = draw(printable_text)
    user_prompt_template = f"{prefix}{{context}}{suffix}{{question}}"
    
    return PromptTemplate(
        name=name,
        description=description,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template
    )


@settings(max_examples=100)
@given(template=prompt_template_strategy())
def test_prompt_template_format_user_prompt(template: PromptTemplate):
    """
    **Feature: generic-agentic-rag, Property 11: Configurable Prompts**
    
    For any valid PromptTemplate, formatting the user prompt with context and question
    SHALL produce a string containing both the context and question values.
    
    **Validates: Requirements 4.3**
    """
    context = "Test context content"
    question = "Test question?"
    
    formatted = template.format_user_prompt(context=context, question=question)
    
    # The formatted prompt should contain both context and question
    assert context in formatted, f"Context not found in formatted prompt: {formatted}"
    assert question in formatted, f"Question not found in formatted prompt: {formatted}"


@settings(max_examples=100)
@given(template=prompt_template_strategy())
def test_prompt_template_format_full_prompt(template: PromptTemplate):
    """
    **Feature: generic-agentic-rag, Property 11: Configurable Prompts**
    
    For any valid PromptTemplate, formatting the full prompt SHALL include
    both the system prompt and the formatted user prompt.
    
    **Validates: Requirements 4.3**
    """
    context = "Test context content"
    question = "Test question?"
    
    full_prompt = template.format_full_prompt(context=context, question=question)
    
    # The full prompt should contain the system prompt
    assert template.system_prompt in full_prompt, \
        f"System prompt not found in full prompt: {full_prompt}"
    # The full prompt should contain context and question
    assert context in full_prompt, f"Context not found in full prompt: {full_prompt}"
    assert question in full_prompt, f"Question not found in full prompt: {full_prompt}"


@settings(max_examples=100)
@given(template=prompt_template_strategy())
def test_registry_round_trip(template: PromptTemplate):
    """
    **Feature: generic-agentic-rag, Property 11: Configurable Prompts**
    
    For any valid PromptTemplate, registering it and retrieving by name
    SHALL return an equivalent template.
    
    **Validates: Requirements 4.3**
    """
    registry = PromptTemplateRegistry()
    
    # Register the template
    registry.register(template)
    
    # Retrieve by name
    retrieved = registry.get(template.name)
    
    assert retrieved is not None, f"Template '{template.name}' not found after registration"
    assert retrieved.name == template.name
    assert retrieved.description == template.description
    assert retrieved.system_prompt == template.system_prompt
    assert retrieved.user_prompt_template == template.user_prompt_template


@settings(max_examples=100)
@given(template=prompt_template_strategy())
def test_rag_service_uses_injected_template(template: PromptTemplate):
    """
    **Feature: generic-agentic-rag, Property 11: Configurable Prompts**
    
    For any prompt template configuration, the RAGService SHALL use the configured
    template text in LLM calls rather than hardcoded defaults.
    
    **Validates: Requirements 4.3**
    """
    # Create mock clients
    mock_chroma = MagicMock()
    mock_openai = MagicMock()
    
    # Create RAGService with injected template
    with patch('backend.app.services.rag_service.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(
            chroma_server_host=None,
            chroma_persist_directory=None,
            llm_provider="openai",
            embedding_provider="openai",
            openai_model_mini="gpt-4o-mini",
            openai_model_turbo="gpt-4o",
        )
        
        service = RAGService(
            chroma_client=mock_chroma,
            openai_client=mock_openai,
            prompt_template=template
        )
    
    # Verify the service uses the injected template
    assert service.prompt_template == template
    assert service.prompt_template.system_prompt == template.system_prompt
    assert service.prompt_template.user_prompt_template == template.user_prompt_template
    
    # Verify it's not using the default template (unless they happen to be equal)
    if template.system_prompt != DEFAULT_QA_TEMPLATE.system_prompt:
        assert service.prompt_template.system_prompt != DEFAULT_QA_TEMPLATE.system_prompt


@settings(max_examples=50)
@given(template=prompt_template_strategy())
def test_generate_answer_uses_configured_template(template: PromptTemplate):
    """
    **Feature: generic-agentic-rag, Property 11: Configurable Prompts**
    
    For any prompt template configuration, the _generate_answer method SHALL
    use the configured template's system and user prompts in the LLM call.
    
    **Validates: Requirements 4.3**
    """
    # Create mock clients
    mock_chroma = MagicMock()
    mock_openai = MagicMock()
    
    # Mock the OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test answer"
    mock_openai.chat.completions.create.return_value = mock_response
    
    # Create RAGService with injected template
    with patch('backend.app.services.rag_service.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(
            chroma_server_host=None,
            chroma_persist_directory=None,
            llm_provider="openai",
            embedding_provider="openai",
            openai_model_mini="gpt-4o-mini",
            openai_model_turbo="gpt-4o",
        )
        
        service = RAGService(
            chroma_client=mock_chroma,
            openai_client=mock_openai,
            prompt_template=template
        )
    
    # Call _generate_answer
    context = "Test context"
    question = "Test question?"
    result = service._generate_answer(
        question=question,
        context=context,
        model="mini",
        temperature=None
    )
    
    # Verify the OpenAI API was called with the configured template
    call_args = mock_openai.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    
    # Check system message uses configured template
    system_message = messages[0]
    assert system_message["role"] == "system"
    assert system_message["content"] == template.system_prompt, \
        f"Expected system prompt '{template.system_prompt}', got '{system_message['content']}'"
    
    # Check user message uses configured template format
    user_message = messages[1]
    assert user_message["role"] == "user"
    expected_user_prompt = template.format_user_prompt(context=context, question=question)
    assert user_message["content"] == expected_user_prompt, \
        f"Expected user prompt '{expected_user_prompt}', got '{user_message['content']}'"


def test_default_template_is_domain_agnostic():
    """
    Verify that the default template does not contain blockchain-specific terminology.
    
    **Validates: Requirements 4.2**
    """
    blockchain_terms = [
        "比特币", "bitcoin", "区块链", "blockchain", "白皮书", "whitepaper",
        "加密货币", "cryptocurrency", "挖矿", "mining"
    ]
    
    # Check system prompt
    for term in blockchain_terms:
        assert term.lower() not in DEFAULT_QA_TEMPLATE.system_prompt.lower(), \
            f"Default template system prompt contains blockchain term: {term}"
    
    # Check user prompt template
    for term in blockchain_terms:
        assert term.lower() not in DEFAULT_QA_TEMPLATE.user_prompt_template.lower(), \
            f"Default template user prompt contains blockchain term: {term}"


def test_registry_get_or_default():
    """
    Verify that get_or_default returns the default template when name is None or not found.
    """
    registry = PromptTemplateRegistry()
    
    # None should return default
    result = registry.get_or_default(None)
    assert result == DEFAULT_QA_TEMPLATE
    
    # Non-existent name should return default
    result = registry.get_or_default("non_existent_template")
    assert result == DEFAULT_QA_TEMPLATE
    
    # Existing name should return that template
    result = registry.get_or_default("chinese_qa")
    assert result == CHINESE_QA_TEMPLATE
