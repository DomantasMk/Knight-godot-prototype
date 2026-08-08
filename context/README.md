# Project context notes

Short, durable notes on **why** this project is shaped the way it is. Checked into git
so they version alongside the code they describe and survive any single conversation.

The index of these notes lives in `CLAUDE.md` under "Project context". That index is
loaded into every session; these files are read on demand. So the index line carries the
gist, and the file carries the detail you only need once you are actually working there.

## What belongs here

Only what the code cannot say on its own:

- **Why** a shape was chosen, and what was rejected.
- **Invariants** — what silently breaks if you change a thing.
- **Intent** — what a scene or system is *for* (demo? shipping? throwaway?).
- **Cross-cutting rules** that have no single file to live in.

## What does not

- Anything a doc comment in the file already says. This codebase comments its `why`
  well — do not mirror it here. Link to the file instead.
- API listings, node trees, function signatures. Those go stale; read the code.
- Task state, TODOs, "next steps". Those belong in issues or the conversation.
- Anything derivable in one `grep`.

## Template

```markdown
# <Topic>

<One sentence: what this is.>

**Decisions**
- <choice> — <why>, instead of <rejected alternative>.

**Gotchas**
- <invariant> — <what breaks if violated>.

_Files: path, path_
```

Drop a section when it has nothing to say. `**Gotchas**` is usually the most valuable one.

## Rules

- **One topic per file**, kebab-case name. If a note needs sub-headings, it is two notes.
- **Hard cap ~25 lines.** Over the cap means it is documentation, not a note — cut it or
  split it. The cap is the point: it forces you to keep only the load-bearing sentences.
- **Rewrite, don't append.** When the code changes, the old note is *wrong*, not history.
  Edit it in place, or delete it. Stale context is worse than none.
- **Every note earns its index line.** Adding a note means adding one line to `CLAUDE.md`;
  deleting one means removing that line. They stay in sync or the system rots.
- **Cap the *count*, not just the size.** The index is the part loaded into every session, and
  it grows one row per note. At this project's scope, **~8 notes is the ceiling**. Wanting a
  ninth is a signal to merge two existing ones, not to extend the table. If the codebase grows
  an order of magnitude, raise the ceiling deliberately — never by drift.

## When to update

- After building or materially changing a system → update the note in the same commit.
- When the user explains a preference or a reason → capture the reason, not the instruction.
- When you discover a gotcha the hard way → write it down so it is paid for once.

Do **not** write a note for routine edits that change no decision.
