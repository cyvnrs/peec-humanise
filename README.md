# peec-humanise

A Claude Code plugin that rewrites [Peec AI](https://app.peec.ai) tracked prompts from stiff SEO-flavoured copy into the language real people actually type into search boxes — lowercase, short, occasional typos, no corporate filler — grounded in verbatim phrasing harvested from Reddit, HN, Quora, and X for each tracked topic.

Turns this

> Which platform offers the best AI safety training for busy professionals seeking certification?

into this

> best ai safety training course

or this

> ai safety cert worth it reddit

Daily prompt runs on Peec are only useful if they mirror how humans search. This plugin closes that gap.

## What it does

When you type `/peec-humanise`:

1. Silently verifies the Peec AI MCP server is installed and authed; guides setup if not.
2. Picks your project (auto if one, asks if multiple).
3. Pulls all tracked prompts and groups them by topic — no brand selection needed, the rewrite is topic-grounded.
4. For each topic, runs parallel Reddit/HN/Quora/X searches to build a per-topic tone dictionary of how real humans phrase things about that space.
5. Rewrites every prompt using a strict rule set (ban list for `seeking`, `busy professional`, `leveraging`, `comprehensive`, `robust`; lowercase; drop articles and question marks; ~25% typo rate; 2-6 word target) blended with the harvested tone.
6. Launches an interactive curses picker:
   - `up` / `down` to scroll through before/after pairs
   - `y` to accept the primary rewrite
   - `a` to accept the alternate rewrite
   - `n` to reject (keep the old prompt)
   - `tab` to toggle between primary and alt in the preview
   - navigate past the last row to `[ submit accepted to peec ]` and hit `enter`
7. For each accepted rewrite, calls `delete_prompts` + `create_prompts` on the Peec MCP (preserving `topic_id` and `tag_ids`).

## Peec's prompt action model

**Peec treats prompt text as immutable.** There is no in-place text edit — a rewrite is `delete_prompt(old)` + `create_prompt(new)`. Consequences:

- The old `prompt_id` and its historical daily runs are destroyed.
- Brand-report, URL-report, and chat history tied to that prompt_id become orphaned.
- The new prompt starts collecting metrics from day one.
- Topic and tag assignments are preserved because the plugin carries them forward in the `create_prompts` payload.

The picker footer surfaces this warning so you see it before pressing enter.

## Install

### via local marketplace (clone first)

```
git clone https://github.com/cyvnrs/peec-humanise.git
/plugin marketplace add /absolute/path/to/peec-humanise
/plugin install peec-humanise@peec-humanise
```

### OR project-local skill (no plugin system)

```
git clone https://github.com/cyvnrs/peec-humanise.git
mkdir -p .claude/skills
cp -R peec-humanise/plugins/peec-humanise/skills/peec-humanise .claude/skills/
```

Then type `/peec-humanise` while in that project.

## Prerequisites

- Peec AI MCP server installed and authed (`mcp__peec-ai__*` tools must be available)
- `WebSearch` tool available in your Claude Code session
- Python 3.12 (stdlib `curses` only — no `pip install` needed)

If the MCP is missing or not authed, the skill surfaces the install / auth instructions on the first run and stops.

## License

MIT. See [LICENSE](./LICENSE).
