from pathlib import Path

import pytest
import yaml

from scenario_generator.cli import main, run
from scenario_generator.dialogue import build_prompt, generate_scene, parse_turns
from scenario_generator.world import WorldError, load_world

EXAMPLE = Path(__file__).parent.parent / "examples" / "pension-rivage"


class FakeLLM:
    """Renvoie des répliques valides, ou un résumé si le prompt en demande un."""

    def __init__(self, speakers, garbage_first=0):
        self.speakers = speakers
        self.garbage_left = garbage_first
        self.calls = []

    def __call__(self, system, prompt, *, max_tokens, temperature):
        self.calls.append(prompt)
        if "Write the summary" in prompt:
            return "Résumé de la scène."
        if self.garbage_left:
            self.garbage_left -= 1
            return "pas du yaml : ["
        n = int(prompt.split("Write exactly ")[1].split()[0])
        return yaml.dump([{"speaker": self.speakers[i % len(self.speakers)],
                           "text": f"réplique {i}"} for i in range(n)],
                         allow_unicode=True)


def test_load_example_world():
    w = load_world(EXAMPLE)
    assert w.title == "La pension Rivage"
    assert set(w.characters) == {"anne", "paul", "mathilde"}
    assert w.speakers[-1] == "client"
    assert [s.id for s in w.scenes] == ["01-retour", "02-l-offre", "03-la-digue"]


def test_unknown_character_is_rejected(tmp_path):
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "a.md").write_text("A")
    (tmp_path / "world.yaml").write_text("title: t\n")
    (tmp_path / "scenario.yaml").write_text(
        "scenes:\n  - {id: s1, stakes: x, present: [a, zorro]}\n")
    with pytest.raises(WorldError, match="zorro"):
        load_world(tmp_path)


def test_parse_turns_strips_fences_and_unknown_speakers():
    raw = "```yaml\n- speaker: anne\n  text: Bonjour\n  mood: las\n- speaker: x\n  text: Quoi\n```"
    assert parse_turns(raw, ["anne"]) == [{"speaker": "anne", "text": "Bonjour", "mood": "las"}]
    assert parse_turns("pas du yaml : [", ["anne"]) == []


def test_prompt_carries_history():
    w = load_world(EXAMPLE)
    p = build_prompt(w.scenes[2], "Avant.", [{"speaker": "paul", "text": "Salut"}], 4)
    assert "Avant." in p and "paul: Salut" in p and "Write exactly 4 lines" in p
    assert "Absent" in p and "anne" in p


def test_generate_scene_batches_and_retries():
    w = load_world(EXAMPLE)
    sc = w.scenes[0]  # 12 répliques
    fake = FakeLLM(["anne", "paul"], garbage_first=1)
    turns = generate_scene(w, sc, fake, batch_size=5, log=lambda *_: None)
    assert len(turns) == 12
    assert len(fake.calls) == 4  # 1 raté + 3 lots (5, 5, 2)


def test_absent_character_cannot_speak():
    w = load_world(EXAMPLE)
    turns = generate_scene(w, w.scenes[2], FakeLLM(["anne", "paul"]), log=lambda *_: None)
    assert turns and all(t["speaker"] == "paul" for t in turns)


def test_run_writes_scenes_and_summaries(tmp_path):
    w = load_world(EXAMPLE)
    fake = FakeLLM(["anne", "paul", "mathilde"])
    run(w, tmp_path, fake)
    for sc in w.scenes:
        doc = yaml.safe_load((tmp_path / "scenes" / f"{sc.id}.yaml").read_text())
        assert doc["name"] == sc.id and doc["turns"]
        assert (tmp_path / "summaries" / f"{sc.id}.md").exists()
    # Une scène seule relit les résumés des précédentes.
    fake.calls.clear()
    run(w, tmp_path, fake, scene_no=3)
    assert "SUMMARY OF PREVIOUS SCENES" in fake.calls[0]


def test_dry_run(capsys):
    assert main([str(EXAMPLE), "--dry-run"]) == 0
    assert "03-la-digue" in capsys.readouterr().out
