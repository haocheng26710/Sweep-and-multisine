# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`.
- **Read an issue**: `gh issue view <number> --comments`, including labels.
- **List issues**: use `gh issue list` with appropriate label/state filters and JSON output.
- **Comment on an issue**: `gh issue comment <number> --body "..."`.
- **Apply/remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- **Close**: `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` resolves it automatically inside this clone.

When a skill says to publish to the issue tracker, create a GitHub issue. When it says to fetch a ticket, use `gh issue view <number> --comments`.
