import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Unit tests for the unified tokenizer utility.

Tests cover:
- English tokenization
- Chinese tokenization (via jieba)
- Mixed language tokenization
- Language detection
- Edge cases (empty input, whitespace-only)
"""

import pytest
from app.agent.retrieval.tokenizer import (
    tokenize,
    is_chinese_text,
    _is_cjk_char,
    _calculate_cjk_ratio,
)


class TestLanguageDetection:
    """Tests for language detection functionality."""

    def test_is_cjk_char_with_chinese(self):
        """Chinese characters should be detected as CJK."""
        assert _is_cjk_char('你') is True
        assert _is_cjk_char('好') is True
        assert _is_cjk_char('世') is True

    def test_is_cjk_char_with_english(self):
        """English characters should not be detected as CJK."""
        assert _is_cjk_char('a') is False
        assert _is_cjk_char('Z') is False
        assert _is_cjk_char('1') is False

    def test_calculate_cjk_ratio_pure_chinese(self):
        """Pure Chinese text should have ratio close to 1.0."""
        ratio = _calculate_cjk_ratio('你好世界')
        assert ratio == 1.0

    def test_calculate_cjk_ratio_pure_english(self):
        """Pure English text should have ratio of 0.0."""
        ratio = _calculate_cjk_ratio('Hello world')
        assert ratio == 0.0

    def test_calculate_cjk_ratio_empty(self):
        """Empty text should have ratio of 0.0."""
        assert _calculate_cjk_ratio('') == 0.0
        assert _calculate_cjk_ratio('   ') == 0.0


    def test_is_chinese_text_with_chinese(self):
        """Chinese text should be detected as Chinese."""
        assert is_chinese_text('你好世界') is True
        assert is_chinese_text('这是一个测试') is True

    def test_is_chinese_text_with_english(self):
        """English text should not be detected as Chinese."""
        assert is_chinese_text('Hello world') is False
        assert is_chinese_text('This is a test') is False

    def test_is_chinese_text_with_mixed(self):
        """Mixed text detection depends on CJK ratio threshold (0.3)."""
        # '你好Hello' has 2 CJK chars out of 7 total = 0.286 < 0.3 threshold
        assert is_chinese_text('你好Hello') is False
        # '你好你好Hello' has 4 CJK chars out of 9 total = 0.44 > 0.3 threshold
        assert is_chinese_text('你好你好Hello') is True
        # More English than threshold
        assert is_chinese_text('Hello world 你') is False


class TestEnglishTokenization:
    """Tests for English text tokenization."""

    def test_simple_english(self):
        """Simple English sentence should be tokenized into words."""
        tokens = tokenize('Hello world')
        assert tokens == ['hello', 'world']

    def test_english_with_punctuation(self):
        """Punctuation should be removed during tokenization."""
        tokens = tokenize('Hello, world! How are you?')
        assert tokens == ['hello', 'world', 'how', 'are', 'you']

    def test_english_case_insensitive(self):
        """Tokenization should be case-insensitive."""
        tokens = tokenize('HELLO World')
        assert tokens == ['hello', 'world']


class TestChineseTokenization:
    """Tests for Chinese text tokenization."""

    def test_simple_chinese(self):
        """Simple Chinese text should be segmented into words."""
        tokens = tokenize('你好世界')
        assert '你好' in tokens
        assert '世界' in tokens

    def test_chinese_with_punctuation(self):
        """Chinese punctuation should be handled correctly."""
        tokens = tokenize('你好，世界！')
        assert '你好' in tokens
        assert '世界' in tokens
        # Punctuation should not be in tokens
        assert '，' not in tokens
        assert '！' not in tokens


class TestMixedTokenization:
    """Tests for mixed Chinese/English text tokenization."""

    def test_mixed_text(self):
        """Mixed text should tokenize both languages correctly."""
        tokens = tokenize('Hello 你好 world')
        assert 'hello' in tokens
        assert '你好' in tokens
        assert 'world' in tokens


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_string(self):
        """Empty string should return empty list."""
        assert tokenize('') == []

    def test_whitespace_only(self):
        """Whitespace-only string should return empty list."""
        assert tokenize('   ') == []
        assert tokenize('\t\n') == []

    def test_single_word(self):
        """Single word should return list with one token."""
        assert tokenize('hello') == ['hello']
        assert '你好' in tokenize('你好')

    def test_numbers(self):
        """Numbers should be tokenized."""
        tokens = tokenize('test123 456')
        assert 'test123' in tokens
        assert '456' in tokens
