"""CLI — `scenario-generator <monde> [--scene N] [--dry-run]`.

Écrit, pour chaque scène :
    <out>/scenes/<id>.yaml      les répliques
    <out>/summaries/<id>.md     le résumé, relu par les scènes suivantes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .dialogue import generate_scene
from .llm import Complete, get_backend
from .summary import summarise
from .world import World, WorldError, load_world


def _scene_yaml(scene, turns: list[dict]) -> str:
    doc = {"name": scene.id, "description": " ".join(scene.stakes.split()), "turns": turns}
    return yaml.dump(doc, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=100)


def _previous_summaries(out: Path, world: World, upto: int) -> str | None:
    parts = []
    for sc in world.scenes[:upto]:
        f = out / "summaries" / f"{sc.id}.md"
        if f.exists():
            parts.append(f.read_text(encoding="utf-8").strip())
        else:
            print(f"[warn] résumé absent pour {sc.id} : la scène sera écrite sans lui",
                  file=sys.stderr)
    return "\n\n---\n\n".join(parts) or None


def run(world: World, out: Path, complete: Complete, scene_no: int | None = None,
        batch_size: int = 10) -> list[Path]:
    indices = range(len(world.scenes)) if scene_no is None else [scene_no - 1]
    prev = _previous_summaries(out, world, indices[0]) if indices[0] else None
    (out / "scenes").mkdir(parents=True, exist_ok=True)
    (out / "summaries").mkdir(parents=True, exist_ok=True)
    written = []
    for k, i in enumerate(indices, 1):
        sc = world.scenes[i]
        print(f"\n[{k}/{len(indices)}] {sc.id} ({sc.turns} répliques)", flush=True)
        turns = generate_scene(world, sc, complete, prev, batch_size)
        path = out / "scenes" / f"{sc.id}.yaml"
        path.write_text(_scene_yaml(sc, turns), encoding="utf-8")
        written.append(path)
        print(f"  → {path}", flush=True)
        summary = summarise(world, sc, turns, complete)
        (out / "summaries" / f"{sc.id}.md").write_text(summary + "\n", encoding="utf-8")
        prev = f"{prev}\n\n---\n\n{summary}" if prev else summary
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="scenario-generator",
                                description="Génère les dialogues d'un scénario, scène par scène.")
    p.add_argument("world", type=Path, help="dossier du monde (world.yaml, characters/, scenario.yaml)")
    p.add_argument("--out", type=Path, help="dossier de sortie (défaut : out/<monde>)")
    p.add_argument("--scene", type=int, help="n'écrire que la scène N (1 = la première)")
    p.add_argument("--dry-run", action="store_true", help="afficher le plan, sans appel au modèle")
    p.add_argument("--backend", default="auto", help="auto, anthropic ou claude-cli")
    p.add_argument("--model", help="modèle Claude (défaut : $SCENARIO_MODEL ou Haiku 4.5)")
    p.add_argument("--batch-size", type=int, default=10)
    args = p.parse_args(argv)

    try:
        world = load_world(args.world)
    except WorldError as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 2
    if args.scene is not None and not 1 <= args.scene <= len(world.scenes):
        print(f"[erreur] --scene doit être entre 1 et {len(world.scenes)}", file=sys.stderr)
        return 2

    print(f"{world.title} — {len(world.scenes)} scènes, "
          f"{len(world.characters)} personnages ({', '.join(world.characters)})")
    if args.dry_run:
        for i, sc in enumerate(world.scenes, 1):
            print(f"  [{i}] {sc.id} — {sc.turns} répliques — tension {sc.tension}/5 — "
                  f"{', '.join(sc.present)}")
        return 0

    out = args.out or Path("out") / args.world.resolve().name
    try:
        complete = get_backend(args.backend, args.model)
    except (RuntimeError, ValueError) as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 2
    run(world, out, complete, args.scene, args.batch_size)
    print(f"\n[ok] scènes écrites dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
