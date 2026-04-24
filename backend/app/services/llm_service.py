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
        "You are a precise AI assistant. Answer the question using ONLY the context below.\n\n"
        "RULES:\n"
        "- Answer directly using information from the context.\n"
        "- DO NOT add external information or hallucinate.\n"
        "- If the answer is genuinely absent from the context, say so briefly.\n"
        "- Use markdown formatting where helpful.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def _build_summary_prompt(text: str) -> str:
    return (
        "You are given the extracted text or transcript from a document or media file.\n\n"
        "Your task is to summarize it.\n\n"
        "STRICT RULES:\n"
        "- Base your summary ENTIRELY on the provided text below.\n"
        "- DO NOT add any information not present in the text.\n"
        "- DO NOT hallucinate, guess, or invent content.\n"
        "- If the text is short or simple, keep the summary short and factual.\n\n"
        "OUTPUT FORMAT (use exactly this structure):\n"
        "## Overview\n"
        "1-2 sentences describing what this content is about.\n\n"
        "## Key Points\n"
        "- Bullet point 1\n"
        "- Bullet point 2\n"
        "(only include points that are actually in the text)\n\n"
        "## Details\n"
        "Any specific names, numbers, topics, or conclusions found in the text.\n\n"
        f"Text to summarize:\n\"\"\"\n{text}\n\"\"\"\n\n"
        "Summary:"
    )


def _build_visual_summary_prompt(metadata_text: str) -> str:
    """
    For silent videos — generates a human-friendly content description
    instead of a dry technical report.
    """
    return (
        "You are given metadata about a video file that contains no detectable speech.\n\n"
        "Your task is to write a short, natural, user-friendly summary of what this "
        "video likely contains based only on the metadata provided.\n\n"
        "STRICT RULES:\n"
        "- Do NOT use technical jargon like 'codec', 'bitrate', or 'container format'.\n"
        "- Write as if describing the video to a non-technical user.\n"
        "- Keep it to 2-3 sentences.\n"
        "- Do NOT invent specific content (characters, scenes, story) — only infer "
        "from what the metadata tells you (duration, resolution, presence of audio track).\n\n"
        f"Metadata:\n\"\"\"\n{metadata_text}\n\"\"\"\n\n"
        "Summary:"
    )


def generate_summary(text: str, is_silent_video: bool = False) -> str:
    """
    Generate a grounded summary of the provided text or transcript.
    For silent videos, uses a content-style prompt instead of a metadata dump.
    """
    truncated = text[:8000] if len(text) > 8000 else text
    prompt = (
        _build_visual_summary_prompt(truncated)
        if is_silent_video
        else _build_summary_prompt(truncated)
    )
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1,   # near-zero = grounded, no creativity
        )
        summary = response.choices[0].message.content.strip()
        logger.info("Summary generated successfully")
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise RuntimeError(f"Summary generation failed: {str(e)}")


def answer_question(question: str, context_chunks: List[str]) -> str:
    prompt = _build_qa_prompt(question, context_chunks)
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"LLM answered: {question[:50]}")
        return answer
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise RuntimeError(f"LLM error: {str(e)}")


async def stream_answer_question(
    question: str, context_chunks: List[str]
) -> AsyncGenerator[str, None]:
    prompt = _build_qa_prompt(question, context_chunks)
    try:
        client = get_groq_client()
        stream = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
        logger.info(f"LLM streamed answer for: {question[:50]}")
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        raise RuntimeError(f"LLM streaming error: {str(e)}")


def find_relevant_timestamp_chunk(
    question: str, context_chunks: List[str]
) -> Optional[str]:
    if not context_chunks:
        return None
    return context_chunks[0]
