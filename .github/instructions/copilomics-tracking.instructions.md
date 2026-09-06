---
description: Track Copilomics prototype work through evidence-linked issues and verified release gates.
applyTo: "copilomics/**,tests_copilomics/**,docs/copilomics/**"
---

# Copilomics tracking

- Use the Copilomics roadmap and tracking guide under `docs/copilomics` before
  starting a meaningful change. GitHub Issues and the linked Project are the
  source of truth for work status; chat/session notes are not the permanent tracker.
- Work against a scoped issue with acceptance criteria and an identified parent
  workstream. Record blockers and the next action rather than silently expanding
  scope. Do not invent assignments, deadlines, test results, or deployment status.
- Link the implementation PR, tested revision, validation evidence and applicable
  pilot build. A merged PR is not proof that the running service has changed.
- Preserve the frozen 50-conversation baseline. New evaluations belong in a new
  evidence bundle. Do not publish raw transcripts, screenshots, patient data or
  local filesystem paths without checking the intended access and approval.
- Distinguish completed tasks, attempted steps, safe unsupported-input refusals
  and scientific validation. Empty `ran` does not prove a specific safeguard
  was tested; nonempty `ran` does not prove scientific correctness.
- Record requested versus effective inputs/settings and the exact producing run.
  For example, a new result with 13 clusters must not be narrated as an earlier
  11-cluster run; a request for 5 factors must execute 5 or explicitly reject it.
- Keep critical regression checks and scientific applicability limits with the
  issue. Do not silently substitute a demonstration dataset, reanalyse on a
  read-only question, or weaken an invalid-input guard to make a test pass.
- Before ending a work session, update the issue with what changed, what was
  verified, what remains blocked, and the next action. If GitHub access is blocked,
  report that explicitly and do not claim the tracker or issue is complete.
