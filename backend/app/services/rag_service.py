"""
Phase 4 — RAG (Retrieval-Augmented Generation) Service

Lightweight keyword-based knowledge retrieval for citizen questions.
No vector database required for POC — uses TF-IDF-style keyword scoring.

Knowledge base: backend/knowledge/**/*.md

Usage:
    rag = RAGService()
    chunks = rag.retrieve("Why do you need my father's name?", service_id="income_certificate")
    answer = LLMService().answer_rag(question, chunks, language="en")

Rules:
    - LLM explains using ONLY these chunks (no hallucination)
    - Knowledge files are the authoritative source for government requirements
    - YAML rules engine is the authoritative source for eligibility/fees/validation
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)

# Path to knowledge base directory (checks backend/knowledge and root knowledge)
_backend_knowledge = Path(__file__).resolve().parent.parent.parent / "knowledge"
_root_knowledge = Path(__file__).resolve().parent.parent.parent.parent / "knowledge"
KNOWLEDGE_DIR = _backend_knowledge if _backend_knowledge.exists() else _root_knowledge


class KnowledgeChunk:
    """A section of text from the knowledge base."""

    def __init__(self, text: str, source: str, heading: str = ""):
        self.text = text
        self.source = source        # filename path
        self.heading = heading      # section heading
        self.score = 0.0           # relevance score (set during retrieval)

    def __repr__(self):
        return f"<KnowledgeChunk source={self.source} heading={self.heading!r} score={self.score:.2f}>"


class RAGService:
    """
    Keyword-based RAG retrieval service.

    Loads all markdown files from backend/knowledge/ on first call.
    Scores chunks by keyword overlap with the question.
    Boosts chunks from the relevant service directory.
    """

    _loaded: bool = False
    _chunks: List[KnowledgeChunk] = []

    def __init__(self):
        if not RAGService._loaded:
            RAGService._chunks = self._load_all_chunks()
            RAGService._loaded = True
            logger.info(f"RAGService loaded {len(RAGService._chunks)} knowledge chunks")

    # ─────────────────────────────────────────────
    # Load
    # ─────────────────────────────────────────────

    def _load_all_chunks(self) -> List[KnowledgeChunk]:
        """Load and parse all markdown files from knowledge directory."""
        chunks: List[KnowledgeChunk] = []

        if not KNOWLEDGE_DIR.exists():
            logger.warning(f"Knowledge directory not found: {KNOWLEDGE_DIR}")
            return chunks

        for md_file in KNOWLEDGE_DIR.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                file_chunks = self._parse_markdown(text, str(md_file))
                chunks.extend(file_chunks)
            except Exception as e:
                logger.warning(f"Failed to load knowledge file {md_file}: {e}")

        return chunks

    def _parse_markdown(self, text: str, source: str) -> List[KnowledgeChunk]:
        """Split markdown into chunks by heading sections."""
        chunks = []
        # Split by H2 headings
        sections = re.split(r"\n##\s+", text)

        for section in sections:
            if not section.strip():
                continue
            # First line is the heading (or intro)
            lines = section.strip().split("\n", 1)
            heading = lines[0].strip().lstrip("#").strip()
            body = lines[1].strip() if len(lines) > 1 else heading

            # Skip very short sections
            if len(body) < 30:
                continue

            chunks.append(KnowledgeChunk(text=body, source=source, heading=heading))

            # Also create sub-chunks for H3 sections within
            sub_sections = re.split(r"\n###\s+", body)
            for sub in sub_sections[1:]:
                sub_lines = sub.strip().split("\n", 1)
                sub_heading = sub_lines[0].strip()
                sub_body = sub_lines[1].strip() if len(sub_lines) > 1 else sub_heading
                if len(sub_body) > 30:
                    chunks.append(KnowledgeChunk(
                        text=f"{heading}: {sub_body}",
                        source=source,
                        heading=f"{heading} — {sub_heading}"
                    ))

        return chunks

    # ─────────────────────────────────────────────
    # Retrieve
    # ─────────────────────────────────────────────

    def retrieve(
        self,
        question: str,
        service_id: Optional[str] = None,
        max_chunks: int = 5
    ) -> List[str]:
        """
        Retrieve the most relevant knowledge chunks for a question.

        Args:
            question: Citizen's question text.
            service_id: Service being applied for (e.g., 'income_certificate').
                        Chunks from this service get a relevance boost.
            max_chunks: Maximum number of chunks to return.

        Returns:
            List of text strings (most relevant first).
        """
        if not RAGService._chunks:
            logger.warning("RAGService has no chunks loaded. Check backend/knowledge/ directory.")
            return []

        question_tokens = self._tokenize(question.lower())

        scored: List[Tuple[float, KnowledgeChunk]] = []

        for chunk in RAGService._chunks:
            score = self._score_chunk(chunk, question_tokens, service_id)
            if score > 0:
                scored.append((score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored[:max_chunks]:
            chunk.score = score
            header = f"[{chunk.heading}]" if chunk.heading else ""
            results.append(f"{header}\n{chunk.text}".strip())

        logger.debug(f"RAG retrieved {len(results)} chunks for: '{question[:60]}'")
        return results

    def _score_chunk(
        self,
        chunk: KnowledgeChunk,
        question_tokens: List[str],
        service_id: Optional[str]
    ) -> float:
        """Score a chunk's relevance to the question."""
        chunk_text = (chunk.text + " " + chunk.heading).lower()
        chunk_tokens = self._tokenize(chunk_text)

        if not question_tokens or not chunk_tokens:
            return 0.0

        # Token overlap score
        overlap = len(set(question_tokens) & set(chunk_tokens))
        if overlap == 0:
            return 0.0

        # Normalize by question length (recall-focused)
        score = overlap / len(set(question_tokens))

        # Service relevance boost: 50% boost for matching service directory
        if service_id and service_id.replace("_", "/") in chunk.source.replace("\\", "/").lower():
            score *= 1.5

        # Boost for "general" knowledge (applies to all)
        if "general" in chunk.source.lower():
            score *= 1.1

        return score

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase words, filter stopwords."""
        STOPWORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "of", "in", "for", "on",
            "with", "at", "by", "from", "to", "and", "or", "but", "not", "you",
            "i", "my", "your", "we", "they", "it", "this", "that", "what", "why",
            "how", "when", "where", "which", "who", "me", "us",
        }
        tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
        return [t for t in tokens if t not in STOPWORDS]
