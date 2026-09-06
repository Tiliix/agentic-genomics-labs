# Copilomics implementation tracking guide

## Source of truth and publication

The live [GitHub Issues](https://github.com/Tiliix/agentic-genomics-labs/issues) own acceptance criteria, dependency relationships and validation evidence. The private [Copilomics Project](https://github.com/users/Tiliix/projects/1) owns Status, Priority, Journey, Work type and Deployment. Sign in as Tiliix or use an account granted Project access. Creation-time metadata in issue bodies and the seed JSON is historical, not a competing live tracker. GitHub open/closed state alone does not encode the workflow.

`backlog.json` is a versioned seed and finding-coverage snapshot; `roadmap.md` is durable outcome/support policy, not a second status board. Project authorization was approved separately from repository access. If access is unavailable in a future session, record the blocker and proposed update explicitly; do not claim that a Project field changed or reset live work from the initial seed.

Five epic containers, nineteen actionable child issues and the roadmap record are linked to the Project. Preserve **EP-CORE / EP-BULK / EP-SC / EP-TARGET / EP-OPS** and **CP-01 ... CP-19** in titles. Native parent/sub-issue and blocked-by relationships are configured. Preserve dependency links independently of parentage.

No deadlines or implementation assignees have been fabricated. Start from Ready next, claim a real owner when work begins, and use Inbox to triage newly added items.

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

Configured custom metadata is Status, Priority, Journey, Work type and Deployment. Built-in fields retain title, assignees, labels, milestone, repository and linked-PR information where available. Native issue relationships carry parentage and prerequisites; external blocker reasons and owners belong on the issue. Stable issue keys remain in titles/body links; GitHub numbers are publication identifiers, not replacement planning keys.

**Canonical metadata:** do not create duplicate priority, journey or status labels. Use `copilomics` plus the relevant issue-type label: `bug`, `enhancement`, `documentation`, `type:validation`, `type:epic` or `type:roadmap`. The `blocked` label may flag an external impediment; `needs-scientific-review` may flag an outstanding scientific review, with details on the issue. Neither replaces Status or native dependency links. Map seed type to Project Work type during intake.

### Views and automation

- **Delivery board:** implementation cards, grouped by the six Status columns; excludes structural epic and roadmap records.
- **Ready next:** the starting queue, initially CP-01 and CP-02.
- **Integrity blockers:** P0 implementation work; critical does not necessarily mean ready.
- **Bulk alpha / Single-cell / Target evidence:** journey-specific views with parent context.
- **Workstreams:** the five epic containers and their child progress.
- **Inbox:** items without Priority. Set Priority, Journey, Work type and Deployment and check prerequisites before moving to Ready.

Built-in intake places new Project items in Backlog, and sub-issues are automatically added. Automatic issue closure, Item closed status changes, PR-linked status changes and PR-merged status changes were removed. After verified acceptance and applicable deployment, explicitly set Done and close the issue so both Project status and native issue roll-ups agree. No PR event performs those steps for you.

After the tracking PR is merged, the Copilomics issue form's `projects: ["Tiliix/1"]` setting adds submissions when the creator has Project write access. Check Inbox after creating work; no token-bearing Actions workflow is required.

### Evidence publication safety

Seed issue bodies retain the explicit **`{{EVIDENCE_URL}}`** import token. Resolve it to the published sanitized index before creating an issue; repository Markdown uses relative links instead. Generated finding URL anchors must be **lowercase**, for example `#finding-pa-f01`, while visible finding IDs retain their original uppercase form, for example **PA-F01**. Verify generated anchors against the published index. Conversation/turn coordinates refer to retained evaluation records without exposing the raw corpus.

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

**Blocked is not a seventh status.** Keep the current workflow status, use native blocked-by relationships for issue prerequisites or the `blocked` label for an external impediment, and record:

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
