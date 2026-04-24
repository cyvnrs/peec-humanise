---
name: peec-humanise
description: Rewrites Peec AI tracked prompts from stiff SEO-flavoured copy into how real people actually type searches — lowercase, short, occasional typos, no corporate filler — grounded in verbatim language harvested from Reddit, HN, Quora, and X for each tracked topic. Presents rewrites in an interactive terminal picker (arrow keys to scroll, y to accept, n to reject, enter on "submit" to push) and explains that Peec's prompt model requires delete-then-create, so accepted rewrites replace the old prompt IDs and their history. Trigger when the user types `/peec-humanise`, asks to "humanise" or "de-SEO" Peec prompts, or says tracked prompts read like marketing copy and want them rewritten to match real user search behaviour.
---

# peec-humanise

Turn prompts like

> Which platform offers the best AI safety training for busy professionals seeking certification?

into prompts like

> best ai safety training course
> ai safety cert worth it reddit
> anyone done ai safety training

Real humans type short, lowercase, misspelled, badly-punctuated fragments. Peec's daily prompt runs are only useful if they mirror that reality, otherwise the retrieval surface and brand mentions reflect a world that doesn't exist.

## When to run

Invoke when the user:
- types `/peec-humanise`
- asks to rewrite, humanise, de-SEO, or "make real" their Peec prompts
- complains that tracked prompts read like marketing copy or a product-manager wrote them
- mentions grounding prompts in how people actually search

## Prerequisites

- Peec AI MCP tools visible (`mcp__peec-ai__list_projects`, `mcp__peec-ai__list_prompts`, etc.)
- `WebSearch` tool available — used to harvest real user phrasing

## Important: Peec's prompt action model

**Peec treats prompt text as immutable.** There is no in-place text edit for a prompt. A rewrite is always `delete_prompt(old_id)` followed by `create_prompt(new_text, topic_id, tag_ids)`. Consequences the user must understand before submitting:

- The old `prompt_id` and all its historical daily runs are destroyed.
- Brand-report, URL-report, and chat history tied to that prompt_id become orphaned.
- The new prompt starts collecting metrics from day one.
- Topic and tag assignments are preserved by the skill, but only if we carry them forward manually in the `create_prompts` payload.

The skill surfaces this note in the picker's footer. Do not hide it.

## Workflow

### Step 1 — MCP preflight

Silently attempt `mcp__peec-ai__list_projects`. Do not announce.

- **Tools absent** (`mcp__peec-ai__*` not in tool list): MCP not installed. Tell user to add it (e.g. `claude mcp add peec-ai <url>` or via `/config`) and re-run. Stop.
- **Auth error on call**: MCP installed but not authed. Return the auth URL from the error verbatim and stop.
- **Success**: proceed silently.

### Step 2 — pick a project

- 0 active projects: ask whether to retry with `include_inactive=true`.
- 1 active project: use it, do not ask.
- 2+: ask which one in one short sentence. Use names, not IDs.

### Step 3 — fetch prompts grouped by topic

In a single parallel batch:
- `mcp__peec-ai__list_prompts` (limit 1000)
- `mcp__peec-ai__list_topics`
- `mcp__peec-ai__list_tags`

Group prompts by `topic_id`. Topic names are the harvest seeds. **Do not ask the user to pick a brand** — the rewrite is topic-grounded, not brand-grounded. Brand-specific tone is a secondary signal picked up from the same topic-level search, not a separate step.

If there are more than 40 prompts total, ask whether to humanise all of them, a specific topic name, or a specific tag name. 20-40 prompt batches are the sweet spot.

### Step 4 — harvest real user language per topic

For each topic in scope, run WebSearch queries in parallel. Goal: 3-6 verbatim snippets per topic of how actual humans phrase things.

Seed patterns (replace `{topic}` with the topic name; prefer the shortest natural form):

```
site:reddit.com {topic}
site:reddit.com best {topic}
site:reddit.com {topic} worth it
site:reddit.com {topic} vs
site:news.ycombinator.com {topic}
site:quora.com {topic}
{topic} reddit
```

