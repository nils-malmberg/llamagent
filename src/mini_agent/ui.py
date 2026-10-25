"""L'interface de mini-agent, sans dépendance (étape 17).

Deux idées :
  - une mascotte, dessinée pour le projet, accueille l'utilisateur ;
  - chaque tour de la boucle agentique est affiché avec ses trois acteurs :
    le modèle (ce qu'il demande), le harness (ce que les garde-fous en font)
    et l'outil (ce qu'il renvoie). On voit la boucle du tutoriel tourner.

Tout passe par des codes ANSI : « \\033[...m » change la couleur ou le style
du texte qui suit, « \\033[0m » revient au style normal. Les couleurs sont
celles du site (bleu-vert et orange), prises dans la palette de 256 couleurs.
Si la sortie n'est pas un terminal (redirection vers un fichier) ou si
NO_COLOR est défini, on affiche du texte simple.
"""

import itertools
import json
import os
import re
import shutil
import sys
import threading
import time
from contextlib import contextmanager


def _supports_style() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _supports_unicode() -> bool:
    """Vrai si la console sait afficher la mascotte et les traits."""
    try:
        "┌┴┐│└┬┘─●▬█░►…".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


STYLE = _supports_style()
UNICODE = _supports_unicode()

# Codes de style. « 38;5;N » choisit la couleur N de la palette de 256.
BOLD = "1"
TEAL = "38;5;38"  # le bleu-vert du site
ORANGE = "38;5;208"  # l'orange du site
GREY = "38;5;245"
LIGHT = "38;5;252"
GREEN = "38;5;114"
RED = "38;5;203"
YELLOW = "38;5;221"
CODE = "38;5;117"

# La mascotte : un petit robot, antenne orange, tête bleu-vert.
MASCOT = [
    "    ●  ",
    "  ┌─┴─┐",
    "  │o o│",
    "  │ ▬ │",
    "  └┬─┬┘",
]
MASCOT_ASCII = [
    "    o  ",
    "  .-+-.",
    "  |o o|",
    "  | = |",
    "  '+-+'",
]

# Les trois acteurs de la boucle, plus l'utilisateur.
ROLE_STYLE = {"vous": ORANGE, "modèle": TEAL, "harness": LIGHT, "outil": GREEN}
ROLE_WIDTH = 9  # assez pour « harness » et deux espaces
INDENT = " " * (2 + ROLE_WIDTH)  # pour aligner les lignes suivantes sous le texte

ANSI_CODE = re.compile(r"\033\[[0-9;]*[mK]")


