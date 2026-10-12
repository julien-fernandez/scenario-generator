"""Dialoguiste — écrit les répliques d'une scène, par lots.

Chaque lot reçoit le résumé des scènes précédentes et les dernières répliques
déjà écrites, pour que la scène avance sans se répéter.
"""

from __future__ import annotations

import re
import sys

import yaml

from .llm import Complete
from .world import Scene, World

_SYSTEM = """\
You are the dialogue writer of an interactive fiction titled "{title}".
Write every line in {language}.

SETTING:
{setting}

CHARACTERS (the file name is the speaker id):
{characters}

WRITING RULES:
- Characters act on their own motives, not as plot devices.
- Tension follows the scene's tension level (1 = calm, 5 = crisis).
- Lines are short (one or two sentences), natural and plausible.
- No neat resolution: scenes may end unresolved.
- No narration, no meta commentary.
{rules}
OUTPUT FORMAT — MANDATORY:
Answer ONLY with a valid YAML list, no markdown fence, nothing before or after:
- speaker: "<speaker id>"   # one of: {speakers}
  text: "..."
  mood: "..."               # optional, one or two words
"""


def build_system(world: World) -> str:
    chars = "\n\n".join(f"### {cid}\n{text}" for cid, text in world.characters.items())
    rules = "".join(f"- {r}\n" for r in world.rules)
    return _SYSTEM.format(
        title=world.title, language=world.language, setting=world.setting,
        characters=chars, rules=rules, speakers=", ".join(world.speakers),
    )


def build_prompt(scene: Scene, prev_summary: str | None, so_far: list[dict],
                 n: int) -> str:
    lines = [f"SCENE: {scene.id}"]
    if scene.when:
        lines.append(f"When: {scene.when}")
    if scene.place:
        lines.append(f"Where: {scene.place}")
    lines.append(f"Tension: {scene.tension}/5")
    lines.append(f"Present: {', '.join(scene.present)}")
    if scene.absent:
        lines.append(f"Absent (may be mentioned, never speak): {', '.join(scene.absent)}")
    lines.append(f"\nStakes:\n{scene.stakes}")
    if scene.notes:
        lines.append(f"\nAuthor's notes:\n{scene.notes}")
    if prev_summary:
        lines.append(f"\nSUMMARY OF PREVIOUS SCENES:\n{prev_summary.strip()}")
    else:
        lines.append("\nThis is the first scene: no history.")
    if so_far:
        lines.append(f"\nLINES ALREADY WRITTEN ({len(so_far)}/{scene.turns}), last ones:")
        for t in so_far[-6:]:
            mood = f" [{t['mood']}]" if t.get("mood") else ""
            lines.append(f"  {t['speaker']}{mood}: {t['text']}")
    start = len(so_far)
    lines.append(
        f"\nWrite exactly {n} lines (lines {start + 1} to {start + n} of "
        f"{scene.turns}). Continue naturally from where the scene stands."
    )
    return "\n".join(lines)


def parse_turns(raw: str, speakers: list[str]) -> list[dict]:
    """Lit la liste YAML renvoyée ; écarte les répliques sans locuteur connu."""
    text = raw.strip()
    m = re.search(r"```(?:ya?ml)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, list):
        return []
    turns = []
    for item in data:
        if not (isinstance(item, dict) and "speaker" in item and "text" in item):
            continue
        speaker = str(item["speaker"]).strip()
        if speaker not in speakers:
            print(f"  [warn] locuteur inconnu écarté : {speaker}", file=sys.stderr)
            continue
        t = {"speaker": speaker, "text": str(item["text"]).strip()}
        if item.get("mood"):
            t["mood"] = str(item["mood"]).strip()
        turns.append(t)
    return turns


def generate_scene(world: World, scene: Scene, complete: Complete,
                   prev_summary: str | None = None, batch_size: int = 10,
                   log=print) -> list[dict]:
    system = build_system(world)
    allowed = [s for s in world.speakers if s not in scene.absent]
    turns: list[dict] = []
    failures = 0
    while len(turns) < scene.turns:
        n = min(batch_size, scene.turns - len(turns))
        prompt = build_prompt(scene, prev_summary, turns, n)
        batch = parse_turns(complete(system, prompt, max_tokens=2048, temperature=0.8),
                            allowed)
        if not batch:
            # Un second essai, plus sage, avant d'abandonner le lot.
            batch = parse_turns(complete(system, prompt, max_tokens=2048,
                                         temperature=0.5), allowed)
        if not batch:
            failures += 1
            log(f"  lot illisible ({failures}/2)")
            if failures >= 2:
                break
            continue
        turns.extend(batch[:n])
        log(f"  lot : +{min(len(batch), n)} répliques ({len(turns)}/{scene.turns})")
    return turns