Cap total searches at about 20 — if there are 10 topics, pick the 2 best seed patterns per topic rather than 7. Skip 4chan (no stable search, low signal for SaaS).

From the returned snippets, build a **per-topic tone dictionary**:
- verbs humans use (`tried`, `switched to`, `dropped`, `worth it`, `anyone`)
- negations (`not worth`, `dont bother`, `meh`)
- comparative shorthand (`x vs y`, `alternative to x`)
- casing/punctuation habits (almost always lowercase, rarely a question mark)
- nicknames or shorthands (e.g. `biz` for business, `seo` as always lowercase)

Store this dictionary in memory per topic — it biases the rewrite in Step 5.

### Step 5 — apply the rules per prompt

For each prompt, rewrite using the rules in the **Rules** section, biased toward the harvested per-topic tone. Produce 1 primary rewrite (`after`) and 1 alternate (`alt`). If a prompt is already short and casual, mark it `UNCHANGED`.

Carry forward from each original prompt: `prompt_id`, `text`, `topic_id`, `tag_ids` (if present in the `list_prompts` response).

### Step 6 — write the rewrite bundle to disk

Create `/tmp/peec-humanise-<project_id>-<timestamp>.json` with this shape:

```json
{
  "project_id": "...",
  "items": [
    {
      "prompt_id": "...",
      "topic_id": "...",
      "topic_name": "...",
      "tag_ids": ["..."],
      "before": "Which platform offers the best AI safety training for busy professionals seeking certification?",
      "after": "best ai safety training course",
      "alt": "ai safety cert worth it reddit"
    }
  ]
}
```

Skip items where `after == "UNCHANGED"`.

### Step 8 — push accepted rewrites to Peec

Read `/tmp/peec-humanise-*.selected.json`. For each accepted item, the payload is:

```json
{
  "old_prompt_id": "...",
  "new_text": "...",
  "topic_id": "...",
  "tag_ids": ["..."]
}
```

Execute as follows:

1. Collect all `old_prompt_id`s into one list and call `mcp__peec-ai__delete_prompts` (batch).
2. Collect all new prompt payloads into one list and call `mcp__peec-ai__create_prompts` (batch) with each entry carrying `text`, `topic_id`, `tag_ids`.

Prefer the batch variants (`delete_prompts`, `create_prompts`). If only the singular variants exist, call them in parallel batches of 10.

**Do NOT use `mcp__peec-ai__update_prompt`.** Per Peec's action model, update is for metadata like tag or topic reassignment, not text changes. Text changes go through delete+create.

### Step 9 — report

Short summary to the user:

```
rewrote X prompts.
deleted: [old_prompt_id_1, old_prompt_id_2, ...]
created: [new_prompt_id_1, new_prompt_id_2, ...]
topic-level tone dictionaries used: [topic_name_1, topic_name_2, ...]
```

Link to the project in app.peec.ai.

## Rules

The rewrite rules. Shorter and uglier wins when choosing between candidates.

### 1. Strip superficial adjectives

Ban-list (delete on sight):

```
busy, modern, leading, world-class, cutting-edge, innovative, robust,
seamless, comprehensive, best-in-class, state-of-the-art, top-rated,
growing, forward-thinking, agile, enterprise-grade, next-gen, premium,
high-performance, scalable, dynamic
```

These words almost never appear in real searches. Delete, don't replace.

### 2. Strip superficial verbs/nouns

Ban-list:

```
seeking, leveraging, utilize, utilise, streamline, optimize, optimise,
navigate, facilitate, empower, unlock, elevate, enhance, drive,
harness, maximize, maximise, solution, offering, platform (when generic),
professional, stakeholder, ecosystem, journey, experience (when generic)
```

Replace with what a human would type, or drop. `seeking certification` → `cert`. `leveraging ML` → `ml`. `streamline operations` → delete.

### 3. Strip filler question framings

