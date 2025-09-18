# Project Management Toolkit

This folder holds planning artefacts for AuraConnect.

- `backlog/phase1_foundations.yaml` &mdash; initial backlog items we plan to import into GitHub.

## Using the Bulk Issue Script

1. Ensure you have the [GitHub CLI](https://cli.github.com/) installed and logged in (`gh auth login`).
2. Optionally edit the YAML backlog to set the real repository name, labels, etc.
3. Run from the repo root:

```bash
python scripts/create_github_issues.py project_management/backlog/phase1_foundations.yaml --repo your-org/auraconnectai --dry-run
```

Remove `--dry-run` once you are happy with the preview. The script shells out to `gh issue create` for every entry.

### YAML Schema

```yaml
repo: owner/repo            # optional; can be overridden via --repo
default_labels:             # optional list added to every issue
  - roadmap
issues:
  - title: Human readable title
    body: |                 # markdown body (optional but recommended)
      Details...
    labels: [backend]       # optional extra labels
    assignees: [octocat]    # optional usernames
    milestone: Phase 1      # optional
```

> 📝 Install PyYAML (`pip install pyyaml`) before running the script; it is not vendored with the project.
