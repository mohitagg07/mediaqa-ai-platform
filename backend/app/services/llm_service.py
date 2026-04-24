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
    return f"""You are a precise Q&A assistant. Answer using ONLY the context below.

STRICT RULES:
- Use ONLY information from the context.
- DO NOT add anything not present in the context.
- DO NOT hallucinate, invent, or guess.
- If the answer is not in the context, say: "This information is not in the provided content."
- For transcript requests, quote the text exactly as it appears.
- Use markdown formatting (bullet points, bold) where helpful.

Context:
\"\"\"
{context}
\"\"\"

Question: {question}

Answer:"""


def _build_summary_prompt(text: str) -> str:
    return f"""You are given the exact text or transcript from a document or media file.

STRICT RULES:
- Summarize ONLY what is EXPLICITLY written in the text below.
- DO NOT infer personal preferences, opinions, or themes unless clearly stated.
- DO NOT hallucinate or add anything not present.
- If the text appears to be unrelated test phrases or sentences, say so explicitly.
- Do not assume meaning beyond what is literally written.

Text:
\"\"\"
{text}
\"\"\"

Output this exact format:

## Overview
One or two sentences describing what this content literally contains.

## Key Points
- List only statements that are actually present in the text
- Do not interpret or generalize

## Details
Describe the nature of this content (e.g., "a series of unrelated test sentences", "a structured document about X", "spoken phrases used for audio testing").
"""


def _build_visual_summary_prompt(metadata_text: str) -> str:
    return f"""You are given metadata about a video file with no detectable speech.

Write a short, user-friendly description (2-3 sentences) of what this video likely contains.

RULES:
- Do NOT use technical terms like codec, bitrate, container.
- Only infer from: duration, resolution, presence/absence of audio.
- Do NOT invent characters, scenes, or storylines.
- Be factual and professional.

Metadata:
\"\"\"
{metadata_text}
\"\"\"

Description:"""


def generate_summary(text: str, is_silent_video: bool = False) -> str:
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
            temperature=0.0,
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
            temperature=0.0,
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
            temperature=0.0,
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


def find_relevant_timestamp_chunk(question: str, context_chunks: List[str]) -> Optional[str]:
    return context_chunks[0] if context_chunks else None