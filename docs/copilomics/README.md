# Copilomics prototype tracker

Start with the **[pinned roadmap issue](https://github.com/Tiliix/agentic-genomics-labs/issues/1)**.
It links five workstreams and nineteen actionable issues with acceptance criteria,
scientific validation requirements, native parent/sub-issue relationships and blockers.

## Current setup state

- Repository issues and four milestones are live.
- The GitHub Project board is pending owner authorization for the `project` permission.
  Repository access alone does not grant it. No board or project automation is claimed yet.
- This documentation-only change does not publish application code or deploy Copilomics.
- The issue form, PR template and scoped instructions take effect after this change is merged.
- No implementation assignees, due dates or completed prototype work have been invented.

## Where to go

| Need | Location |
|---|---|
| Direction and workstreams | [Pinned roadmap](https://github.com/Tiliix/agentic-genomics-labs/issues/1) |
| Pending tasks | [Open Copilomics issues](https://github.com/Tiliix/agentic-genomics-labs/issues?q=is%3Aissue+is%3Aopen+label%3Acopilomics) |
| Release gates | [Milestones](https://github.com/Tiliix/agentic-genomics-labs/milestones) |
| Product scope and all thirteen support tiers | [Roadmap](roadmap.md) |
| Working process and definition of Done | [Tracking guide](tracking-guide.md) |
| Measured weaknesses and safeguards | [Curated evaluation baseline](evaluation-baseline.md) |
| Finding-to-work mapping | [Coverage map](finding-coverage.md) |
| Public-source identities and checksums | [Dataset manifest](evaluation-datasets.json) |

## Start here: two ready actions

1. [CP-01: reconcile and verify the actual pilot baseline](https://github.com/Tiliix/agentic-genomics-labs/issues/7).
   The evaluated prototype and its earlier fixes were local; tested is not deployed.
2. [CP-02: freeze capability support contracts and fixture expectations](https://github.com/Tiliix/agentic-genomics-labs/issues/8).
   Define what supported analysis and specific safe rejection mean before expanding behavior.

The other issues have explicit prerequisite relationships. A P0 issue may be critical
but not Ready until its prerequisites are verified. Claim a real owner when work starts.

## Daily workflow

1. Choose a Ready issue and record the actual owner and next action.
2. Work on a scoped branch/PR linked to that issue.
3. Record tests, scientific checks, UI evidence where applicable, and the tested revision.
4. Verify acceptance and applicable deployment before Done.

Workflow: **Backlog -> Ready -> In progress -> Review -> Validation -> Done**.
Blocked is a flag with a reason, dependency and next action, not a replacement status.
Until the board is authorized, keep status in the issue's latest explicit status update.
Once available, Project fields become canonical; do not maintain competing live trackers.

## Contribution templates

- [Copilomics issue form](../../.github/ISSUE_TEMPLATE/copilomics-work.yml)
- [Copilomics PR template](../../.github/PULL_REQUEST_TEMPLATE/copilomics.md)
- [Scoped Copilot tracking instructions](../../.github/instructions/copilomics-tracking.instructions.md)

After merge, select the Copilomics issue form from New issue. For a browser-created
Copilomics PR, select `template=copilomics.md` in the PR creation URL; other lab PRs
are not forced to use the Copilomics template.

Use `Refs #...` until acceptance is actually verified. Do not use an automatic
closing keyword merely because code is ready to merge.

## Evidence and privacy

This public repository contains planning text and a curated evidence summary, not the
raw fifty-conversation archive, screenshots, datasets, credentials or private data.
The full frozen archive remains with the project owner; controlled durable preservation
and reproducibility are tracked in baseline work. New evaluations must not overwrite it.

The JSON backlog is a seed snapshot, not a second task board. Its body templates retain
an explicit evidence-URL substitution token for safe re-import; live issue bodies have
real links. Edit live issues/project fields for current work rather than resetting them
from this initial snapshot.
