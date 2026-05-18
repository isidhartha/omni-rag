"""Document summarizer using OpenAI or Anthropic with graceful fallback."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("omnirag.summarizer")


class Summarizer:
    """Generate abstractive summaries for documents or query answers."""

    SUMMARY_PROMPT = (
        "You are an expert summarizer. Summarize the following text concisely, "
        "preserving key facts, entities, and structure. Keep it under 200 words.\n\n"
        "TEXT:\n{text}"
    )

    QA_PROMPT = (
        "You are OmniRAG, a precise and helpful research assistant. "
        "Answer the user's question based ONLY on the provided context. "
        "If the context does not contain enough information, say so clearly. "
        "Always cite sources by referencing the chunk IDs provided.\n\n"
        "CONTEXT:\n{context}\n\n"
        "QUESTION: {question}\n\n"
        "ANSWER (be thorough but concise, cite relevant sources):"
    )

    def __init__(self, openai_client=None, anthropic_client=None) -> None:
        self._openai = openai_client
        self._anthropic = anthropic_client

    def summarize(self, text: str, max_tokens: int = 300) -> str:
        """Summarize a text passage."""
        if not text.strip():
            return ""
        prompt = self.SUMMARY_PROMPT.format(text=text[:6000])
        return self._generate(prompt, max_tokens)

    def answer_with_context(
        self,
        question: str,
        context_chunks: list[dict],
        max_tokens: int = 1024,
    ) -> str:
        """Generate a RAG answer given retrieved chunks."""
        context_parts = []
        for chunk in context_chunks:
            source_info = f"[Source: {chunk.get('filename', 'unknown')}, Chunk: {chunk.get('chunk_id', '?')}]"
            context_parts.append(f"{source_info}\n{chunk.get('text', '')}")

        context = "\n\n---\n\n".join(context_parts)
        prompt = self.QA_PROMPT.format(context=context[:8000], question=question)
        return self._generate(prompt, max_tokens)

    def _generate(self, prompt: str, max_tokens: int) -> str:
        """Route to available LLM backend."""
        if self._openai:
            return self._openai_generate(prompt, max_tokens)
        if self._anthropic:
            return self._anthropic_generate(prompt, max_tokens)
        logger.warning("No LLM backend configured — returning stub answer.")
        return "[LLM not configured: please set OPENAI_API_KEY or ANTHROPIC_API_KEY]"

    def _openai_generate(self, prompt: str, max_tokens: int) -> str:
        from backend.shared.config import get_settings
        settings = get_settings()
        response = self._openai.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _anthropic_generate(self, prompt: str, max_tokens: int) -> str:
        response = self._anthropic.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""
