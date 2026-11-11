@AGENTS.md

# Claude Code notes

The line above imports the canonical instructions from `AGENTS.md`. Everything there applies. This file adds only what is specific to Claude Code. Project rules live in `context.md`.

- **Plan before multi-file changes.** Use plan mode for any change that touches more than one file or any shared file, and show the plan (specification, ACs in scope, files) before editing. Write it as numbered steps, each ending in `→ verify: <check>` (`AGENTS.md` §2.4).
- **Prefer the dedicated file tools.** Use the read, search and edit tools instead of shell commands such as `cat`, `sed` or `grep` for reading and changing files.
- **Verify before you claim success.** Run the repository's checks (`make check` and the gates named in the task brief) and quote their results. If a command is still marked "planned" in `AGENTS.md` and does not exist yet, say that it could not be run.
- **Keep memory and notes free of personal data.** Do not store names, emails, phone numbers, credentials or anything about people in memory files, notes, plans or commit messages. Never copy session memory into the repository.
- **Never commit `.env` or database files** (`*.db`, `*.db-wal`, `*.db-shm`), API keys or recordings that show secrets.
- **Ask instead of guessing** when `AGENTS.md` §2.1 applies (two readings, unclear requirement) or section 5 applies. State your assumptions before you edit. Use a `blocked` completion report for section 5 only.
