# Issue tracker: GitHub plus local feature todos

Detailed, reproducible issues for this repository live as GitHub Issues. Use the `gh` CLI for those issues.

Lightweight feature todos that do not need extensive context remain in [`docs/todo.md`](../../docs/todo.md). Do not create a GitHub issue for a simple feature todo unless it grows to require detailed examples, error lines, reproduction steps, or other substantial context.

## GitHub issue conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`
- **List issues**: `gh issue list --state open`
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: explain the resolution with `gh issue comment <number> --body "..."`, then run `gh issue close <number>`

Infer the repository from the GitHub remote. File issues only in this repository.

## Pull requests as a triage surface

**PRs as a request surface: no.**
