# shipping-coach

**A free Claude Code subagent that catches the embarrassing stuff before it reaches `main`.**

Leftover `console.log`. Hardcoded API keys. A `.skip` you forgot to remove. A `.DS_Store` that snuck into the diff. The kind of thing you'd catch yourself if you weren't tired.

`shipping-coach` is the pre-flight check. Runs in under 90 seconds. Doesn't autofix anything — just tells you what's wrong, with file:line evidence, in a format you can act on without re-reading.

> 📖 **Writeups on the design ideas behind these agents:**
> - [The best Claude Code agents are defined by what they refuse to do](https://dev.to/peterverse180/the-best-claude-code-agents-are-defined-by-what-they-refuse-to-do-13p2)
> - [Your AI writes PR descriptions from your commit messages. That's the bug.](https://dev.to/peterverse180/your-ai-writes-pr-descriptions-from-your-commit-messages-thats-the-bug-795)
> - [Why Claude Code never runs your subagent](https://dev.to/peterverse180/why-claude-code-never-runs-your-subagent-4afm)

---

## What it catches

| Category | Examples |
|---|---|
| **Debug residue** | `console.log`, `print(`, `debugger`, `.only(`, `.skip(`, new `TODO`/`FIXME` |
| **Secret leaks** | API key shapes (`sk-`, `ghp_`, `AKIA`, `AIza`…), private keys, credentials in URLs |
| **Broken builds** | Typecheck, lint, tests — detected automatically from `package.json` / `Makefile` / etc. |
| **Tracked junk** | `.DS_Store`, `.env`, `node_modules/`, build output that snuck past `.gitignore` |
| **Migration gotchas** | Missing rollback, large-table changes without `CONCURRENTLY`, deploy-order coupling |
| **Lockfile drift** | Phantom lockfile changes, new low-trust dependencies |

Only flags things **added by your current diff**. Pre-existing junk is somebody else's problem.

## Install (30 seconds)

```bash
# user-level (works in all your projects)
mkdir -p ~/.claude/agents
curl -fsSL https://raw.githubusercontent.com/allcanprophesy-ops/claude-code-shipping-coach/main/shipping-coach.md \
  -o ~/.claude/agents/shipping-coach.md
```

Or clone and copy:

```bash
git clone https://github.com/allcanprophesy-ops/claude-code-shipping-coach.git
cp claude-code-shipping-coach/shipping-coach.md ~/.claude/agents/
```

Project-scoped install:

```bash
mkdir -p .claude/agents && cp shipping-coach.md .claude/agents/
```

## Use it

Open Claude Code in any repo with uncommitted changes and say:

> *"Run the pre-flight check on my diff."*

Or just:

> *"Anything I missed before I merge?"*

You'll get back a report like this:

```
## Pre-ship report (took 47s)

### 🛑 Blockers (2)
- Hardcoded API key at src/lib/openai.ts:14 — starts with `sk-proj-…`. Move to env.
- `console.log("DEBUG:", user)` added at src/auth/login.ts:88

### ⚠️ Worth a look (1)
- New TODO at src/billing/invoice.ts:203 — "fix tax rounding before launch"

### ✅ Passed
- Typecheck: pass
- Lint: pass (warnings: 0)
- Tests: pass (147 tests, 12.3s — ran related-only)
- Tracked junk: clean
- Migration sanity: N/A

Do not merge until blockers are resolved.
```

## Why this exists

Most "AI code review" tools want to review *everything*. They produce long reports that train you to ignore them. This agent does the opposite — narrow scope, high signal, written rules about when to refuse and when to stop.

The agent file is ~50 lines of carefully tuned prompt. Open `shipping-coach.md`, read it, edit it. It's MIT-licensed and meant to be forked.

## What's not in this freebie

This is one agent from the larger Claude Code Pro collection. Two paid packs are available:

### The Agents Pack — 6 more autonomous workers in the same style

- **pr-surgeon** — Writes PR titles + bodies + real test plans from the actual diff, not the commit messages.
- **commit-historian** — Turns a messy WIP into clean atomic commits. Refuses to rewrite `main`.
- **test-gap-hunter** — Ranks missing tests by blast radius, with evidence.
- **bug-reproducer** — Writes a failing test *before* anyone proposes a fix.
- **dependency-detective** — Audits packages for unused, redundant, and risky deps.
- **regression-sentinel** — Reads the diff with one question: "what existing behavior could this break?" Runs on `opus`.

→ **[Claude Code Pro Agents](https://peterverse180.gumroad.com/l/claude-code-pro-agents)** — $5+ PWYW.

### The Skills Pack — 7 loaded-context disciplines

Skills are different from agents. Agents do work for you (run commands, produce reports). Skills shape how Claude *reasons* when your prompt triggers them.

- **release-notes-craftsman** — Drafts release notes in 3 voices from commit history.
- **migration-safe** — Engine-specific migration safety review (Postgres, MySQL, SQLite).
- **api-contract-keeper** — Backwards-compat audit for API changes.
- **error-message-craftsman** — Improves error message quality with the what/why/what-now framework.
- **observability-eye** — Right-amount-of-logging guidance, cardinality risk surfacing.
- **changelog-keeper** — Keep-a-Changelog discipline.
- **flag-hygiene** — Feature flag taxonomy + the 30/60/90 cleanup rhythm.

→ **[Claude Code Pro Skills](https://peterverse180.gumroad.com/l/claude-code-pro-skills)** — $7+ PWYW.

## License

MIT. Fork it, ship it, modify it for your team. No attribution required.

## Feedback

Built something useful with this? Caught a sharp edge? Open an issue — it'll get read.
