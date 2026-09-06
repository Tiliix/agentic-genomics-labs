# Frozen evaluation baseline

Evaluation date: 5 September 2026. This is a curated public-safe index of the
completed evaluation, not a new run or a claim that the prototype is ready.

The full transcript/screenshot bundle is retained by the project owner.
Raw conversations, screenshots, downloaded datasets, credentials and local
filesystem links are deliberately not published by this tracking setup.
Stable controlled-access archival of the full evidence is a tracked baseline task.

## Scope and accounting

- 50 conversations: 20 bundled-data and 30 additional-public-data scenarios.
- 302 replies; every conversation has at least five follow-ups.
- 302 primary reply screenshots; 442 original PNG captures including results/viewport views.
- 13 intended capabilities; 12 with completed steps. Enrichment did not complete a step.
- 19/20 bundled conversations and 0/30 public conversations completed at least one step.
- These are execution counts, not scientific task-success or hallucination rates.
- 9 source dataset entries and 14 labelled derivatives; derivatives are not independent studies.
- The preceding shared pipeline fixes passed 39 targeted regression tests.
- Application code stayed frozen during the evaluation; discovered weaknesses were not repaired.

The public cases include deliberately incompatible-input controls. An honest refusal
can be correct; an unrelated failure does not prove the intended scientific guard
was checked. The study was scripted, not an adaptive human trial or clinical validation.

## Publication and deployment boundary

At tracking setup, the published repository baseline was `80e0f0f`; the evaluated
local prototype baseline included `438b069` plus the preceding uncommitted fixes.
The original service had not been rebuilt with those fixes. A Git commit alone
does not fully describe the evaluated lab/runtime state. Baseline integration,
artifact preservation and deployment verification remain explicit pending work.

## Evidence use

Each finding below retains its original ID and concrete conversation/turn references.
Issue acceptance must use the underlying preserved records or a reproduced fixture;
this index is not a replacement for numerical validation. Source-provided context
is not automatically an independently inspected property.

## Findings

### Finding B1

**Initial natural-language settings are not transferred into executable plans**

Assessment: **high**; classification: `root_cause`.

Several text-only initial requests execute bridge defaults rather than explicit settings. The read-only _run_new implementation builds a plan from inputs and goal and does not apply the adjustment's parameter changes before execution. Empty provenance alone is not proof, but effective execution events establish concrete mismatches. Catalog-generated requests are excluded from this inference.

- Conversation 16, turn 1: Actual request says with 5 factors; params is {}; original event says Training MOFA+ (10 factors), and the answer reports 10.
- Conversation 19, turn 1: Actual request specifies 4 rounds of 8; params is {}; original event says 8 rounds x 8 knockouts and the answer reports 64 knockouts.
- Conversation 20, turn 1: Actual request specifies 100 permutations; params is {}; original event reports the 7-rung ladder with 200 permutations.

**Proposed direction:** Build a typed requested-versus-effective settings contract for new analyses, apply it before execution, and visibly acknowledge defaults or rejected settings. Preserve explicit values through planning rather than merely recognizing the dataset and capability.

### Finding B2

**Rerun acknowledgment does not guarantee that the requested parameter was applied**

Assessment: **high**; classification: `root_cause`.

Followup parameters are free-form and are not consistently normalized to bridge signatures. Catch-all keyword arguments permit unsupported aliases to be ignored, while a categorical reference change is lost before invocation. The delta message reports a change in the plan representation, not verification of the effective setting. Positive controls show this is selective, not a total failure of reruns.

- Conversation 2, turn 4: The reply says Re-ran with your change; provenance supplies low_count_threshold:20, but run_qc accepts min_count. Both summaries retain 4,678 low-count genes.
- Conversation 4, turn 3: The requested treated reference is absent from provenance, which records only alpha:0.05; the original event explicitly retains reference level untreated.
- Conversation 18, turn 3: Provenance records top_n:10; run_target_prioritization accepts top, so the five-record result cannot validate the requested change.
- Conversation 20, turn 4: Provenance records n_permutations:200; run_spatial_validation accepts n_perm. Both original events report 200 permutations.
- Conversation 3, turn 3: Positive control: alpha:0.01 is supported and reported significant genes change to 571.
- Conversation 15, turn 5: Positive control: resolution:1.0 is supported and original compute events report 13 clusters.

**Proposed direction:** Normalize documented aliases to a capability-specific schema, reject unknown parameters instead of silently swallowing them, support categorical values, and compare effective settings before declaring a successful adjustment.

### Finding B3

**A compound DE-to-enrichment task silently stops after DE**

Assessment: **high**; classification: `observed`.