def style(text: str, *codes: str) -> str:
    """Entoure le texte des codes ANSI demandés (ou le laisse tel quel)."""
    if not STYLE or not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}\033[0m"


def visible_len(text: str) -> int:
    """Longueur affichée d'un texte : les codes ANSI ne prennent pas de place."""
    return len(ANSI_CODE.sub("", text))


def symbol(fancy: str, plain: str) -> str:
    return fancy if UNICODE else plain


def shorten(text: str, width: int) -> str:
    """Raccourcit par le début (on garde la fin d'un chemin, la plus parlante)."""
    if len(text) <= width:
        return text
    return symbol("…", "...") + text[-(width - 1):]


# ─────────────────────────── Démarrage ───────────────────────────


def mascot() -> list[str]:
    lines = []
    for number, line in enumerate(MASCOT if UNICODE else MASCOT_ASCII):
        chars = []
        for char in line:
            if char == " ":
                chars.append(char)
            elif number == 0:
                chars.append(style(char, ORANGE, BOLD))  # l'antenne
            elif char == "o":
                chars.append(style(char, BOLD))  # les yeux
            else:
                chars.append(style(char, TEAL))
        lines.append("".join(chars))
    return lines


def banner(rows: list[tuple[str, str]]) -> str:
    """La mascotte, le titre, puis les réglages de la session."""
    dot = symbol(" · ", " - ")
    hint = (
        style("/help", ORANGE) + style(" commandes", GREY) + style(dot, GREY)
        + style("@fichier", ORANGE) + style(" joindre un fichier", GREY) + style(dot, GREY)
        + style("/quit", ORANGE) + style(" quitter", GREY)
    )
    beside = ["", style("mini-agent", BOLD, TEAL), style("un agent de code minimal autour d’Ollama", GREY), "", hint]
    top = [f"{line}   {text}".rstrip() for line, text in zip(mascot(), beside)]
    width = shutil.get_terminal_size().columns - ROLE_WIDTH - 4
    label_width = max(len(label) for label, _ in rows)
    info_lines = [f"  {style(label.ljust(label_width), GREY)}  {shorten(value, width)}" for label, value in rows]
    return "\n" + "\n".join(top) + "\n\n" + "\n".join(info_lines)


# ─────────────────────────── La boucle ───────────────────────────


def role(name: str) -> str:
    """L'étiquette d'un acteur, en couleur, sur une largeur fixe."""
    return "  " + style(name.ljust(ROLE_WIDTH), ROLE_STYLE[name], BOLD)


def role_line(name: str, text: str, *codes: str) -> str:
    return role(name) + style(text, *codes)


def prompt() -> str:
    """L'invite : l'utilisateur est le premier acteur de la conversation."""
    return "\n" + role("vous")


def rule(label: str) -> str:
    """Un trait de séparation avec un titre : « ── tour 2 ─────── »."""
    h = symbol("─", "-")
    width = min(64, shutil.get_terminal_size().columns - 2)
    start = f"{h * 2} {label} "
    return style(start + h * max(3, width - len(start)), GREY)


def tour_header(tour: int) -> str:
    return "\n" + rule(f"tour {tour}")


def call_text(name: str, arguments) -> str:
    """« edit_file(calc.py, …) » : le nom de l'outil et son premier argument."""
    if isinstance(arguments, dict) and arguments:
        values = list(arguments.values())
        detail = str(values[0]) + (", " + symbol("…", "...") if len(values) > 1 else "")
    elif isinstance(arguments, dict):
        detail = ""
    else:
        detail = json.dumps(arguments, ensure_ascii=False)
    if len(detail) > 60:
        detail = detail[:59] + symbol("…", "...")
    return f"{name}({detail})"


def model_asks(name: str, arguments) -> str:
    return role_line("modèle", "demande ") + style(call_text(name, arguments), BOLD)


def tool_result(result: str, truncated: bool = False) -> str:
    is_error = result.startswith(("Erreur", "Refusé"))
    lines = result.splitlines() or [""]
    preview = lines[0][:90] + (f"  (+{len(lines) - 1} lignes)" if len(lines) > 1 else "")
    if truncated:
        preview += "  [tronqué]"
    return role_line("outil", preview, RED if is_error else GREY)


def answer_header(tour: int) -> str:
    calls = f"{tour} appel{'s' if tour > 1 else ''} au modèle"
    return "\n" + rule(f"réponse {symbol('·', '-')} {calls}")


@contextmanager
def thinking(label: str = "réfléchit"):
    """Animation dans la colonne du modèle pendant qu'on attend sa réponse.

    Elle tourne dans un fil d'exécution (thread) séparé : le programme
    principal, lui, est bloqué dans la requête HTTP. « \\r » ramène le
    curseur en début de ligne, « \\033[K » efface la ligne à la fin.
    """
    if not STYLE:
        yield
        return
    stop = threading.Event()

    def animate() -> None:
        start = time.monotonic()
        for dots in itertools.cycle(["   ", ".  ", ".. ", "..."]):
            elapsed = time.monotonic() - start
            sys.stdout.write(f"\r{role('modèle')}{style(f'{label}{dots} {elapsed:.0f} s', GREY)}")
            sys.stdout.flush()
            if stop.wait(0.3):  # attend 0,3 s, ou s'arrête si on le lui demande
                break
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    thread = threading.Thread(target=animate, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def confirm(question: str) -> bool:
    """Comme guards.ask_confirmation, avec le diff en couleurs, aligné sous le harness."""
    lines = question.splitlines() or [""]
    for line in lines[:-1]:
        if line.startswith(("+++", "---")):
            line = style(line, GREY)
        elif line.startswith("+"):
            line = style(line, GREEN)
        elif line.startswith("-"):
            line = style(line, RED)
        elif line.startswith("@@"):
            line = style(line, CODE)
        print(INDENT + line)
    reply = input(f"{INDENT}{style('?', ORANGE, BOLD)} {lines[-1]} {style('[o/N]', BOLD)} ")
    return reply.strip().lower() in ("o", "oui")


# ─────────────────────────── Réponse ───────────────────────────

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD_TEXT = re.compile(r"\*\*(.+?)\*\*")
BULLET = re.compile(r"^(\s*)[-*] (.*)")


def render_markdown(text: str) -> str:
    """Un rendu très simple du Markdown des réponses : titres, gras, `code`,
    listes et blocs de code. Sans couleurs, le texte reste tel quel."""
    if not STYLE:
        return text
    lines, in_code = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code  # les lignes ``` elles-mêmes ne sont pas affichées
            continue
        if in_code:
            lines.append(style(symbol("│ ", "| "), GREY) + style(line, CODE))
            continue
        if line.startswith("#"):
            lines.append(style(line.lstrip("#").strip(), BOLD, TEAL))
            continue
        bullet = BULLET.match(line)
        if bullet:
            line = f"{bullet.group(1)}{style(symbol('►', '-'), ORANGE)} {bullet.group(2)}"
        line = BOLD_TEXT.sub(lambda match: style(match.group(1), BOLD), line)
        line = INLINE_CODE.sub(lambda match: style(match.group(1), CODE), line)
        lines.append(line)
    return "\n".join(lines)


def answer(text: str) -> str:
    """La réponse finale, décalée sous le trait « réponse »."""
    return "\n".join("  " + line for line in render_markdown(text).splitlines())


def context_gauge(model: str, used: int, size: int, estimated: bool) -> str:
    """Une jauge de remplissage du contexte, affichée sous chaque réponse."""
    ratio = min(1.0, used / size)
    filled = round(ratio * 10)
    bar = symbol("█", "#") * filled + symbol("░", "-") * (10 - filled)
    level = RED if used >= size else YELLOW if used >= 0.75 * size else TEAL
    dot = symbol(" · ", " - ")
    approx = symbol("≈", "~") if estimated else ""
    text = style(f"  contexte {bar}", level) + style(f" {approx}{used} / {size} tokens ({int(ratio * 100)} %){dot}{model}", GREY)
    if used >= size:
        text += style("  plein : Ollama a coupé le début de la conversation", RED)
    return text


# ─────────────────────────── Messages ───────────────────────────


def info(text: str) -> str:
    """Un message secondaire, aligné sous le texte (fichier joint...)."""
    return style(f"{INDENT}{text}", GREY)


def warning(text: str) -> str:
    return style(f"  {text}", YELLOW)


def error(text: str) -> str:
    return style(f"  {symbol('×', 'x')} {text}", RED)


def indent(text: str) -> str:
    """Décale un bloc de texte (sortie des commandes /...)."""
    return "\n".join("  " + line for line in text.splitlines())