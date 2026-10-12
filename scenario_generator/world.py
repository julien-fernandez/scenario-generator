"""Chargement d'un monde : `world.yaml`, `characters/*.md`, `scenario.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class WorldError(ValueError):
    pass


@dataclass
class Scene:
    id: str
    stakes: str
    present: list[str]
    turns: int = 20
    tension: int = 1
    when: str = ""
    place: str = ""
    absent: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class World:
    root: Path
    title: str
    language: str
    setting: str
    rules: list[str]
    characters: dict[str, str]
    extra_speakers: list[str]
    scenes: list[Scene]

    @property
    def speakers(self) -> list[str]:
        return [*self.characters, *self.extra_speakers]


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise WorldError(f"fichier introuvable : {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WorldError(f"{path.name} doit être un dictionnaire YAML")
    return data


def load_world(root: Path) -> World:
    root = Path(root)
    meta = _read_yaml(root / "world.yaml")

    chars_dir = root / "characters"
    characters = {f.stem: f.read_text(encoding="utf-8").strip()
                  for f in sorted(chars_dir.glob("*.md"))} if chars_dir.exists() else {}
    if not characters:
        raise WorldError(f"aucun personnage dans {chars_dir}")

    extra = [str(s) for s in meta.get("extra_speakers", [])]
    known = set(characters) | set(extra)

    raw_scenes = _read_yaml(root / "scenario.yaml").get("scenes") or []
    if not raw_scenes:
        raise WorldError("scenario.yaml ne contient aucune scène")
    scenes: list[Scene] = []
    for i, s in enumerate(raw_scenes, 1):
        for key in ("id", "stakes", "present"):
            if key not in s:
                raise WorldError(f"scène {i} : clé `{key}` manquante")
        unknown = [p for p in s["present"] + s.get("absent", []) if p not in known]
        if unknown:
            raise WorldError(f"scène {s['id']} : personnages inconnus {unknown}")
        tension = int(s.get("tension", 1))
        if not 1 <= tension <= 5:
            raise WorldError(f"scène {s['id']} : tension hors de 1-5")
        scenes.append(Scene(
            id=str(s["id"]), stakes=str(s["stakes"]).strip(),
            present=list(s["present"]), turns=int(s.get("turns", 20)),
            tension=tension, when=str(s.get("when", "")),
            place=str(s.get("place", "")), absent=list(s.get("absent", [])),
            notes=str(s.get("notes", "")).strip(),
        ))
    if len({s.id for s in scenes}) != len(scenes):
        raise WorldError("deux scènes portent le même id")

    return World(
        root=root,
        title=str(meta.get("title", root.name)),
        language=str(meta.get("language", "français")),
        setting=str(meta.get("setting", "")).strip(),
        rules=[str(r) for r in meta.get("rules", [])],
        characters=characters,
        extra_speakers=extra,
        scenes=scenes,
    )