The explicit multi-stage objective becomes a one-step DE plan. No evidence supports an Enrichr invocation, identifier mapping, network failure or downstream artifact handoff. Later safe uncertainty avoids fabricated pathways, but the application does not explicitly reconcile the requested stages with what actually ran.

- Conversation 5, turn 1: Actual request says first run DE, then add pathway enrichment using up to 200 significant genes. Plan goal is bulk-rnaseq-de with one step and ran contains only bulk-rnaseq-de#1.
- Conversation 5, turn 2: The reply says completion/failure/skipping of enrichment cannot be determined from JSON even though the captured execution plan shows no enrichment step.
- Conversation 5, turn 4: The agent correctly states that enrichment is unavailable, not evidence of no enrichment; no compute occurs on this or any later turn.

**Proposed direction:** Represent compound user goals explicitly, plan the required artifact-dependent stages, and return a task ledger distinguishing requested, scheduled, executed, failed and not-run stages.

### Finding B4

**Global summary truncation hides the latest run and causes stale result narration**

Assessment: **high**; classification: `root_cause`.

RunContext appends summaries in chronological order, while the narrator serializes the entire list and truncates at 4,000 characters. This drops later clusters, methods and later-run results. The clearest consequence is not merely missing detail: the multiome rerun computes 13 clusters but is narrated as the earlier 11. A larger unstructured token limit alone would not supply reliable run identity or complete comparisons.

- Conversation 15, turn 5: Original execution events say 13 joint clusters at resolution 1.0; the actual answer says the retained 2,628 nuclei formed 11 clusters.
- Conversation 15, turn 6: The requested two-run comparison is refused because the supplied JSON is truncated; the embedding method is called unspecified although the execution event says per-modality PCA, concatenated.
- Conversation 15, turn 7: The concluding current-result summary again reports 11 clusters.
- Conversation 13, turn 5: Only the first cluster entries are visible to the narrator; it says the remaining clusters cannot be annotated from what is shown.
- Conversation 16, turn 3: Four cross-omic factors are reported, but the narrator can identify only two because of truncation.

**Proposed direction:** Use run-addressable, question-specific result retrieval. Keep latest-run identity and effective parameters outside any truncatable payload; retrieve complete compact cluster/factor headers and selected detail rows as needed. Compare explicitly selected runs rather than concatenating all history.

### Finding B6

**Kang profiling fails and recovery discards the selected scientific task**

Assessment: **high**; classification: `observed`.

The original event stream shows a profiling exception before the complex single-cell plan exists. Subsequent turns do not preserve the selected Kang dataset or a useful failure record; generic clarification offers a different organism and modality. The precise HDF5/object-layout cause is not established by the captured AttributeError, so this finding does not claim one.

- Conversation 14, turn 1: After Profiling 1 input file(s), the failed event is AttributeError: 'Dataset' object has no attribute 'keys'; plan, tools and provenance are empty.
- Conversation 14, turn 4: A request for resolution 1.2 on the same Kang input receives Which dataset should I use? and a Drosophila pasilla bulk-counts suggestion.
- Conversation 14, turn 7: A request to summarize the failed runs without further analysis again receives the unrelated pasilla clarification; the screenshot confirms ran 0.

**Proposed direction:** Diagnose the supported Kang input's profiler failure with a targeted layout regression, and persist failed analysis intent, input, stage and error independently of successful results. Recovery and no-compute summaries must remain dataset- and modality-specific.

### Finding PA-F01

**Sample metadata is planned and bound as another expression matrix**

Assessment: **high**; classification: `root_cause`.

Initial plans for IDs 21-30 treat counts and named coldata as independent bulk-expression artifacts and generate two analysis steps. Their warning already recognizes the second file as coldata but does not assign it a metadata role. Frozen Router._seed_inputs preserves the input order, while PythonAdapter selects the latest accepted artifact if input_path is absent. With empty step parameters, the supplied coldata becomes the effective primary expression input. This explains the nonnumeric-count failures for SEQC and the default mammary/coldata.csv lookup for mammary cases. The correct count matrices are independently validated nonnegative integers with aligned, explicitly supplied metadata.

- Conversation 21, turn 1: Plan has two rnaseq-qc steps, profiles full_counts.csv and full_coldata.csv as bulk-expression, and warns that full_coldata.csv looks like coldata rather than counts.
- Conversation 21, turn 3: Two run_qc invocations with params={} fail: Counts must be finite nonnegative integers, without missing values. The source audit validates full_counts.csv as 21,716 by 10 integer counts.
- Conversation 25, turn 3: Two run_de attempts look for <public-data-root>/mammary/coldata.csv despite turn 1 explicitly supplying the existing virgin_coldata.csv. The selected virgin matrix is 2,000 by 4 with matching sample IDs.
- Conversation 22, turn 4: Adding QC repeats both failed DE attempts. No successful QC is recorded; the input-role problem propagates into refinement.

