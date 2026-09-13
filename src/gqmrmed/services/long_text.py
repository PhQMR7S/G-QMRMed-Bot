"""Phase 8 long-text processing for infographic generation."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s+|(?:\d+[.)]|[-*])\s+)(.+?)\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?؟])\s+|\n{2,}")
_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_MEDICAL_TERMS = frozenset({
    "diagnosis", "treatment", "symptom", "symptoms", "cause", "causes",
    "mechanism", "pathophysiology", "laboratory", "lab", "drug", "dose",
    "differential", "complication", "management", "تشخيص", "علاج", "أعراض",
    "اعراض", "سبب", "أسباب", "اسباب", "آلية", "الية", "مرض", "دواء",
    "جرعة", "مضاعفات", "تحاليل",
})


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    heading: str | None
    topic: str
    priority: float


@dataclass(frozen=True, slots=True)
class LongTextPlan:
    mode: str
    chunks: tuple[TextChunk, ...]
    topics: tuple[str, ...]
    page_count: int
    visual_identity: str
    usage_units: int = 1


class LongTextEngine:
    """Transform arbitrary long text into a deterministic generation plan."""

    def __init__(
        self,
        *,
        chunk_target_chars: int = 900,
        max_single_page_chars: int = 3_200,
        max_page_chars: int = 3_800,
        dedup_similarity: float = 0.82,
    ) -> None:
        if chunk_target_chars < 200:
            raise ValueError("chunk_target_too_small")
        if max_single_page_chars < chunk_target_chars:
            raise ValueError("single_page_limit_too_small")
        if max_page_chars < chunk_target_chars:
            raise ValueError("page_limit_too_small")
        if not 0 < dedup_similarity <= 1:
            raise ValueError("invalid_dedup_similarity")
        self.chunk_target_chars = chunk_target_chars
        self.max_single_page_chars = max_single_page_chars
        self.max_page_chars = max_page_chars
        self.dedup_similarity = dedup_similarity

    def build_plan(
        self,
        text: str,
        *,
        visual_identity: str = "gqmrmed-medical",
    ) -> LongTextPlan:
        normalized = self._normalize(text)
        if not normalized:
            raise ValueError("long_text_required")
        chunks = self._deduplicate(self._semantic_chunks(self._parse_sections(normalized)))
        topics = self._extract_topics(chunks)
        ranked = self._prioritize(chunks, topics)
        total_chars = sum(len(chunk.text) for chunk in ranked)
        page_count = max(
            1,
            (total_chars + self.max_page_chars - 1) // self.max_page_chars,
        )
        mode = (
            "single"
            if total_chars <= self.max_single_page_chars and len(ranked) <= 6
            else "multi_page"
        )
        return LongTextPlan(
            mode=mode,
            chunks=tuple(ranked),
            topics=tuple(topics),
            page_count=page_count if mode == "multi_page" else 1,
            visual_identity=visual_identity.strip() or "gqmrmed-medical",
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"[ \t]+", " ", normalized).strip()

    @staticmethod
    def _parse_sections(text: str) -> list[tuple[str | None, str]]:
        sections: list[tuple[str | None, str]] = []
        heading: str | None = None
        buffer: list[str] = []
        for line in text.splitlines():
            match = _HEADING_RE.match(line)
            if match:
                if buffer:
                    sections.append((heading, " ".join(buffer).strip()))
                    buffer = []
                heading = match.group(1).strip()
            elif line.strip():
                buffer.append(line.strip())
        if buffer:
            sections.append((heading, " ".join(buffer).strip()))
        return sections or [(None, text)]

    def _semantic_chunks(
        self,
        sections: list[tuple[str | None, str]],
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        index = 0
        for heading, body in sections:
            sentences = [
                part.strip()
                for part in _SENTENCE_RE.split(body)
                if part.strip()
            ]
            current: list[str] = []
            size = 0
            for sentence in sentences:
                if current and size + len(sentence) + 1 > self.chunk_target_chars:
                    chunks.append(self._make_chunk(index, heading, " ".join(current)))
                    index += 1
                    current, size = [], 0
                current.append(sentence)
                size += len(sentence) + 1
            if current:
                chunks.append(self._make_chunk(index, heading, " ".join(current)))
                index += 1
        return chunks

    @staticmethod
    def _make_chunk(index: int, heading: str | None, text: str) -> TextChunk:
        topic = heading or LongTextEngine._topic_from_text(text)
        return TextChunk(index, text, heading, topic, 0.0)

    @staticmethod
    def _topic_from_text(text: str) -> str:
        words = _TOKEN_RE.findall(text.lower())
        return Counter(words).most_common(1)[0][0] if words else "general"

    def _deduplicate(self, chunks: list[TextChunk]) -> list[TextChunk]:
        kept: list[TextChunk] = []
        signatures: list[set[str]] = []
        for chunk in chunks:
            tokens = set(_TOKEN_RE.findall(chunk.text.lower()))
            if not tokens:
                continue
            duplicate = any(
                len(tokens & previous) / max(1, len(tokens | previous))
                >= self.dedup_similarity
                for previous in signatures
            )
            if not duplicate:
                kept.append(chunk)
                signatures.append(tokens)
        return kept

    @staticmethod
    def _extract_topics(chunks: list[TextChunk]) -> list[str]:
        scores: Counter[str] = Counter()
        for chunk in chunks:
            for word in _TOKEN_RE.findall(chunk.text.lower()):
                scores[word] += 3 if word in _MEDICAL_TERMS else 1
        return [word for word, _ in scores.most_common(8)]

    @staticmethod
    def _prioritize(
        chunks: list[TextChunk],
        topics: list[str],
    ) -> list[TextChunk]:
        ranked: list[TextChunk] = []
        topic_set = set(topics)
        for chunk in chunks:
            words = set(_TOKEN_RE.findall(chunk.text.lower()))
            medical_hits = len(words & _MEDICAL_TERMS)
            topic_hits = len(words & topic_set)
            heading_bonus = 1.5 if chunk.heading else 0.0
            position_bonus = max(0.0, 1.0 - chunk.index * 0.02)
            score = medical_hits * 2.0 + topic_hits + heading_bonus + position_bonus
            ranked.append(
                TextChunk(
                    chunk.index,
                    chunk.text,
                    chunk.heading,
                    chunk.topic,
                    round(score, 3),
                )
            )
        return sorted(ranked, key=lambda item: (-item.priority, item.index))


__all__ = ["LongTextEngine", "LongTextPlan", "TextChunk"]
