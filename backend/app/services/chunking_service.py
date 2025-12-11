from __future__ import annotations

import json
import re
import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import logging

try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.html import partition_html
except ImportError:  # pragma: no cover
    partition_pdf = None
    partition_html = None

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore

# Add tenacity for smart retries
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
    from google.genai.errors import ClientError
except ImportError:
    retry = lambda *args, **kwargs: lambda f: f
    stop_after_attempt = lambda x: x
    wait_exponential = lambda *args, **kwargs: x
    retry_if_exception_type = lambda x: x
    before_sleep_log = lambda logger, level: lambda f: f
    ClientError = Exception

try:
    from pdf2image import convert_from_path
    from PIL import Image
except ImportError:  # pragma: no cover
    convert_from_path = None  # type: ignore
    Image = None  # type: ignore

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

DEFAULT_CHUNK_SIZE = 800  # tokens (reduced for better embedding model compatibility)
DEFAULT_CHUNK_OVERLAP = 150  # increased overlap for better context preservation

SECTION_HEADING_PATTERN = re.compile(
    r"^(?P<heading>(#+|\d+(\.\d+)*))\s*(?P<title>.+)$"
)

# Patterns for cleaning PDF artifacts
PAGE_NUMBER_PATTERN = re.compile(r'\n\s*\d{1,3}\s*$')  # Trailing page numbers
HEADER_FOOTER_PATTERN = re.compile(r'^[\s\d\-–—]+$', re.MULTILINE)  # Standalone numbers/dashes
MULTIPLE_NEWLINES = re.compile(r'\n{3,}')  # Excessive newlines


@dataclass
class Chunk:
    text: str
    metadata: Dict[str, str]