**Proposed direction:** Create typed primary counts and sample_metadata roles and bind both explicit paths to each intended step. A coldata warning must alter routing or hold the plan for a concrete role question, never become a second DE/QC analysis. Validate sample identifiers, uniqueness, alignment, design columns and units before dispatch.

### Finding PA-F02

**Explicit new-analysis parameters do not survive into execution**

Assessment: **high**; classification: `root_cause`.

Recorded adapter parameters are empty even when the initial prompt specifies supported controls. The frozen _run_new branch calls router.plan with new_inputs and new_goal only, then executes the returned plan. ID 34 is a direct contradiction between requested input and actionable error: dataset='simple' is supplied but the tool fails demanding it. The same gap prevents auditing UHRR/basal/virgin reference levels and condition columns. For ID 28, the requested factorial formula is never represented or rejected as a design requirement. These are ingestion/contract failures, not observed incorrect fitted statistics.

- Conversation 34, turn 1: Actual request includes dataset='simple', resolution=0.8 and top_markers=5. The file is profiled as single-cell-rna at 0.90 confidence. Provenance params={} and the error requests dataset='simple' or 'complex'.
- Conversation 22, turn 3: The pending request originally supplied metadata_path, condition_column=condition, reference_level=UHRR and alpha=0.05, but both failed DE provenance records show params={}.
- Conversation 27, turn 3: The explicit reference_level='18.5 day pregnancy' is not recorded in effective parameters. No contrast was computed, so its direction cannot be verified.
- Conversation 28, turn 1: Requested ~ cell_type + stage + cell_type:stage becomes a generic two-step bulk-rnaseq-de plan, without an explicit unsupported-design response.

**Proposed direction:** Preserve a typed requested-versus-effective parameter contract from natural-language interpretation through planning and dispatch. Validate supported fields and values; reject unsupported formulas explicitly rather than dropping them. Display the effective contrast and processing mode before approval.

### Finding PA-F03

**Opaque clarification can launch an unchanged, still-unsatisfied plan**

Assessment: **high**; classification: `root_cause`.

The UI says it needs a couple of details 'below' but supplies no concrete question or structured missing-field request. Biological corrections are classified as clarify_response and cause pending plans to execute unchanged. Frozen _resume_after_clarify unconditionally clears confirm_required and dispatches; it does not apply or validate the answer. ID 23 is particularly clear: a request for a safe readiness check 'without fitting DE' triggers two DE adapter attempts. They fail, so this is unintended attempted execution, not a completed prohibited fit.

- Conversation 21, turn 1: open_question is exactly 'I need a couple of details before running (below).' Screenshot shows no actual role-selection or missing-parameter question.
- Conversation 21, turn 3: Correcting UHRR/HBRR biology is treated as clarify_response; confirm_required is cleared and both unresolved QC steps are attempted.
- Conversation 23, turn 4: User requests a safe QC/readiness check 'without fitting DE'. Intent becomes clarify_response and two labs.lab01_rnaseq:run_de invocations occur.
- Conversation 28, turn 3: User explicitly warns that a single-condition model is not the requested factorial interaction; the response says 'that unblocks it' and attempts the unchanged generic DE plan.
- Conversation 33, turn 3: Warning that renaming HDF5 is not conversion clears confirmation on the same ambiguous HDF5 plan; no format requirement has been resolved.

**Proposed direction:** Represent pending requirements explicitly, ask one actionable question with known context, apply the answer to the appropriate field, and revalidate before execution. Explanations, corrections and requests not to run must remain read-only unless the user clearly authorizes a valid revised plan.

### Finding PA-F04

**Legacy AnnData structured-array layout crashes the HDF5 profiler**

Assessment: **high**; classification: `root_cause`.

Both PBMC68k conversations fail before analysis with AttributeError: 'Dataset' object has no attribute 'keys'. The preserved original is readable by AnnData and independently verified as 700 by 765, but its obs, var and obsm are legacy structured HDF5 Datasets rather than Groups. Frozen _refine_anndata unconditionally calls f['obsm'].keys(); the obs/var helper already supports structured arrays. This is a concrete format-compatibility exception, not successful rejection of scaled values or lack of installed single-cell dependencies.

- Conversation 31, turn 1: Execution log stops after 'Profiling 1 input file(s)' with the Dataset.keys AttributeError; plan and provenance are absent.
- Conversation 32, turn 1: The same source file independently produces the identical profiler error when the task is reference-label assessment.
- Conversation 31, turn 3: The user's explanation that negative X is scaling is handled as an unsupported capability request, not as inspected input semantics.

