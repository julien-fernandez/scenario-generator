# Scenario Generator

Writes a screenplay's dialogue scene by scene with Claude.

You describe a **world** in a few files — the setting, the characters, the sequence of scenes
with their stakes and tension — and the tool writes the lines. After each scene it writes a
summary of about 200 words: the next scene reads it, so the story keeps its memory without
re-reading every line of dialogue.

```
world  ──►  dialogue writer (batches of 10 lines)  ──►  scenes/<id>.yaml
                    ▲                                         │
                    └──────────  summariser  ◄────────────────┘
                              summaries/<id>.md
```

## Install

```bash
uv sync            # or: pip install -e .
```

Two ways to call Claude, picked automatically (`--backend auto`):

- **`anthropic`** — the API, when `ANTHROPIC_API_KEY` is set;
- **`claude-cli`** — otherwise, the `claude -p` command of
  [Claude Code](https://claude.com/claude-code), with its usual authentication.

The default model is Claude Haiku 4.5; `--model` or the `SCENARIO_MODEL` variable change it.

## Try it

`examples/pension-rivage` holds a small world (in French): a family guesthouse in Brittany,
a brother and a sister who must decide whether to sell it.

```bash
uv run scenario-generator examples/pension-rivage --dry-run   # the plan, no model call
uv run scenario-generator examples/pension-rivage             # the three scenes
uv run scenario-generator examples/pension-rivage --scene 2   # scene 2 only
```

Files land in `out/pension-rivage/` (or `--out`); a real run is kept in
`examples/pension-rivage/exemple-sortie/`. A scene written on its own reads the summaries of
earlier scenes when they already exist.

## Describing a world

```
my-world/
├── world.yaml        setting and writing rules
├── scenario.yaml     the sequence of scenes
└── characters/
    ├── anne.md       one sheet per character; the file name is the speaker id
    └── paul.md
```

**`world.yaml`**

| Key | Role |
|-----|------|
| `title` | title of the fiction |
| `language` | language of the lines (default: `français`) |
| `setting` | the setting, the starting situation |
| `rules` | writing rules specific to this world (list) |
| `extra_speakers` | speakers without a sheet: a customer, a radio, a phone… |

**`scenario.yaml`** — a `scenes` list, each scene with:

| Key | Role |
|-----|------|
| `id` | identifier, used as the file name (required) |
| `stakes` | the dramatic stakes of the scene (required) |
| `present` | the speakers on stage (required) |
| `absent` | characters talked about who do not speak |
| `turns` | number of lines (default: 20) |
| `tension` | from 1 (calm) to 5 (crisis) |
| `when`, `place` | time and place |
| `notes` | author's instructions for this scene |

The world is validated on load: an unknown character, a tension outside 1-5 or two scenes with
the same `id` stop the tool before any model call.

## Output

`scenes/<id>.yaml`:

```yaml
name: 01-retour
description: Paul arrive de Paris pour la première fois depuis l'enterrement…
turns:
- speaker: anne
  text: Tu as pris le train de quelle heure ?
  mood: affairée
```

## Tests

```bash
uv run pytest -q
```

Tests never call the model: a fake backend returns the lines.

## License

MIT, see [`LICENSE`](LICENSE).