class StructuredChunker:
    """Chunking pipeline backed by Unstructured with advanced table/text handling."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        summarizer_client: Optional[OpenAI] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        if tiktoken:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        else:  # pragma: no cover
            self.tokenizer = None
        self.openai = summarizer_client
        if self.openai is None and OpenAI is not None:
            try:
                self.openai = OpenAI()
            except Exception:  # pragma: no cover
                self.openai = None

    # --------------------- Parsing ---------------------

    def parse_pdf(self, pdf_path: Path) -> List[Dict]:
        if not partition_pdf:
            raise ImportError("Please install 'unstructured[pdf]' to parse PDFs.")
        
        try:
            elements = partition_pdf(
                filename=str(pdf_path),
                strategy="hi_res",
                infer_table_structure=True,
                model_name="yolox",
            )
            
            # Collect table elements for VLM extraction
            table_elements = [e for e in elements if e.category == "Table"]
            
            # Extract tables using VLM (Gemini) for maximum accuracy
            vlm_tables = {}
            if table_elements and genai:
                try:
                    vlm_tables = self._extract_tables_with_vlm(pdf_path, table_elements)
                    logging.getLogger(__name__).info(
                        f"VLM extracted {len(vlm_tables)} tables from {pdf_path.name}"
                    )
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        f"VLM table extraction failed, falling back to unstructured: {e}"
                    )
            
            cleaned_results = []
            table_count_per_page = {}  # Track table index per page
            
            for element in elements:
                # Skip headers and footers (page numbers, etc.)
                if element.category in ["Footer", "Header"]:
                    continue
                
                item_dict = self._element_to_dict(element)
                
                # For tables, use VLM extraction result
                if element.category == "Table":
                    page_num = getattr(element.metadata, 'page_number', 1) or 1
                    table_idx = table_count_per_page.get(page_num, 0)
                    table_count_per_page[page_num] = table_idx + 1
                    
                    # Check if we have a VLM-extracted table
                    vlm_key = (page_num, table_idx)
                    if vlm_key in vlm_tables:
                        item_dict['text'] = vlm_tables[vlm_key]
                        item_dict['metadata']['extraction_method'] = 'vlm_gemini'
                    elif hasattr(element.metadata, 'text_as_html') and element.metadata.text_as_html:
                        # Fallback to unstructured HTML
                        item_dict['text'] = element.metadata.text_as_html
                        item_dict['metadata']['extraction_method'] = 'unstructured_html'
                
                cleaned_results.append(item_dict)
            
            return cleaned_results
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Failed to parse PDF with unstructured: %s", pdf_path
            )
            raise

    def _extract_tables_with_vlm(self, pdf_path: Path, table_elements: List) -> Dict[int, List[str]]:
        """Extract tables from PDF using VLM (Gemini) for maximum accuracy.
        
        Pipeline:
        1. Get table bounding box from unstructured element
        2. Convert PDF page to image
        3. Crop table region from image
        4. Send to Gemini for markdown conversion
        
        Returns:
            Dict mapping (page_number, table_index) -> markdown string
        """
        if not convert_from_path or not Image or not genai:
            logging.getLogger(__name__).warning(
                "VLM table extraction requires pdf2image, PIL, and google-genai"
            )
            return {}
        
        from ..core.config import get_settings
        settings = get_settings()
        
        if not settings.google_api_key:
            logging.getLogger(__name__).warning("No Google API key for VLM extraction")
            return {}
        
        # Initialize Gemini client
        gemini_client = genai.Client(api_key=settings.google_api_key)
        
        # Convert PDF pages to images (only pages with tables)
        table_pages = set()
        for elem in table_elements:
            page_num = getattr(elem.metadata, 'page_number', 1) or 1
            table_pages.add(page_num)
        
        if not table_pages:
            return {}
        
        # Convert relevant pages to images (300 DPI for good quality)
        try:
            page_images = convert_from_path(
                str(pdf_path),
                dpi=150,  # Balance between quality and speed
                first_page=min(table_pages),
                last_page=max(table_pages),
            )
            # Create mapping: page_number -> image
            page_offset = min(table_pages)
            images_by_page = {
                page_offset + i: img for i, img in enumerate(page_images)
            }
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to convert PDF to images: {e}")
            return {}
        
        tables_extracted = {}
        
        for elem in table_elements:
            page_num = getattr(elem.metadata, 'page_number', 1) or 1
            
            if page_num not in images_by_page:
                continue
            
            page_image = images_by_page[page_num]
            
            # Get bounding box coordinates from unstructured
            coords = getattr(elem.metadata, 'coordinates', None)
            
            if coords and hasattr(coords, 'points'):
                # Crop table region
                cropped = self._crop_table_from_image(page_image, coords.points)
            else:
                # No bbox, use full page (less ideal but still works)
                cropped = page_image
            
            # Send to Gemini for extraction
            markdown = self._extract_table_with_gemini(gemini_client, cropped, settings.gemini_model_flash)
            
            # Rate limiting: Sleep to avoid 429 RESOURCE_EXHAUSTED
            time.sleep(2)
            
            if markdown:
                key = (page_num, len([k for k in tables_extracted if k[0] == page_num]))
                tables_extracted[key] = markdown
        
        return tables_extracted
    
    def _crop_table_from_image(self, page_image: "Image.Image", points: List) -> "Image.Image":
        """Crop table region from page image using bounding box coordinates."""
        if not points or len(points) < 2:
            return page_image
        
        try:
            # Points are typically in PDF coordinates, need to scale to image
            # unstructured returns points as list of (x, y) tuples
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            
            # Get image dimensions
            img_width, img_height = page_image.size
            
            # PDF coordinates are typically 72 DPI, image is 150 DPI
            scale_factor = 150 / 72
            
            left = max(0, int(min(xs) * scale_factor) - 10)
            top = max(0, int(min(ys) * scale_factor) - 10)
            right = min(img_width, int(max(xs) * scale_factor) + 10)
            bottom = min(img_height, int(max(ys) * scale_factor) + 10)
            
            return page_image.crop((left, top, right, bottom))
        except Exception as e:
            logging.getLogger(__name__).debug(f"Failed to crop table: {e}")
            return page_image
    
    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True
    )
    def _extract_table_with_gemini(self, client, image: "Image.Image", model: str) -> Optional[str]:
        """Use Gemini VLM to extract table as markdown."""
        try:
            # Convert PIL image to bytes
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()

            logging.getLogger(__name__).info(f"Extracting table with VLM model: {model}")
            
            prompt = """请精准转录这张图片中的表格为 Markdown 格式。