**Proposed direction:** Read AnnData encoding/version and accommodate structured Dataset as well as Group representations for obsm, obs and var. Return a typed, actionable unsupported-encoding result for unknown layouts. Only after successful profiling should a separate scientific preflight distinguish counts, normalized/logged values and scaled data.

### Finding PUBLIC-B-01

**A failed analysis loses its usable conversational audit trail**

Assessment: **high**; classification: `observed`.

A professional should be able to ask what was attempted, which selected data were inspected, why execution stopped and what remains missing. After precise first-turn errors, the application generally replies that it has no results and asks for data again. It does not distinguish an absent dataset from a known dataset with a failed or unsupported analysis. Raw execution provenance exists in some initial responses, but later audit questions do not retrieve it.

- Conversation 37, turn 1: The initial reply explicitly identifies the missing annotation cache and offline restriction.
- Conversation 37, turn 6: The requested source/input/tool/output audit receives only 'I don't have any results yet'.
- Conversation 44, turn 2: The user asks for the precise external-cache restriction; the answer loses the restriction already reported at turn 1.
- Conversation 46, turn 2: The missing bundle question receives no description of required bundle structure or evidence types.

**Proposed direction:** Retain a session-level ledger of selected inputs, profiles, attempted steps, failures, missing evidence and available artifacts independently of whether a result summary exists. Answer audit/readiness questions from that ledger.

### Finding PUBLIC-B-02

**Readiness and comparison requests can trigger unrequested execution attempts**

Assessment: **high**; classification: `observed`.

Several prompts explicitly ask for an explanation, checklist or recommendation, not new computation. The application treats 'add' or domain terms as scope changes and tries to run another step. No biological result was produced in these examples, but the plan/execution boundary is unreliable and obscures the user's intent.

- Conversation 36, turn 4: A recommendation and required-input inventory triggers 'Re-ran with your change' and a single-cell step lacking an input artifact.
- Conversation 39, turn 4: Comparing ACMG requirements triggers a rerun of the blocked Bayesian analysis rather than a comparison.
- Conversation 49, turn 4: A minimum-data checklist triggers a tumor-board attempt with no compatible input artifact.

**Proposed direction:** Represent explanation, readiness inspection, proposal, confirmation and execution as distinct intents. Respect explicit no-run constraints and use a complete typed input binding before any scope refinement.

### Finding B10

**Evidence-only prompting sometimes prevents useful general scientific explanation**

Assessment: **medium**; classification: `safe_unsupported`.

Abstaining from unavailable case-specific evidence is appropriate, but the result-only instruction also blocks established conceptual definitions that could be clearly labeled and sourced. The most explicit example is refusal to explain what PVS1 generally means. This is educational under-answering, not evidence fabrication.

- Conversation 9, turn 4: The answer says the JSON does not define PVS1, so its evidence type cannot be established from this result alone, instead of distinguishing its standard loss-of-function evidence meaning from an unverified assignment to this variant.
- Conversation 2, turn 3: The answer correctly refuses to guess the implementation's low-count rule; this rule should be retrieved from method metadata rather than invented.
- Conversation 12, turn 5: Positive contrast: the explanation gives a useful general account of why a negative assay is not automatically benign evidence without inventing a variant outcome.

**Proposed direction:** Separate computed case facts, documented implementation details and sourced general scientific background. Allow standard explanations with citations while keeping variant-specific evidence strength and applicability explicitly unverified.

### Finding B5

**Result, provenance, metadata and artifact evidence are separated across answer routes**

Assessment: **medium**; classification: `root_cause`.

Query answers receive summaries without provenance or artifacts, whereas explain answers receive provenance without findings. Artifact references are stripped into the separate artifact bus; the UI specially displays only a DE artifact label. Consequently, a user can see a computed-by chip or artifact string while the prose says those details are unavailable, and an explain turn can forget a skip reason already quoted. This is often safe abstention from an incomplete prompt, but poor access to evidence the application already holds.

- Conversation 1, turn 6: The reply says the statistics tool and full-result location are not recorded. The original response contains labs.lab01_rnaseq:run_de provenance and de_artifact out/rnaseq/de/2ddd603450c3d1d73ae6/de_results.csv; rendered HTML has no download anchor.
- Conversation 3, turn 6: The reply cannot identify the latest run or artifacts; original responses have different artifact labels for alpha 0.05 and 0.01.
- Conversation 6, turn 4: The explain response cannot determine the HRD skip reason, despite T2 stating low TMB and no BRCA mutation and T6 repeating the same recorded reason.
- Conversation 13, turn 6: The answer lacks source, QC definitions, marker method and artifact paths; method and path fields are not maintained in an always-available result descriptor.
- Conversation 17, turn 6: The selected T2D snapshot path is absent from the prose and no exact source artifact or date can be supplied.

