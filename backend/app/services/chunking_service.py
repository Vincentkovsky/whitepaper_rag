from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.html import partition_html
except ImportError:  # pragma: no cover
    partition_pdf = None
    partition_html = None

DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_OVERLAP = 100

SECTION_HEADING_PATTERN = re.compile(
    r"^(?P<heading>(#+|\d+(\.\d+)*))\s*(?P<title>.+)$"
)


@dataclass
class Chunk:
    text: str
    metadata: Dict[str, str]


class SemanticChunker:
    """Chunking pipeline backed by Unstructured for element extraction."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse_pdf(self, pdf_path: Path) -> List[Dict]:
        if partition_pdf:
            elements = partition_pdf(filename=str(pdf_path), strategy="hi_res")
            return [self._element_to_dict(element) for element in elements]
        data = pdf_path.read_bytes()
        text = data.decode(errors="ignore")
        return self.parse_plain_text(text)

    def parse_html(self, html_content: str) -> List[Dict]:
        if partition_html:
            elements = partition_html(text=html_content)
            return [self._element_to_dict(element) for element in elements]
        return self.parse_plain_text(html_content)

    def build_sections(self, elements: List[Dict]) -> List[Dict[str, Sequence[str]]]:
        sections: List[Dict[str, Sequence[str]]] = []
        current = {"title": "Introduction", "lines": []}

        for element in elements:
            category = element["category"]
            text = element.get("text", "")

            if category == "Title":
                if current["lines"]:
                    sections.append(current)
                current = {"title": text.strip(), "lines": []}
            else:
                current["lines"].append(text)

        if current["lines"]:
            sections.append(current)
        return sections

    def parse_plain_text(self, text: str) -> List[Dict]:
        lines = text.splitlines()
        return [{"category": "NarrativeText", "text": line} for line in lines if line.strip()]

    def chunk_sections(self, sections: List[Dict[str, Sequence[str]]]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for index, section in enumerate(sections):
            section_text = "\n".join(section["lines"]).strip()
            if not section_text:
                continue

            section_chunks = self._split_text(section_text)
            for i, chunk_text in enumerate(section_chunks):
                chunks.append(
                    Chunk(
                        text=f"Section: {section['title']}\n\n{chunk_text}",
                        metadata={
                            "section_path": section["title"],
                            "chunk_index": str(i),
                            "token_count": str(len(chunk_text)),
                            "element_type": "text",
                        },
                    )
                )
        return chunks

    def serialize_chunks(self, chunks: List[Chunk], destination: Path) -> None:
        payload = [
            {"text": chunk.text, "metadata": chunk.metadata} for chunk in chunks
        ]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _split_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = max(0, end - self.chunk_overlap)
        return chunks