```
"which platform offers the best X"        -> "best X"
"what is the best way to X"               -> "how to X"
"what are the top-rated X for Y"          -> "best X for Y"
"how can I leverage X to Y"               -> "can X do Y"
"what are some recommendations for X"     -> "x recommendations"
"could you suggest X for Y"               -> "x for y"
"I am looking for X that does Y"          -> "x that does y"
```

### 4. Lowercase everything

Exception: brand names typed with caps (e.g. `iPhone`, `GitHub`). Even then, ~30% of real users lowercase them. Lowercase is always safe.

### 5. Drop articles and punctuation

- `the`, `a`, `an`: delete unless meaning breaks.
- `?`: drop about 70% of the time.
- apostrophes: drop (`dont`, `cant`, `wont`, `ur`, `youre`).
- commas: delete.
- trailing periods: delete.

### 6. Typos — sparingly

Apply to about 1 in 4 rewrites, max one typo per prompt:

```
the       -> teh
your      -> ur | yr
you       -> u
recommend -> recomend
definitely-> definately
separate  -> seperate
necessary -> necesary
really    -> realy
because   -> bcs | bc
with      -> w
without   -> w/o
versus    -> vs
```

Don't invent LLM-looking typos. Use these or obvious keyboard-adjacent slips.

### 7. Real human shorthand

```
vs, w, w/, w/o, idk, tbh, imo, rec, recs, pls, plz, biz,
worth it, any good, anyone tried, is X legit, X alternative,
best X reddit, X vs Y reddit
```

Appending `reddit` to ~20% of prompts is realistic — humans know Google surfaces forum content that way.

### 8. Length target

- 2-6 words for most prompts.
- 7-10 words when comparing or asking worth-it.
- Never more than 12.

A 20-word original should rewrite to under 8.

### 9. Preserve intent

The rewrite must retrieve the same class of answer. Don't narrow or broaden the topic.

### 10. Match harvested per-topic tone

If the Reddit snippets for this topic consistently use a shorthand (`biz`, `ops`, `ml`), weave it into 1-2 rewrites per topic. If no clear shorthand, don't invent one.

## Worked examples

**Input**: `Which platform offers the best AI safety training for busy professionals seeking certification?`
**Harvest**: "anyone done the ai safety cert", "is coursera ai safety worth it", "best ai safety course reddit"
**after**: `best ai safety training course`
**alt**: `ai safety cert worth it reddit`

---

**Input**: `What are the top-rated CRM solutions for growing small businesses in 2025?`
**after**: `best crm for small biz`
**alt**: `crm for small business reddit`

---

**Input**: `How can I leverage machine learning to optimize my marketing campaigns?`
**after**: `ml for marketing does it work`
**alt**: `does ml actually help with ads`

---

**Input**: `Could you recommend robust, enterprise-grade observability platforms for modern DevOps teams?`
**after**: `best observability tool for devops`
**alt**: `datadog vs grafana reddit` (only if those brand names appeared in the harvest)

---

**Input**: `best crm reddit`
**after**: `UNCHANGED`

## Important behaviours

- **No emojis.** Not in output, not in rewrites, not in the TUI.
- **Never narrate intermediate MCP or WebSearch calls.** The user sees the picker, not the plumbing. Matches Peec MCP's own "never narrate" rule.
- **Never invent prompt IDs, topic IDs, or Reddit threads.** Only what `list_*` and `WebSearch` returned.
- **Never auto-push.** Accepted rewrites only go through delete+create after the user hits submit in the picker.
- **Cache `list_*` results** within the session.
- **Re-runs in same session**: skip preflight and project selection if already done. Go straight to Step 3 (or 4 if prompt set is unchanged).
- **If curses fails**: fall back to numbered print + stdin row list, explain to user.

## One-liner flow

```
preflight -> list_projects -> pick project
          -> list_prompts + list_topics + list_tags (parallel)
          -> group prompts by topic
          -> WebSearch per topic (parallel)
          -> per-topic tone dictionary
          -> apply rules -> before/after/alt bundle -> /tmp/*.json
          -> curses picker (user decides)
          -> delete_prompts + create_prompts (batch, preserving topic_id/tag_ids)
          -> report
```