**Proposed direction:** Provide a small unified evidence envelope to all read-only routes: selected input identity, verified metadata, method, effective settings, run status, tool versions, findings index and safe artifact references. Expose actual artifact downloads or explicitly label filesystem-only references. Keep absent study metadata distinct from metadata merely omitted by summarization.

### Finding B7

**Simulator recovery labels mix detected hits with a true-hit denominator**

Assessment: **medium**; classification: `observed`.

The returned pathway-recovery table can exceed 100% or report hits where there are zero simulated true hits. The bridge counts reported agent hits by pathway and divides by ground-truth true-hit counts without visibly intersecting the numerator with those true hits. These values may describe noisy hit calls, but they cannot be interpreted as true-positive recall. The agent notices and caveats this rather than presenting a clean discovery benchmark.

- Conversation 19, turn 3: Ferroptosis is reported as 2 hits found, 1 simulated true hit, 200.0% recovery; autophagy has 2 hits found and 0 true hits.
- Conversation 19, turn 5: The agent explicitly cautions that hits in pathways with no true hits should not be treated as genuine recovery.
- Conversation 19, turn 6: The final answer calls for gene-level labels and threshold/counting definitions before interpreting the values as true-positive recovery.

**Proposed direction:** Separate observed screen hits, ground-truth true positives, false positives, precision and recall. Define the eligible search space and matched-budget baseline in the output; do not use a true-hit denominator for an unfiltered hit-call numerator.

### Finding B8

**Non-DE result tables are absent and Markdown tables render as literal pipes**

Assessment: **medium**; classification: `root_cause`.

Screenshots and rendered HTML show that chat formatting handles simple emphasis and bullets but not Markdown table structure. A native expandable DE top-gene table exists; the other evaluated workflows receive no equivalent structured result view. Users must read long, partially truncated prose for cluster, factor, variant, target and decision tables.

- Conversation 1, turn 1: conversations/01/turn-01-results.png verifies the positive UI baseline: genuine metric cards and an expanded native gene/log2FC/padj table. A fixed composer at the bottom is a capture/layout feature, not evidence that this table is absent.
- Conversation 1, turn 3: conversations/01/turn-03.png shows raw pipe-delimited gene rows in the answer plus a separate expandable native Top differentially-expressed genes table.
- Conversation 6, turn 1: conversations/06/turn-01.png shows tumor-board prose, tool and provenance sections, and generic RNA-oriented suggestions; the retained rendered HTML contains no table element.
- Conversation 11, turn 2: conversations/11/turn-02.png shows the naive/calibrated classification table as literal Markdown pipes; the retained rendered HTML contains no table element.
- Conversation 13, turn 5: conversations/13/turn-05.png shows raw pipe-delimited provisional annotations; there is no native cluster-results table.
- Conversation 15, turn 5: Original rendered_html contains no table element despite a real multiome rerun.
- Conversation 16, turn 1: Original rendered_html contains no factor table; only narrative, tool/events/provenance and generic suggestions are exposed.

**Proposed direction:** Render supported Markdown safely and add capability-specific structured, accessible result views backed by actual summaries rather than prose parsing. Preserve the existing useful DE table.

### Finding PA-F05

**Failed or pending analyses cannot answer useful read-only provenance questions**

Assessment: **medium**; classification: `root_cause`.

Every final provenance request in IDs 21-35 receives 'I don't have any results yet - share data or ask for an analysis first.' This is numerically honest but discards already known selected inputs, held plans, failed invocations and errors. The frozen read-only branch returns immediately whenever successful summaries are empty, before using available provenance. Methodological questions that do not require result statistics likewise produce a dead end or a generic unsupported message.

- Conversation 22, turn 6: After four failed invocation events, a request for actual tools, parameters and selected-path audit is answered as if no analysis had been requested.
- Conversation 29, turn 2: A question about whether enrichment produced results triggers a new-data prompt despite a known pending counts/metadata plan.
- Conversation 29, turn 6: The final screenshot shows repeated suggestions to use the Drosophila pasilla demo followed by the generic no-results answer to a source-provenance request.
- Conversation 34, turn 6: The selected Paul15 input and dataset-mode failure are known, but the final provenance request is not answered.

**Proposed direction:** Separate result-dependent queries from provenance, readiness and methods explanations. Maintain a failed/pending-run ledger containing selected artifacts, requested/effective settings, unresolved requirements and attempted steps. Answer from that ledger without inventing measurements or causing compute.

### Finding PA-F06

