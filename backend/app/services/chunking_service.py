from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

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
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

DEFAULT_CHUNK_SIZE = 1_000  # tokens
DEFAULT_CHUNK_OVERLAP = 100

SECTION_HEADING_PATTERN = re.compile(
    r"^(?P<heading>(#+|\d+(\.\d+)*))\s*(?P<title>.+)$"
)


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
        if partition_pdf:
            elements = partition_pdf(filename=str(pdf_path), strategy="hi_res")
            return [self._element_to_dict(element) for element in elements]
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            text = "\n".join([page.extract_text() for page in reader.pages])
            return self.parse_plain_text(text)
        except ImportError:
            raise ImportError("Please install 'unstructured' or 'pypdf' to parse PDFs.")

            
    def parse_html(self, html_content: str) -> List[Dict]:
        if partition_html:
            elements = partition_html(text=html_content)
            return [self._element_to_dict(element) for element in elements]
        return self.parse_plain_text(html_content)

    def parse_plain_text(self, text: str) -> List[Dict]:
        lines = text.splitlines()
        return [
            {
                "category": "NarrativeText",
                "text": line,
                "metadata": {},
            }
            for line in lines
            if line.strip()
        ]

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
        if not self.tokenizer:  # pragma: no cover
            if len(text) <= self.chunk_size:
                return [text]
            chunks: List[str] = []
            start = 0
            overlap = self.chunk_overlap
            while start < len(text):
                end = min(len(text), start + self.chunk_size)
                chunks.append(text[start:end])
                if end == len(text):
                    break
                start = max(0, end - overlap)
            return chunks

        token_ids = self.tokenizer.encode(text)
        if len(token_ids) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        for start in range(0, len(token_ids), step):
            end = min(len(token_ids), start + self.chunk_size)
            chunk_ids = token_ids[start:end]
            chunks.append(self.tokenizer.decode(chunk_ids))
            if end == len(token_ids):
                break
        return chunks

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
        html = metadata.get("text_as_html") or metadata.get("table_as_html") or ""
        if not html or pd is None or BeautifulSoup is None:
            return table_element.get("text", "")
        soup = BeautifulSoup(html, "html.parser")
        table_tag = soup.find("table")
        if not table_tag:
            return table_element.get("text", "")
        try:
            df_list = pd.read_html(str(table_tag))
        except ValueError:
            return table_element.get("text", "")
        if not df_list:
            return table_element.get("text", "")
        return df_list[0].to_markdown(index=False)

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

