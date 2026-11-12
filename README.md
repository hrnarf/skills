# skills

My Claude Code plugin marketplace: the skills I use, in one place. Each one is
copied from its source, read before it was added, and checked weekly for
upstream updates.

| Plugin | What it does | Source |
|---|---|---|
| `superpowers` | Brainstorm → plan → test first → build with subagents → debug from the root cause → verify before "done" | [obra/superpowers](https://github.com/obra/superpowers) |
| `frontend-design` | Distinctive frontend design instead of generic AI look | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design) |
| `obsidian` | Obsidian Markdown, Bases, JSON Canvas, Obsidian CLI, Headless sync, Defuddle, Knap | [obsidianmd/obsidian-skills](https://github.com/obsidianmd/obsidian-skills) |
| `eli5` | Explain anything at the right level for a given audience | [dreambigou/eli5](https://github.com/dreambigou/eli5) |

The exact upstream commit each copy matches is in `plugins/<name>/upstream.json`.

## Using it

**On your computer** (once per machine; the repo is private, so git must be
able to reach it, e.g. via `gh auth login`):

```
/plugin marketplace add hrnarf/skills
/plugin install superpowers@hrnarf
/plugin install frontend-design@hrnarf
/plugin install obsidian@hrnarf
/plugin install eli5@hrnarf
```

**In a project** (works in cloud and local sessions): add to that repo's
`.claude/settings.json` only the plugins it needs:

```json
{
  "extraKnownMarketplaces": {
    "hrnarf": { "source": { "source": "github", "repo": "hrnarf/skills" } }
  },
  "enabledPlugins": {
    "superpowers@hrnarf": true,
    "frontend-design@hrnarf": true
  }
}
```

## Updates

`.github/workflows/check-upstream.yml` runs every Monday (and on demand from
the Actions tab). For each plugin with an `upstream.json` it compares the
copied files with the source. If anything changed it opens a pull request
`upstream/<name>` with the list of changed files, a link to the full upstream
diff, and any scripts or hooks flagged for a closer look. Nothing changes
here until you merge.

Run the same check locally:

```bash
python3 scripts/sync_upstream.py plugins/<name>
```

## Adding a skill

**From someone else's repo**

1. Read its `SKILL.md` and every script it ships.
2. Create `plugins/<name>/upstream.json` with `repo`, `branch`, `path` (the
   plugin folder inside that repo, `""` for the root), `include` (files and
   folders to copy) and `"commit": ""`.
3. If the source has no `.claude-plugin/plugin.json`, write one yourself
   (see `plugins/eli5`).
4. Run `python3 scripts/sync_upstream.py plugins/<name>` to copy it in.
5. Add it to `.claude-plugin/marketplace.json` and the table above.
6. Check: `claude plugin validate .`

**Your own:** create `plugins/<name>/.claude-plugin/plugin.json` and
`plugins/<name>/skills/<skill>/SKILL.md`, with no `upstream.json`, then do
steps 5 and 6.

## Licenses

Each copied plugin keeps its own license file: Superpowers, Obsidian skills
and ELI5 are MIT; Frontend Design is Apache 2.0.