**DE-to-enrichment requests do not retain their downstream analytical goal**

Assessment: **medium**; classification: `observed`.

IDs 29 and 30 request DE followed by pathway enrichment on the resulting artifact. Both initial plans contain only duplicate bulk-rnaseq-de steps and have goal=bulk-rnaseq-de. No pathway step or dependency is shown. Subsequent questions cannot recover the intended chain. Since prerequisites never complete, this is a planning and continuity gap; it does not demonstrate an Enrichr outage, incorrect pathway statistics or organism-mapping failure.

- Conversation 29, turn 1: The actual request explicitly says 'then add pathway enrichment from the resulting DE table'; the plan contains only two bulk-rnaseq-de steps.
- Conversation 29, turn 4: A request for mapping/background audit elicits 'Which dataset should I use?' and a pasilla demo offer, not a retained enrichment prerequisite.
- Conversation 30, turn 1: The mouse Entrez pathway request likewise has no enrichment node in its initial plan.
- Conversation 30, turn 3: Execution fails at the misbound metadata prerequisite. There is no evidence that mouse identifier mapping or the enrichment library was exercised.

**Proposed direction:** Preserve ordered multi-capability goals and their dependencies. Enrichment should require a specific successful DE artifact and record organism, namespace, gene selection, library/version and background policy. If a requested mapping/background is unsupported, disclose that exact limitation without dropping the downstream goal.

### Finding PA-F07

**Failure screens and provenance do not present a consistent auditable state**

Assessment: **medium**; classification: `observed`.

Error replies are commendably explicit about noncompletion, but failed tool invocations still receive a 'Computed by' chip, a 'Plan (what ran)' label and generic threshold/enrichment suggestions. The sidebar continues to display the bundled pasilla counts path while an external Paul15 or SEQC file is selected in the plan. Attempt provenance contains empty params, null tool_version/container and a short inputs_digest without named counts/metadata hashes. These presentation and provenance gaps are not proof of successful computation or bundled-data substitution, but they make professional audit and recovery unnecessarily difficult.

- Conversation 21, turn 1: Screenshot shows the external SEQC request and a held plan while the Data sidebar still names labs/scenario-01-pipeline-automation/data/counts.csv.
- Conversation 25, turn 3: Screenshot shows FileNotFoundError together with 'Computed by: labs.lab01_rnaseq:run_de' and suggestions to tighten a threshold or add pathways.
- Conversation 34, turn 1: Failed single-cell attempt displays the same gene/DE-oriented suggestions. Its provenance has params={}, tool_version=null, container=null and a short inputs_digest.
- Conversation 35, turn 1: A zero-step unroutable Matrix Market request still offers threshold and enrichment controls; there is no result artifact to which they could apply.

**Proposed direction:** Render plan, attempt and success as distinct states. Label failed tools 'attempted', bind visible data context to selected artifact roles, hide result-dependent actions without prerequisites, and record full per-file hashes plus effective parameters and runtime versions for every attempt.

### Finding PUBLIC-B-03

**Several advertised capabilities are bundled-data interfaces, not general public-data tools**

Assessment: **medium**; classification: `root_cause`.

Perturbation design rejects experimental MAGeCK counts because its loader supports only bundled simulated ground truth. Target discovery looks for a requested disease in the bundled cache even when an external, explicitly named asthma snapshot is selected. The frozen target bridge confirms that _cached_ids reads the lab data directory and bundled_input enforces that path. This is an honest current scope restriction, not evidence of numerical corruption; it nevertheless prevents the user's expected external-data workflow.

- Conversation 41, turn 1: The exact selected MAGeCK file is rejected with a loader message naming bundled ground_truth.csv.
- Conversation 44, turn 1: An external associations_MONDO_0004979.json snapshot is rejected: no cached MONDO_0004979, only EFO_0001360 available.
- Conversation 43, turn 3: The raw Open Targets response is profiled as generic structured data and has no route to target discovery.
- Conversation 45, turn 3: A flattened target evidence CSV defaults to bulk counts instead of being validated as a target table.

**Proposed direction:** Publish machine-readable input contracts and mark demo-only capabilities clearly. Add explicit, validated external adapters: selected-file Open Targets evidence retrieval first, and a separate guide-count QC/inference capability before feeding experimental evidence into perturbation design.

### Finding PUBLIC-B-04

**A spatial coordinate container is not sufficient to identify the measured assay**

Assessment: **medium**; classification: `observed`.

The IMC protein-intensity H5AD is labelled spatial-transcriptomics in the tumor-board route error. It is correctly prevented from becoming a tumor-board case, but the profile confuses storage/coordinates with RNA measurement semantics. A professional workflow needs assay, units, preprocessing, organism and evidence-layer identity before choosing normalization or inference.

