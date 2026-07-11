"""
Thin wrapper around a local Ollama instance for:
  - text embeddings (used for both indexing and query-time retrieval)
  - chat completion (used to generate the final grounded answer)

No API keys required — everything runs against a local `ollama serve`.
"""
from typing import List

import ollama
 
from . import config

_client = ollama.Client(host=config.OLLAMA_HOST)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts using the configured Ollama embedding model."""
    if not texts:
        return []
    vectors = []
    for text in texts:
        resp = _client.embeddings(model=config.EMBED_MODEL, prompt=text)
        vectors.append(resp["embedding"])
    return vectors


def embed_query(text: str) -> List[float]:
    resp = _client.embeddings(model=config.EMBED_MODEL, prompt=text)
    return resp["embedding"]


SYSTEM_PROMPT = (
    "You are a careful, factual assistant that answers questions strictly using "
    "the provided document excerpts (CONTEXT). Rules:\n"
    "1. Only use information found in the CONTEXT to answer.\n"
    "2. If the CONTEXT does not contain enough information to answer, say so "
    "clearly instead of guessing.\n"
    "3. When you use a piece of context, mention which source it came from "
    "(e.g. 'According to report.pdf...').\n"
    "4. Be concise and directly answer the question first, then add supporting "
    "detail if useful.\n"
)


def generate_answer(question: str, context_blocks: List[str], history: List[dict] = None) -> str:
    """Call the chat model with retrieved context to produce a grounded answer."""
    context_text = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for turn in history[-6:]:  # keep a short rolling window
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    user_message = (
        f"CONTEXT:\n{context_text}\n\n"
        f"QUESTION:\n{question}\n\n"
        "Answer the question using only the context above."
    )
    messages.append({"role": "user", "content": user_message})

    resp = _client.chat(model=config.CHAT_MODEL, messages=messages)
    return resp["message"]["content"]
