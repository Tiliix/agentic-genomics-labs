# Copilomics implementation tracking guide

## Source of truth and publication

The live [GitHub Issues](https://github.com/Tiliix/agentic-genomics-labs/issues) own acceptance criteria, dependency relationships and validation evidence. GitHub Project fields become canonical for workflow status and other project metadata **when a board is available**. Until then, record an explicit `Status: Backlog/Ready/In progress/Review/Validation/Done` and any blocked details in the live issue body or latest status comment. GitHub open/closed state alone does not encode this workflow. When a board becomes available, reconcile those records into its fields and avoid maintaining competing live status records.

`backlog.json` is a versioned seed and finding-coverage snapshot; `roadmap.md` is durable outcome/support policy, not a second status board. Repository authorization does not imply project authorization. If project scope requires unavailable user approval, publishing repository issues and documentation may proceed under existing permission while board creation remains explicitly blocked. Do not claim a board, configured fields or automation exists until verified. Do not bypass the approval requirement.

Publish five epic containers and nineteen actionable child issues. Preserve **EP-CORE / EP-BULK / EP-SC / EP-TARGET / EP-OPS** and **CP-01 ... CP-19** in published titles. Resolve stable keys to actual GitHub issue links after creation. Use GitHub parent/sub-issue relationships where available; otherwise retain explicit epic and child links. Preserve dependency links independently of parentage.

No deadlines or implementation assignees have been fabricated. Field creation, GitHub authentication and publication are handled separately from preparing these files.

### Seed schema

`schema_version` is `1.0`.

- Top-level collections: `milestones`, `epics`, `issues`, `finding_coverage`; `baseline`, `schema` and `publication_policy` document provenance and safe publishing.
- Baseline provenance distinguishes `evaluated_app_branch` / `evaluated_app_branch_base` / `evaluated_app_state` from `tracking_docs_branch` / `tracking_docs_branch_base` / `tracking_docs_state`. The evaluated application and documentation-only tracking worktrees are not interchangeable.
- **Issue:** `key`, `title`, `body` (Markdown), `epic_key`, `priority`, `journey`, `type`, `milestone`, `depends_on` (CP-key array), `initial_status`, `basis`, `finding_ids`.
- **Epic:** `key`, `title`, `body`, `priority`, `journey`, `milestone`, `issue_keys`. Epic milestone is the final outcome horizon; children may close in earlier milestones. Epics are structural containers, not extra implementation tickets.
- **Priority:** P0 / P1 / P2. P0 is a trust/release blocker, not necessarily the next task chronologically.
- **Journey:** Shared / Bulk RNA-seq / Single-cell / Target evidence / Advanced.
- **Type:** Bug / Feature / Validation / Documentation. `basis` independently distinguishes observed defects, product requirements, mixed scope, baseline operational gap and validation requirements; a feature label must not imply the feature was tested and failed.
- **Milestone:** exactly `M0 - Trustworthy foundation`, `M1 - Bulk RNA-seq alpha`, `M2 - Three-journey beta`, `M3 - Internal pilot`.
- **Initial status:** Ready if `depends_on` is empty; otherwise Backlog. CP-01 and CP-02 are the two initial Ready issues. Thereafter status changes require evidence, not a repeated import of this seed.
- **Finding coverage:** one record per original finding ID, with `disposition`, `issue_keys`, `note`. There are 26 records: 23 mapped action findings and 3 non-action safeguards. B10 is a bounded explanatory improvement, not a fabrication defect. B11, PA-F08 and PUBLIC-B-07 preserve correct refusal behavior; future extensions do not turn honest unsupported behavior into a retroactive bug.
- Every child issue body contains scope, acceptance checkboxes and validation evidence requirements. `finding_ids` records direct assignments; explanatory references to related findings need not repeat those assignments.

Suggested project fields, to configure only when board access is authorized: Status, Priority, Journey, Type, Epic, Milestone, Blocked, Blocked reason, Blocked owner and links to validation/deployment evidence. Stable issue keys belong in titles/body links; GitHub numbers are publication identifiers, not replacement planning keys. Use built-in fields where available rather than duplicating them. These are workflow requirements and recommendations, not a claim that fields or transition automation have already been installed.

**Canonical metadata:** use Project fields for Priority, Journey and Status once authorized. Do not create duplicate priority, journey or status labels. Repository labels are limited to `copilomics` plus the relevant issue type: `bug`, `enhancement`, `documentation`, `type:validation` or `type:epic`. Map seed types Bug -> `bug`, Feature -> `enhancement`, Documentation -> `documentation`, Validation -> `type:validation`; epic containers use `type:epic`. Until board access is available, retain priority/journey metadata alongside explicit status in the issue, then reconcile into canonical fields. Use native sub-issue and blocked-by relationships where supported; retain stable-key links for traceability. Configurable project views and filters are optional presentation after authorization, not proof that the board has already been created.

### Evidence publication safety

Replace **`evaluation-baseline.md`** with the actual published **sanitized evidence index URL** before publishing any body or roadmap. Generated finding URL anchors must be **lowercase**, for example `#finding-pa-f01`, while visible finding IDs retain their original uppercase form, for example **PA-F01**. Preserve the token until substitution and verify every generated lowercase anchor against the published index. Conversation/turn coordinates refer to internal evaluation records without exposing them; the public index should provide compact sanitized summaries and traceability.

Publish planning text, aggregate counts, finding IDs/coordinates and approved source/test/build/deployment references only. Do **not** upload full raw conversations, screenshots, downloaded inputs/results, raw private source excerpts, machine paths, credentials or private customer/participant data. Do not attach a file merely because it was used during evaluation. The schema's `finding_coverage` notes intentionally consolidate root-cause duplicates instead of opening one ticket per finding.

## Status workflow

| Status | Entry condition | Exit condition |
|---|---|---|
| **Backlog** | Accepted scope, but prerequisites/evidence or refinement are outstanding. | Prerequisites have verified outcomes and acceptance/validation plan is executable. |
| **Ready** | No unmet hard prerequisite, clear bounded scope, acceptance criteria and validation path. Assignment need not be invented. | Work begins and a real implementation/validation owner is recorded. |
| **In progress** | Implementation or planned validation is actively under way, with linked work. | A reviewable PR or validation/documentation deliverable is ready; blockers remain visible. |
| **Review** | Code/config/docs or validation design/results await appropriate technical/scientific review. | Review passes and the identified artifact/build is available for acceptance validation. Changes requested return to In progress. |
| **Validation** | Acceptance tests, scientific checks and applicable runtime/deployment checks are being performed on a named candidate. | All criteria have linked evidence and required reviewers accept the result; failures return to In progress or remain blocked. |
| **Done** | All issue acceptance criteria are verified, evidence linked and deployment status stated truthfully. | Reopen if a regression invalidates acceptance, or open a linked newly scoped follow-up. |

**Blocked is a flag, not a seventh status.** Keep the current workflow status, set Blocked, and record:

- the exact unmet dependency or external decision;
- the concrete condition needed to unblock;
- a linked dependency/incident where possible;
- a real **blocker-resolution owner**, or explicitly **unassigned - assignment needed**;
- the next action/update, without inventing a due date.

Distinguish blocker-resolution owner from implementation assignee. A parent epic does not unblock a child; verified prerequisite acceptance does. If a listed dependency proves unnecessary, document why and update the live issue relationship rather than bypassing it silently. Epic progress rolls up children; an epic may be Done only when its intended outcome and all required child acceptance evidence are satisfied.

## PR merge is not deployment

Keep four provenance facts distinct: remote main **80e0f0f** predates Copilomics; the evaluated **application worktree branch `agents/copilomics-pipeline-error-fix`**, based at **438b069**, contains unpublished prototype commits and uncommitted original fixes with **39 passing regression tests**; the separate **documentation-only tracking branch `docs/copilomics-prototype-tracking`** is based on remote main **80e0f0f**; the **original service was not rebuilt**. Publishing a tracking-documentation PR does not publish the application changes, satisfy CP-01 or establish a deployment. The separate frozen evaluation runtime is not evidence that the original service runs those fixes.

Record each link explicitly:

**Issue -> PR -> source commit -> test record -> build/environment identity -> deployed runtime -> acceptance evidence**

- A merged PR may move Review to Validation, **never automatically to Done**.
- Do not configure PR-merge automation to close issues or mark them Done.
- Use non-closing PR references such as **"Refs CP-04 / #number"** or **"Implements part of #number"**. Avoid GitHub auto-closing keywords (`Fixes`, `Closes`, `Resolves`) until the issue has actually passed acceptance; preferably close manually after the validation record.
- Keep deployment applicability explicit: **not deployed**, **deployed to named pilot build**, **existing live service unchanged**, or **not applicable** with rationale for a documentation/contract-only task.
- For user-visible runtime fixes, validate on the intended identified candidate environment before Done; release/pilot claims additionally require the actual deployed build. A code-only unit test cannot prove deployment.
- Deploying to an existing live service needs the responsible operator's authorization. Lack of authorization is a blocker, not permission to overwrite it.
- The release gate cannot pass with only a merged commit/build if the tested pilot service is running something else.

## Evidence required to close a child issue

Use a concise verification comment:

1. **Scope and result:** which acceptance checkboxes passed; what remains excluded.
2. **Change links:** issue/PR/commit, configuration changes and any migration.
3. **Test provenance:** command, fixture/source IDs, content hashes where useful, expected/actual outcomes, reference method/tolerance and tool/runtime versions.
4. **Build/model identity:** actual build or immutable environment identifier; model/provider/version and material inference configuration where they affect the evaluated behavior. Record unavailable version detail as unknown, not inferred.
5. **Scientific review:** method/design rationale, replication, preprocessing, missingness, source attribution and interpretation review where applicable. A model grader alone is insufficient.
6. **Runtime evidence:** observed selected run/artifact consistency, working download/hash, restart/cancel/isolation or deployment smoke results relevant to the issue.
7. **Decision:** verified Done, remaining blocker or a precise linked follow-up; name actual reviewers only after review occurred.

Evidence must be portable and sanitized. A relative artifact name or screenshot without a verified file does not prove export; `ran`, HTTP success and reply fluency do not prove scientific task success. Safe refusal must identify the real missing scientific requirement. Never mark an unrelated early crash as a passing biological safeguard.

## Code, model and science changes must be documented

Each change records what changed, why, affected support contracts, reproducibility implications and required regression evidence.

- **Code/config/runtime changes:** source/PR/build identity, adapter and dependency versions, parameter/default/schema changes, storage migrations and deployment/rollback implications.
- **Model/prompt/tool-schema changes:** named version/configuration where available, routing/intent/evidence behavior affected, comparable scenario results and nondeterminism limits. A model switch is not a substitute for repairing deterministic contracts.
- **Scientific changes:** accepted input/preprocessing/design, statistical method, contrasts, filtering/universe, mapping/background/library versions, missing evidence, numeric tolerances and support-tier implications. Document causal/clinical limits and obtain appropriate human review.
- Update user-facing compatibility/method/recovery documentation when behavior changes. Update the roadmap only for a durable support or scope decision, not every merged PR.

## Release and pilot decision

CP-18 owns the release qualification record; CP-19 owns practitioner outcomes and the pilot go/no-go decision. Do not average away a trust failure.

- Replay all fifty baseline conversations without overwriting them, preserving the original safe-refusal cases.
- Add at least twenty held-out eligible conversations across all three supported journeys and count every eligible attempt; target at least ninety percent full-task completion.
- Require two independent suitable public sources per journey, justified reference checks, five meaningful follow-ups, comparison and export; derivatives do not add independent source count.
- All zero-tolerance binding/parameter/approval/current-result/no-substitution/metric gates must pass.
- Require actual persistence, cancel and same-instance two-project tests; four isolated evaluation processes are not multi-user proof.
- Have three to five practicing bioinformaticians perform scripted and self-chosen tasks, recording assistance and failures without developer rescue being scored as unassisted success.
- Publish separate scores for intake, completed science, read-only usefulness, specific refusal, numeric consistency and export, with scientific/support limitations visible.

Advanced ideas stay in the roadmap parking lot until admitted deliberately. Authentication/private-data qualification precedes broader exposure; no internal pilot result grants clinical or production multi-tenant status.
