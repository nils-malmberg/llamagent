"""Mesurer et compacter le contexte (étape 16).

Mesurer : Ollama donne la taille totale après chaque appel (étape 13). Pour
savoir ce qui remplit le contexte, on estime la part de chaque catégorie de
messages à partir du nombre de caractères.

Compacter : quand le contexte est presque plein, on demande au modèle de
résumer la conversation, puis on remplace toute la conversation par ce
résumé. Le prompt système, lui, est gardé tel quel.
"""

import json

from mini_agent import llm
from mini_agent.config import COMPACT_THRESHOLD, PROMPTS_DIR
from mini_agent.guards import truncate
from mini_agent.tools import tool_schemas

# Approximation : environ 4 caractères par token, en français comme en code.
# Ce n'est qu'une estimation ; la vraie mesure vient d'Ollama.
CHARS_PER_TOKEN = 4
# Dans le texte à résumer, chaque résultat d'outil ou argument est raccourci.
TRANSCRIPT_ITEM_CHARS = 300


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def message_text(message: dict) -> str:
    """Tout le texte d'un message, appels d'outils compris."""
    calls = message.get("tool_calls") or []
    return (message.get("content") or "") + (json.dumps(calls, ensure_ascii=False) if calls else "")


def estimate_messages(messages: list[dict]) -> int:
    """Estimation de la place occupée par des messages et par les schémas des outils."""
    text = "".join(message_text(m) for m in messages) + json.dumps(tool_schemas(), ensure_ascii=False)
    return estimate_tokens(text)


def context_report(session) -> str:
    """Ce qui occupe le contexte, catégorie par catégorie (commande /context)."""
    parts = {
        "prompt système": 0,
        "schémas des outils": estimate_tokens(json.dumps(tool_schemas(), ensure_ascii=False)),
        "vos messages": 0,
        "réponses du modèle": 0,
        "résultats d'outils": 0,
    }
    category = {"system": "prompt système", "user": "vos messages", "assistant": "réponses du modèle", "tool": "résultats d'outils"}
    for message in session.messages:
        parts[category[message["role"]]] += estimate_tokens(message_text(message))
    total = sum(parts.values())
    size = session.config.num_ctx
    filled = min(20, round(20 * total / size))
    lines = [f"{name:<20} ≈ {tokens:>6} tokens" for name, tokens in parts.items()]
    lines += [
        f"{'total estimé':<20} ≈ {total:>6} tokens  [{'#' * filled}{'-' * (20 - filled)}] {100 * total // size} % de {size}",
        f"dernier total : {session.context_tokens} tokens ({'estimation' if session.context_estimated else 'mesuré par Ollama'})",
        f"compactage automatique à {int(COMPACT_THRESHOLD * 100)} %, ou maintenant avec /compact",
    ]
    return "\n".join(lines)


def transcript(messages: list[dict]) -> str:
    """La conversation en texte simple, pour la faire résumer par le modèle."""
    lines = []
    for message in messages:
        role = message["role"]
        if role == "user":
            lines.append(f"UTILISATEUR : {truncate(message['content'], 4 * TRANSCRIPT_ITEM_CHARS)}")
        elif role == "assistant":
            if message.get("content"):
                lines.append(f"AGENT : {message['content']}")
            for call in message.get("tool_calls") or []:
                arguments = json.dumps(call["function"].get("arguments", {}), ensure_ascii=False)
                lines.append(f"AGENT appelle {call['function']['name']} {truncate(arguments, TRANSCRIPT_ITEM_CHARS)}")
        elif role == "tool":
            lines.append(f"RÉSULTAT de {message.get('tool_name', '?')} : {truncate(message['content'], TRANSCRIPT_ITEM_CHARS)}")
    return "\n".join(lines)


def needs_compaction(session) -> bool:
    return session.context_tokens >= COMPACT_THRESHOLD * session.config.num_ctx


def compact(session) -> str:
    """Remplace la conversation par un résumé écrit par le modèle, et renvoie ce résumé."""
    conversation = session.messages[1:]
    if not conversation:
        return ""
    # Le texte à résumer doit lui-même tenir dans le contexte : au plus la
    # moitié, en coupant le milieu (truncate garde le début et la fin).
    text = truncate(transcript(conversation), session.config.num_ctx * CHARS_PER_TOKEN // 2)
    instructions = (PROMPTS_DIR / "COMPACT.md").read_text(encoding="utf-8")
    # Appel sans outils : on veut du texte, pas des tool calls.
    reply = llm.chat(session.config, [{"role": "system", "content": instructions}, {"role": "user", "content": text}])
    summary = (reply.get("content") or "").strip()
    session.remember_title()  # avant que la première demande ne disparaisse
    session.messages = [
        session.messages[0],  # le prompt système est gardé tel quel
        {"role": "user", "content": f"Résumé de notre conversation jusqu'ici (le début a été compacté) :\n\n{summary}"},
        {"role": "assistant", "content": "Compris, je reprends à partir de ce résumé."},
    ]
    session.context_tokens = estimate_messages(session.messages)
    session.context_estimated = True
    return summary