- Conversation 49, turn 1: The selected IMC protein dataset is reported as spatial-transcriptomics in the route rejection.
- Conversation 48, turn 1: The explicit protein-intensity and schema-inspection request is not answered; it is classified as outside capability.
- Conversation 47, turn 1: The targeted 351-feature seqFISH panel request gets no assessment of panel-aware QC suitability.

**Proposed direction:** Separate container format, spatial coordinates, measurement assay and numerical representation in the input profile. Treat unknown assay semantics as an explicit readiness issue; do not infer RNA merely from H5AD or coordinates.

### Finding PUBLIC-B-05

**Generic RNA prompts interrupt non-RNA conversations**

Assessment: **medium**; classification: `observed`.

Clarifications about spatial panels and protein intensities elicit an invitation to use Drosophila bulk RNA-seq. The screenshot of conversation 47 turn 3 contains a prominent 'use the demo data' button despite the selected spatial source and explicit no-substitution instruction. No substitution actually ran, but the interaction is contextually misleading.

- Conversation 47, turn 3: A caution about unmeasured targeted genes produces the Drosophila pasilla dataset prompt and demo action.
- Conversation 47, turn 4: A spatial-context planning request repeats the bulk-RNA dataset prompt.
- Conversation 48, turn 3: A caution against normalizing protein intensities as UMI counts produces the same bulk-RNA prompt.

**Proposed direction:** Make clarification questions and suggested actions specific to the current dataset, modality, goal and execution status. Preserve explicit no-demo constraints throughout a conversation.

### Finding PUBLIC-B-06

**The visual result chrome can label a failed attempt as computed**

Assessment: **medium**; classification: `observed`.

The real target-cache failure screenshot displays 'Computed by: labs.lab05_target:run_target_prioritization' alongside ran 0 and a RuntimeError. The prose is honest, but the label conflates an attempted tool with successful computation. RNA-specific next-action chips also appear below this target-discovery failure.

- Conversation 44, turn 1: The PNG shows the cache failure, 'Computed by' badge, ran 0 and padj/pathway-enrichment action chips together.
- Conversation 36, turn 4: The reply begins 'Re-ran with your change' even though the attempted step has no bound input and ran is empty.

**Proposed direction:** Use explicit visual states: proposed, waiting for input, attempted/failed, completed and reused. Show 'Attempted tool' for failure provenance, reserve 'Computed by' for completed results, and tailor action chips to the modality and status.

### Finding B11

**Several requested biological conclusions are properly left unsupported**

Assessment: **low**; classification: `safe_unsupported`.

The captured conversations show professional boundaries worth preserving: a workflow summary does not by itself establish clinical actionability, causal regulation, an inherited diagnosis, a specific resolving experiment or therapeutic benefit. These are not defects merely because the user asks for them. This finding records positive safeguards and the remaining validation boundary.

- Conversation 8, turn 4: The answer says a primary-tumor result without normal/germline testing cannot establish inheritance.
- Conversation 10, turn 4: Posterior pathogenicity 0.3246 is explicitly distinguished from patient disease risk or diagnosis.
- Conversation 12, turn 3: The model refuses to choose a specific high-priority VUS-experiment pairing when only aggregate counts are available.
- Conversation 15, turn 2: The answer explicitly identifies PBMC substitute provenance and rejects heart-failure-specific inference.
- Conversation 17, turn 5: No safety risk is corrected to no safety liabilities listed in the cached snapshot; safety is not established.
- Conversation 20, turn 6: The model reports the returned blockade experiment but does not invent a toxicity threshold or actual experimental outcome.

**Proposed direction:** Retain these safeguards while improving access to existing evidence. Treat requests for stronger biological claims as requirements for additional validated data or analyses, not as prompts to make the answer more confident.

### Finding B9

**Followup suggestions are not capability-aware**

Assessment: **low**; classification: `observed`.

The original responses repeatedly expose the same bulk-DE-oriented suggestion chips on unrelated analyses. These suggestions were not executed in this assessment, so their downstream behavior is unknown; the observed problem is misleading and unhelpful workflow guidance.

- Conversation 13, turn 5: The screenshot displays tighten a threshold (e.g. padj<0.01), add pathway enrichment, and ask which genes are in a pathway after single-cell annotation.
- Conversation 16, turn 1: The same three suggestion strings appear after MOFA despite the user's explicit one-fit budget.
- Conversation 20, turn 4: The same DE-oriented chips appear after spatial target validation rather than gate, experiment or provenance queries.

**Proposed direction:** Generate capability- and state-specific suggestions, favoring useful read-only inspection and clearly labeling actions that trigger compute. Respect failed state and explicit no-rerun budgets.