要求：
1. 保持原始表格结构，包括所有列和行
2. 不要遗漏任何数字、日期或文本
3. 对于空白单元格，保留为空（不要填 N/A 或 -）
4. 对于金额，保留原始格式（如 $1,234,567）
5. 直接输出 Markdown 表格，不要添加任何解释

只返回表格本身，不要有其他内容。"""

            response = client.models.generate_content(
                model=model,
                contents=[
                    genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    prompt,
                ],
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )
            
            # Extract text from response
            if hasattr(response, 'text') and response.text:
                markdown = response.text.strip()
                # Clean up any markdown code block wrappers
                if markdown.startswith('```'):
                    lines = markdown.split('\n')
                    markdown = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                return markdown
            
            return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Gemini table extraction failed: {e}")
            return None

            
    def parse_html(self, html_content: str) -> List[Dict]:
        if partition_html:
            elements = partition_html(text=html_content)
            return [self._element_to_dict(element) for element in elements]
        return self.parse_plain_text(html_content)

    def parse_plain_text(self, text: str) -> List[Dict]:
        # Clean PDF artifacts before parsing
        text = self._clean_pdf_artifacts(text)
        lines = text.splitlines()
        elements = []
        for line in lines:
            if not line.strip():
                continue
                
            category = "NarrativeText"
            if SECTION_HEADING_PATTERN.match(line):
                category = "Title"
                
            elements.append({
                "category": category,
                "text": line,
                "metadata": {},
            })
        return elements

    def _clean_pdf_artifacts(self, text: str) -> str:
        """Remove common PDF extraction artifacts like page numbers, headers/footers."""
        # Remove trailing page numbers (e.g., "\n\n1", "\n  3")
        text = PAGE_NUMBER_PATTERN.sub('', text)
        # Remove lines that are just numbers/dashes (likely headers/footers)
        text = HEADER_FOOTER_PATTERN.sub('', text)
        # Normalize excessive newlines
        text = MULTIPLE_NEWLINES.sub('\n\n', text)
        # Remove isolated single digits at paragraph boundaries
        text = re.sub(r'\n\n\s*(\d{1,2})\s*\n\n', '\n\n', text)
        return text.strip()

    # --------------------- Section building ---------------------

    def build_sections(self, elements: List[Dict]) -> List[Dict]:
        sections: List[Dict] = []
        heading_stack: List[str] = ["Introduction"]

        current = {
            "path": heading_stack.copy(),
            "text": [],
            "tables": [],
            "page_number": None,
        }

        for element in elements:
            category = element.get("category")
            text = element.get("text", "")
            metadata = element.get("metadata", {}) or {}

            if category == "Title":
                level = max(1, self._infer_title_level(text))
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(text.strip())
                if current["text"] or current["tables"]:
                    sections.append(current)
                current = {
                    "path": heading_stack.copy(),
                    "text": [],
                    "tables": [],
                    "page_number": metadata.get("page_number"),
                }
            elif category == "Table":
                current["tables"].append({"text": text, "metadata": metadata})
            else:
                current["text"].append(text)

        if current["text"] or current["tables"]:
            sections.append(current)

        return sections

    # --------------------- Chunking ---------------------

    def chunk_sections(self, sections: List[Dict]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for section in sections:
            section_path = " -> ".join(section["path"])
            page_number = section.get("page_number")

            text_content = "\n\n".join(section["text"]).strip()
            if text_content:
                text_chunks = self._split_text(text_content)
                for idx, chunk_text in enumerate(text_chunks):
                    chunks.append(
                        Chunk(
                            text=f"Section: {section_path}\n\n{chunk_text}",
                            metadata={
                                "section_path": section_path,
                                "chunk_index": str(idx),
                                "token_count": str(self._count_tokens(chunk_text)),
                                "element_type": "text",
                                "page_number": str(page_number) if page_number is not None else "",
                            },
                        )
                    )

            for table in section["tables"]:
                markdown = self._table_to_markdown(table)
                summary = self._summarize_table(markdown)
                chunks.append(
                    Chunk(
                        text=f"Section: {section_path}\n\nSummary: {summary}\n\nTable:\n{markdown}",
                        metadata={
                            "section_path": section_path,
                            "element_type": "table",
                            "has_summary": str(bool(summary)),
                            "page_number": str(table["metadata"].get("page_number") or page_number or ""),
                        },
                    )
                )

        return chunks

    def serialize_chunks(self, chunks: List[Chunk], destination: Path) -> None:
        payload = [
            {"text": chunk.text, "metadata": chunk.metadata} for chunk in chunks
        ]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --------------------- Helpers ---------------------

    def _split_text(self, text: str) -> List[str]:
        if not text:
            return []
        
        # First, try semantic splitting by paragraphs
        paragraphs = self._split_by_semantic_boundaries(text)
        
        if not self.tokenizer:  # pragma: no cover
            return self._merge_small_chunks(paragraphs, self.chunk_size, self.chunk_overlap, char_mode=True)

        return self._merge_small_chunks(paragraphs, self.chunk_size, self.chunk_overlap, char_mode=False)

    def _split_by_semantic_boundaries(self, text: str) -> List[str]:
        """Split text at semantic boundaries (paragraphs, code blocks, formulas)."""
        # Preserve code blocks as single units
        code_block_pattern = re.compile(r'(```[\s\S]*?```|`[^`]+`)', re.MULTILINE)
        
        # Split by double newlines (paragraphs) while preserving code blocks
        parts = []
        last_end = 0
        
        for match in code_block_pattern.finditer(text):
            # Add text before code block
            before = text[last_end:match.start()]
            if before.strip():
                parts.extend([p.strip() for p in before.split('\n\n') if p.strip()])
            # Add code block as single unit
            parts.append(match.group(0))
            last_end = match.end()
        
        # Add remaining text
        remaining = text[last_end:]
        if remaining.strip():
            parts.extend([p.strip() for p in remaining.split('\n\n') if p.strip()])
        
        return parts if parts else [text]

    def _merge_small_chunks(
        self, 
        paragraphs: List[str], 
        max_size: int, 
        overlap: int,
        char_mode: bool = False
    ) -> List[str]:
        """Merge small paragraphs into chunks while respecting size limits."""
        if not paragraphs:
            return []
        
        def get_size(text: str) -> int:
            if char_mode or not self.tokenizer:
                return len(text)
            return len(self.tokenizer.encode(text))
        
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_size = 0
        
        for para in paragraphs:
            para_size = get_size(para)
            
            # If single paragraph exceeds max size, split it further
            if para_size > max_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph by tokens
                sub_chunks = self._split_large_paragraph(para, max_size, overlap, char_mode)
                chunks.extend(sub_chunks)
                continue
            
            # Check if adding this paragraph exceeds limit
            separator_size = get_size('\n\n') if current_chunk else 0
            if current_size + separator_size + para_size > max_size:
                # Save current chunk
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                
                # Start new chunk with overlap from previous
                if overlap > 0 and current_chunk:
                    # Include last paragraph(s) as overlap context
                    overlap_paras = self._get_overlap_context(current_chunk, overlap, char_mode)
                    current_chunk = overlap_paras + [para]
                    current_size = get_size('\n\n'.join(current_chunk))
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                current_chunk.append(para)
                current_size += separator_size + para_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def _split_large_paragraph(
        self, 
        text: str, 
        max_size: int, 
        overlap: int,
        char_mode: bool
    ) -> List[str]:
        """Split a large paragraph that exceeds max_size."""
        if char_mode or not self.tokenizer:
            chunks = []
            start = 0
            while start < len(text):
                end = min(len(text), start + max_size)
                chunks.append(text[start:end])
                if end == len(text):
                    break
                start = max(0, end - overlap)
            return chunks
        
        token_ids = self.tokenizer.encode(text)
        chunks = []
        step = max(1, max_size - overlap)
        for start in range(0, len(token_ids), step):
            end = min(len(token_ids), start + max_size)
            chunk_ids = token_ids[start:end]
            chunks.append(self.tokenizer.decode(chunk_ids))
            if end == len(token_ids):
                break
        return chunks

    def _get_overlap_context(
        self, 
        paragraphs: List[str], 
        target_overlap: int,
        char_mode: bool
    ) -> List[str]:
        """Get paragraphs from the end to use as overlap context."""
        def get_size(text: str) -> int:
            if char_mode or not self.tokenizer:
                return len(text)
            return len(self.tokenizer.encode(text))
        
        overlap_paras = []
        total_size = 0
        
        for para in reversed(paragraphs):
            para_size = get_size(para)
            if total_size + para_size > target_overlap:
                break
            overlap_paras.insert(0, para)
            total_size += para_size
        
        return overlap_paras

    def _count_tokens(self, text: str) -> int:
        if not self.tokenizer:  # pragma: no cover
            return len(text)
        return len(self.tokenizer.encode(text))

    def _element_to_dict(self, element) -> Dict:
        try:
            element_dict = element.to_dict()
        except AttributeError:  # pragma: no cover
            element_dict = {
                "category": getattr(element, "category", "NarrativeText"),
                "text": str(element),
                "metadata": {},
            }
        metadata = element_dict.get("metadata") or {}
        return {
            "category": element_dict.get("type", element_dict.get("category")),
            "text": element_dict.get("text", ""),
            "metadata": metadata,
        }

    def _table_to_markdown(self, table_element: Dict) -> str:
        metadata = table_element.get("metadata") or {}
        
        # CRITICAL: If already extracted accurately (VLM or pdfplumber), use that directly!
        # Don't re-parse HTML which would overwrite the accurate result
        extraction_method = metadata.get("extraction_method", "")
        if extraction_method in ("vlm_gemini", "pdfplumber"):
            return table_element.get("text", "")
        
        html = metadata.get("text_as_html") or metadata.get("table_as_html") or ""
        if not html or pd is None or BeautifulSoup is None:
            return table_element.get("text", "")
        soup = BeautifulSoup(html, "html.parser")
        table_tag = soup.find("table")
        if not table_tag:
            return table_element.get("text", "")
        try:
            from io import StringIO
            df_list = pd.read_html(StringIO(str(table_tag)))
        except ValueError:
            return table_element.get("text", "")
        if not df_list:
            return table_element.get("text", "")
        
        df = df_list[0]
        # Replace NaN values with empty strings to avoid 'nan' in output
        df = df.fillna('')
        # Also clean up any 'nan' strings that might have been parsed as text
        df = df.replace('nan', '')
        return df.to_markdown(index=False)

    def _summarize_table(self, markdown: str) -> str:
        if not markdown.strip():
            return ""
        if not self.openai:
            return "Table summary not available."
        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this table in 2-3 sentences:\n\n{markdown}",
                    }
                ],
                max_tokens=120,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception:  # pragma: no cover
            return "Table summary not available."

    def _infer_title_level(self, title: str) -> int:
        match = SECTION_HEADING_PATTERN.match(title.strip())
        if match:
            heading = match.group("heading")
            if heading.startswith("#"):
                return len(heading)
            return heading.count(".") + 1
        return 1

