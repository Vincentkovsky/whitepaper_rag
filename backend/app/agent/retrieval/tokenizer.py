"""
Unified tokenizer utility for BM25 indexing and querying.

This module provides a single source of truth for text tokenization,
supporting both Chinese (via jieba) and English text.

CRITICAL: This tokenizer MUST be used for both indexing and querying
to ensure consistent tokenization across the BM25 pipeline.
"""

import re
import string
from typing import List

import jieba


# CJK Unicode ranges (characters only, not punctuation)
CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
    (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
]

# Chinese punctuation characters to filter out
CHINESE_PUNCTUATION = set('，。！？、；：""''（）【】《》〈〉「」『』…—～·')

# Threshold for determining if text is primarily Chinese
CJK_RATIO_THRESHOLD = 0.3


def _is_cjk_char(char: str) -> bool:
    """Check if a character is a CJK character."""
    code_point = ord(char)
    return any(start <= code_point <= end for start, end in CJK_RANGES)


def _calculate_cjk_ratio(text: str) -> float:
    """Calculate the ratio of CJK characters in the text."""
    if not text:
        return 0.0
    
    # Count only actual characters (not whitespace or punctuation)
    chars = [c for c in text if c.strip() and c not in string.punctuation]
    if not chars:
        return 0.0
    
    cjk_count = sum(1 for c in chars if _is_cjk_char(c))
    return cjk_count / len(chars)


def is_chinese_text(text: str) -> bool:
    """
    Determine if text is primarily Chinese based on CJK character ratio.
    
    Args:
        text: Input text to analyze
        
    Returns:
        True if CJK character ratio exceeds threshold (0.3)
    """
    return _calculate_cjk_ratio(text) >= CJK_RATIO_THRESHOLD


def _is_punctuation(token: str) -> bool:
    """Check if a token is purely punctuation (English or Chinese)."""
    return all(
        c in string.punctuation or c in CHINESE_PUNCTUATION or c.isspace()
        for c in token
    )


def _tokenize_chinese(text: str) -> List[str]:
    """
    Tokenize Chinese text using jieba segmentation.
    
    Args:
        text: Chinese text to tokenize
        
    Returns:
        List of tokens (words/characters)
    """
    # Use jieba's cut function for word segmentation
    tokens = jieba.cut(text, cut_all=False)
    # Filter out empty tokens, whitespace, and punctuation
    return [
        t.strip().lower() for t in tokens 
        if t.strip() and not _is_punctuation(t)
    ]


def _tokenize_english(text: str) -> List[str]:
    """
    Tokenize English text using whitespace and punctuation splitting.
    
    Args:
        text: English text to tokenize
        
    Returns:
        List of tokens (words)
    """
    # Convert to lowercase
    text = text.lower()
    # Split on whitespace and punctuation
    # This regex splits on any non-alphanumeric character
    tokens = re.split(r'[^\w]+', text)
    # Filter out empty tokens
    return [t for t in tokens if t]


def tokenize(text: str) -> List[str]:
    """
    Tokenize text using appropriate method based on language detection.
    
    This is the SINGLE SOURCE OF TRUTH for tokenization in the BM25 pipeline.
    It MUST be used for both indexing and querying to ensure consistency.
    
    Args:
        text: Input text to tokenize (Chinese or English)
        
    Returns:
        List of tokens
        
    Examples:
        >>> tokenize("Hello world")
        ['hello', 'world']
        >>> tokenize("你好世界")  # Chinese: "Hello world"
        ['你好', '世界']
        >>> tokenize("Hello 你好 world")  # Mixed
        ['hello', '你好', 'world']
    """
    if not text or not text.strip():
        return []
    
    # Detect language based on CJK ratio
    if is_chinese_text(text):
        return _tokenize_chinese(text)
    else:
        # For mixed text or English, use a hybrid approach
        # Split into segments, tokenize each appropriately
        return _tokenize_mixed(text)


def _tokenize_mixed(text: str) -> List[str]:
    """
    Tokenize mixed Chinese/English text.
    
    Handles text that contains both CJK and non-CJK characters
    by processing each segment with the appropriate tokenizer.
    
    Args:
        text: Mixed language text
        
    Returns:
        List of tokens from both languages
    """
    tokens = []
    current_segment = []
    current_is_cjk = None
    
    for char in text:
        char_is_cjk = _is_cjk_char(char)
        
        # Handle whitespace and punctuation
        if char.isspace() or char in string.punctuation or char in '，。！？、；：""''（）【】':
            # Flush current segment
            if current_segment:
                segment_text = ''.join(current_segment)
                if current_is_cjk:
                    tokens.extend(_tokenize_chinese(segment_text))
                else:
                    tokens.extend(_tokenize_english(segment_text))
                current_segment = []
                current_is_cjk = None
            continue
        
        # Start new segment or continue current
        if current_is_cjk is None:
            current_is_cjk = char_is_cjk
            current_segment.append(char)
        elif char_is_cjk == current_is_cjk:
            current_segment.append(char)
        else:
            # Language switch - flush current segment
            segment_text = ''.join(current_segment)
            if current_is_cjk:
                tokens.extend(_tokenize_chinese(segment_text))
            else:
                tokens.extend(_tokenize_english(segment_text))
            current_segment = [char]
            current_is_cjk = char_is_cjk
    
    # Flush remaining segment
    if current_segment:
        segment_text = ''.join(current_segment)
        if current_is_cjk:
            tokens.extend(_tokenize_chinese(segment_text))
        else:
            tokens.extend(_tokenize_english(segment_text))
    
    return tokens