### Finding PA-F08

**Matrix Market is honestly refused, but refusal does not validate every negative control**

Assessment: **low**; classification: `safe_unsupported`.

ID 35 explicitly produces a zero-step plan because the Matrix Market primary file is unrecognized and the sidecars have no chain to the selected single-cell goal. The response states no analysis ran, and no result is fabricated. This is a supported observation of honest refusal at the current format/routing boundary, not a failure of a numerical single-cell engine. In contrast, ID 33 stops at dataset-mode selection before H5AD validation; ID 28 fails an unintended metadata lookup before model-design assessment; ID 23 reaches a count error after metadata misbinding. Those outcomes must not be scored as successful scientific safety checks.

- Conversation 35, turn 1: Plan has zero steps, primary .mtx modality unknown and an explicit unrecognized/unroutable message; genes.tsv and barcodes.tsv are separately misclassified as bulk-expression. No adapter invocation event occurs.
- Conversation 33, turn 3: The non-AnnData source HDF5 fails 'unknown single-cell dataset'; the bridge checks mode before extension, so format-specific rejection has not been demonstrated.
- Conversation 28, turn 3: The intended unsupported-factorial-design control instead fails looking for mammary/coldata.csv.
- Conversation 23, turn 4: A generic nonnegative-integer count error occurs in the same two-artifact misrouting pattern as valid SEQC counts. It is not isolated evidence of CPM-unit validation.

**Proposed direction:** Retain fail-closed behavior and score negative controls by the specific requirement they are intended to test. Provide format-aware conversion guidance and a requirement-specific diagnostic without pretending that a generic blocker establishes biological safety.

### Finding PUBLIC-B-07

**Conservative boundaries held, but a refusal is not a complete scientific readiness assessment**

Assessment: **low**; classification: `safe_unsupported`.

Offline unannotated variants, RNA-only multiome input, a single spatial H5AD and an IMC tumor-board request did not yield fabricated results or substitute demonstrations. Those are strengths worth preserving. However, format/cache/route guards stopped execution before many biological constraints were examined. Generic 'outside capability' replies on unmatched cross-species MOFA do not prove sample-pairing validation exists.

- Conversation 36, turn 1: The RNA-only input is not silently routed to a different terminal when multiome is explicitly requested.
- Conversation 37, turn 1: Offline classification requires an annotation cache and does not fabricate ACMG criteria.
- Conversation 40, turn 1: The VCF is not silently substituted for the curated VUS cohort.
- Conversation 46, turn 1: A lone spatial H5AD cannot satisfy the complete evidence-bundle loader.
- Conversation 50, turn 1: No factor fit is performed, but the generic response does not establish that cross-species or unmatched-sample checks were applied.

**Proposed direction:** Preserve fail-closed boundaries while adding explicit, assay-specific readiness checks and explanations. Treat invalid-input safeguards and successful compatible-input analyses as separate release-gate categories.

## Scientific references

These references inform method/scope requirements; they do not certify the evaluated outputs.

- [DESeq2 official vignette](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html): Raw-count input, design formulas, contrasts and interpretation of differential-expression inference; supports assessing requests for paired designs and explicit comparisons.
- [Harvard Bioinformatics Core: single-cell pseudobulk differential expression](https://hbctraining.github.io/scRNA-seq/lessons/pseudobulk_DESeq2_scrnaseq.html): Explains why cells are not independent biological replicates, aggregation by sample, raw-count and metadata requirements; includes the Kang IFN-beta PBMC context.
- [Richards et al. 2015: ACMG/AMP sequence variant interpretation standards](https://pmc.ncbi.nlm.nih.gov/articles/PMC4544753/): Evidence-weighted interpretation for Mendelian variants, scope limits, uncertainty and the distinction between variant pathogenicity and explaining disease in an individual.
- [McCormick et al. 2020: mitochondrial DNA-specific ACMG/AMP specifications](https://pubmed.ncbi.nlm.nih.gov/32906214/): Mitochondrial interpretation requires attention to heteroplasmy, maternal inheritance and haplogroup context; generic nuclear-variant criteria are not a demonstrated validation standard for these mitochondrial negative controls.
- [MOFA2 official FAQ](https://biofam.github.io/MOFA2/faq.html): Normalization, technical variation, factor interpretation and missing-value handling. MOFA supports missingness, but unrelated species/tissues must not be fabricated into paired biological observations.

## Data provenance

The companion [dataset manifest](evaluation-datasets.json) lists source identities,
URLs, checksums and transformations without including the datasets. Paths in that
manifest are names within the retained evaluation archive, not files in this repository.
