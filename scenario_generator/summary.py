"""Résumeur — environ 200 mots par scène, lus par le dialoguiste à la scène suivante."""

from __future__ import annotations

from .llm import Complete
from .world import Scene, World

_SYSTEM = """\
You summarise one scene of the interactive fiction "{title}", in {language}.
The summary (about 200 words of prose) is read by the dialogue writer before the next scene.
Include: key events, how each character's feelings moved, decisions and telling silences,
the state of every tension at the end of the scene.
Leave out: line-by-line recaps, meta commentary, analysis.
"""


def summarise(world: World, scene: Scene, turns: list[dict],
              complete: Complete) -> str:
    lines = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
    prompt = (f"Scene: {scene.id}\nStakes: {scene.stakes}\n\nLINES:\n{lines}\n\n"
              "Write the summary.")
    return complete(_SYSTEM.format(title=world.title, language=world.language),
                    prompt, max_tokens=600, temperature=0.3).strip()
