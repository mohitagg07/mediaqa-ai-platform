"""
llm_service.py — improved prompt to avoid false "not found" responses

KEY FIXES:
  - Stronger prompt: "Answer ONLY using the context. DO NOT say not found unless truly absent."
  - Summary prompt asks for markdown-formatted structured output
  - find_relevant_timestamp_chunk returns the semantically closest chunk
"""

import logging
from typing import List, Optional, AsyncGenerator
from groq import Groq
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[Groq] = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _build_qa_prompt(question: str, context_chunks: List[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    return (
        "You are a precise AI assistant. Your ONLY job is to answer the user's question "
        "using the context below.\n\n"
        "RULES:\n"
        "- Answer clearly and directly using information from the context.\n"
        "- If the answer is present, give it — do NOT say it is missing.\n"
        "- Use markdown formatting (bullet points, bold, headers) to structure your answer.\n"
        "- Only say 'not found' if the information is genuinely absent from the context.\n"
        "- Never make up information not in the context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def _build_summary_prompt(text: str) -> str:
    return (
        "You are an expert document analyst. Summarize the following content.\n\n"
        "FORMAT YOUR RESPONSE EXACTLY LIKE THIS:\n"
        "## Overview\n"
        "2-3 sentences describing what this document/media is about.\n\n"
        "## Key Points\n"
        "- Point 1\n"
        "- Point 2\n"
        "- Point 3 (etc.)\n\n"
        "## Details\n"
        "Any important specifics, names, dates, numbers, or conclusions.\n\n"
        "Keep the total summary concise (under 300 words). "
        "Use proper markdown formatting throughout.\n\n"
        f"Content:\n{text}\n\n"
        "Summary:"
    )


def answer_question(question: str, context_chunks: List[str]) -> str:
    prompt = _build_qa_prompt(question, context_chunks)
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,   # lower = more factual
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"LLM answered question: {question[:50]}...")
        return answer
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise RuntimeError(f"LLM error: {str(e)}")


async def stream_answer_question(
    question: str, context_chunks: List[str]
) -> AsyncGenerator[str, None]:
    """Stream LLM answer token by token."""
    prompt = _build_qa_prompt(question, context_chunks)
    try:
        client = get_groq_client()
        stream = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
        logger.info(f"LLM streamed answer for: {question[:50]}...")
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        raise RuntimeError(f"LLM streaming error: {str(e)}")


def generate_summary(text: str) -> str:
    """Generate a structured markdown summary of the provided text."""
    truncated = text[:8000] if len(text) > 8000 else text
    prompt = _build_summary_prompt(truncated)
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        logger.info("Summary generated successfully")
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise RuntimeError(f"Summary generation failed: {str(e)}")


def find_relevant_timestamp_chunk(question: str, context_chunks: List[str]) -> Optional[str]:
    """Return the top-ranked chunk for timestamp matching (FAISS already ranked these)."""
    if not context_chunks:
        return None
    return context_chunks[0]
