# Copilomics usable research prototype

**Planning baseline: 6 September 2026.** This is a proposed delivery roadmap, not a statement that application code has been implemented, published, deployed or scientifically qualified. Live [GitHub Issues](https://github.com/Tiliix/agentic-genomics-labs/issues) own acceptance criteria, dependencies and validation evidence. The private [Copilomics Project](https://github.com/users/Tiliix/projects/1) is live and owns workflow status, priority, journey, work type and deployment metadata. Sign in with an account granted Project access. This document deliberately contains no duplicate task-status table, deadlines or invented implementation owners.

## Product and evidence boundary

Build a dependable research workbench with conversational control: the intended data, an inspectable plan, faithful settings, immutable results and useful follow-ups. Start with a controlled internal pilot using approved public/non-sensitive data. This is not clinical decision support, a production multi-tenant platform or an autonomous replacement for a bioinformatician.

The frozen evaluation covered **50 conversations and 302 replies**: 19 of 20 bundled conversations completed at least one step; none of 30 public conversations completed a step. Thirteen capabilities were intended and twelve completed steps. These are execution facts, not full-workflow pass rates. Several public inputs should continue to be refused. The study was scripted, not an adaptive practitioner trial or independent numerical/clinical gold-standard benchmark.

[Sanitized evaluation evidence](evaluation-baseline.md) identifies findings by their original uppercase IDs and conversation/turn coordinates. Generated evidence URL anchors are lowercase: for example, finding **PA-F01** links to `#finding-pa-f01`. Links inside these repository documents are relative; live issue links use an immutable documentation revision. The public planning material must not include raw conversations, the original screenshot corpus, downloaded inputs/outputs, local machine paths, source excerpts, credentials or private data.

### Publication is not deployment

At the initial tracking setup on 6 September 2026, remote GitHub main **80e0f0f predated Copilomics**. The evaluated **application worktree branch `agents/copilomics-pipeline-error-fix`** was based at **438b069**, with unpublished prototype commits plus uncommitted original fixes verified by **39 regression tests**. The separate **documentation-only tracking branch `docs/copilomics-prototype-tracking`** started from remote main **80e0f0f**. These are historical baseline facts; current application publication and deployment evidence belongs in CP-01. Publishing tracking documents does not publish or deploy the application changes.

The original live service **was not rebuilt**. The frozen evaluation used a separate runtime; the application base commit alone does not fully identify its application and lab-adapter contents. Neither branch publication nor the 39 passing tests proves application deployment.

The first operational gate is to review/reconcile the application source and uncommitted fixes, publish approved application changes, build an identified pilot candidate and verify what actually runs. Record application source commit, tested build and deployment separately from documentation-only tracking publication. Do not claim the original service changed, and do not overwrite it without the responsible operator's explicit authorization.

## Five outcome areas

| Epic | Outcome |
|---|---|
| **EP-CORE - Trust foundations** | Typed data/method contracts, parameter fidelity, valid intent and approval, immutable runs/failures, complete evidence queries. |
| **EP-BULK - Bulk RNA-seq** | External counts and metadata through QC, explicit DE, real enrichment, inspection and handoff. |
| **EP-SC - Single-cell** | Independent raw-count and processed-data exploration with encoding/readiness checks and provisional cluster evidence. |
| **EP-TARGET - Target evidence** | Selected external snapshots, source-faithful ranking, visible evidence gaps and auditable dossiers. |
| **EP-OPS - UX/runtime** | Source/build reconciliation, intake, native results and exports, persistence, bounded jobs, release gates and practitioner qualification. |

The seed backlog contains nineteen scoped implementation/validation issues. Shared root causes consolidate the twenty-six findings; positive safeguards are retained without manufacturing defect tickets. Epics summarize outcomes; only the live child issues determine delivery progress.

## Milestone sequence and exit gates

### M0 - Trustworthy foundation

Freeze the thirteen-capability support promise and positive/negative fixture expectations. Publish and verify the baseline pilot build. Correct typed input bindings, requested/effective settings, execution approval, current-result identity, failure records and full evidence access. Repair supported legacy H5AD profiling separately from scientific readiness. Correct misleading simulation recall without widening the simulator's scope.

**Exit:** the intended matrix and metadata reach each adapter; accepted settings are applied or rejected before dispatch; no-run/no-network constraints hold; a newly computed thirteen-cluster result cannot be narrated as its earlier eleven-cluster result. Failed attempts remain auditable and repairable. Critical reproduced failures have executable regression evidence on an identified build.

### M1 - Bulk RNA-seq alpha

Deliver a real file/multi-file and approved-mounted-folder intake flow, a dataset library and a small permitted public-source importer. Provide a compact native workspace, truthful status, full result queries, working artifact downloads and a reproducible report/configuration.

Qualify external count matrices with supplied metadata: sample identity, raw-count suitability, library/sample QC, explicit supported design and contrast, full DE table and a genuine dependency-linked over-representation stage. Record identifier mapping, species, tested/background universe, gene selection, library version and actual network needs. Do not label DE alone as a completed DE-plus-enrichment request or treat unavailable enrichment as no significant pathways.

**Exit:** bundled pasilla plus at least two independent suitable public bulk sources pass the workflow. Mouse mammary subsets retain their source relationships; SEQC technical reference libraries are not described as independent human subjects. CPM and unsupported/confounded design controls reach their intended scientific checks. A user can inspect a non-preview gene, ask about provenance, change one setting, compare named runs and export without code or container-path knowledge.

### M2 - Three-journey beta

Add **standalone single-cell exploration**: a defined H5AD/Matrix Market path, raw-count versus processed inspection branches, supported QC/embedding/clustering/markers, all cluster evidence, inherited versus new labels and provisional identities. Scaled PBMC68k is a processed-readiness fixture, not a raw-count positive. Cell-level exploratory marker tests are not donor-level inference; targeted panels cannot establish absence of unmeasured genes.

Add **target evidence review**: read the selected external snapshot through versioned adapters, retain disease/target identity and source scores, explain filtering and subset limits, distinguish missing from negative evidence and export a gap-aware dossier. The selected asthma snapshot cannot fall back to a diabetes cache. Reranking twenty supplied targets is not genome-wide target discovery or clinical recommendation.

**Exit:** both added journeys qualify at least two independent suitable public sources, with correct branch/schema, five meaningful follow-ups, a requested change, comparison, export and precise refusal controls. Derivatives do not count as independent sources. Single-cell and target work can proceed in parallel after shared contracts/UI; neither depends on implementing bulk DE or multiome first. The bulk alpha remains the first release focus, not a mandatory dependency for their science adapters.

### M3 - Internal pilot

Qualify project persistence across refresh and process restart, bounded background jobs, progress, timeout/cancel, source/parameter/version-aware cache reuse and two-project isolation in the same application instance. Keep execution independent of HTTP/model lifetime. One scientific job per worker is a reasonable starting bound.

**Exit:** replay all fifty original conversations into a distinct evidence set; add at least twenty held-out supported conversations across all three journeys with at least ninety percent end-to-end task completion, using predefined eligibility and every eligible attempt in the denominator. All integrity gates must pass regardless of completion percentage. Three to five practicing bioinformaticians then complete scripted and self-chosen tasks without developer intervention, with assistance and failures recorded honestly.

Authentication, authorization, user isolation and private-data controls must be qualified **before exposure beyond the controlled pilot**. Two-project testing and four isolated evaluation servers do not establish production multi-user readiness.

## Scientific acceptance rules

- Every critical number must agree with its named producing artifact; narrative fluency is not a correctness metric.
- Approved inputs/settings, no-analysis/no-network boundaries and non-substitution have zero tolerance for violations.
- Each flagship needs two independent suitable public sources plus bundled controls. Acquire missing positive fixtures during implementation; no claim that the current corpus already satisfies this.
- Negative controls must reach the specific scientific requirement being tested. A missing metadata file does not demonstrate unsupported-design rejection; a dataset-mode error does not demonstrate H5AD validation.
- Define justified independent reference methods/tolerances before scoring: effect direction and multiple testing for DE, mapping/background/statistics for enrichment, processing/cluster invariants and exploratory interpretation for single-cell, source-score/identity fidelity for targets.
- Distinguish biological from technical replication, raw from transformed values, inherited annotations from new findings and absent evidence from negative evidence.
- Use true-positive intersections for recall; undefined denominators remain undefined. Experimental screen counts cannot become simulation ground truth.
- Test recovery, complete read-only evidence retrieval, downloaded bytes/checksums and exported-object reload/reproducibility, not just HTTP success or artifact labels.
- Require human scientific review of interpretation. A model grader, completed-step telemetry or screenshot count alone cannot qualify the release.
- Preserve safe refusals recorded in **B11, PA-F08 and PUBLIC-B-07**: no invented clinical/causal certainty, offline annotation evidence, paired modalities, complete case bundles or fabricated substitutes.

## Admission policy for all thirteen capabilities

These are intended support dispositions, **not a claim of qualification today**. Catalogue labels and contracts must match actual validated inputs.

| Capability | Prototype disposition | Admission requirements / limits |
|---|---|---|
| `rnaseq-qc` | Core alpha | External counts/metadata, raw-count readiness, explicit QC definitions and plots. |
| `bulk-rnaseq-de` | Core alpha | Documented estimable designs/contrasts, real replication, full results and faithful settings. |
| `rnaseq-pathway-enrichment` | Core alpha | Actual DE handoff, species/ID mapping, correct background/library and explicit partial/failure state; start with over-representation analysis. |
| `single-cell-annotation` | Bounded core beta | Robust raw/processed import, cluster/marker evidence and provisional labels; no donor-level inference claim from clustering. |
| `target-discovery` | Bounded core beta | Selected-source adapters, source-score provenance, missing evidence and ranking-subset boundaries. |
| `multiome-annotation` | Experimental, next wave | Paired RNA/ATAC identity, modality QC, validated external fixture and defensible run/cluster comparison. |
| `multiomics-factor-hypothesis` | Experimental, next wave | Valid multi-view manifest, actual sample correspondence, transformations/missingness and factor stability. MOFA can support missing data; do not invent cross-study pairings. |
| `variant-interpretation` | Annotated research input only initially | Separate VCF/VCF.gz readiness and consented annotation; correct reference/allele normalization, evidence provenance and domain applicability. |
| `variant-cohort-bayesian` | Experimental | Defined priors, evidence dependence and calibration evaluation; pathogenicity posterior is not patient disease risk. |
| `vus-deep-curation` | Experimental evidence review | Per-variant evidence, missing-versus-negative distinctions, strength assessment and human adjudication. |
| `multiomics-tumor-board` | Demonstration/research synthesis only | Complete case/evidence schema and expert validation; no clinical deployment claim. |
| `spatial-target-validation` | Bundle-limited demonstration | Assay-specific complete multi-evidence contract and qualified gates; one spatial H5AD is not the complete ladder. |
| `perturbation-design` | Explicit simulation demonstration | Correct precision/recall and matched-budget comparisons; experimental screen inference is a distinct future capability. |

## Advanced capability parking lot - not first-release commitments

Keep these as discovery/admission outlines, not a swarm of speculative issues. Create scoped work only after a concrete user need, suitable fixtures, method/reference criteria and support boundary are agreed.

1. **Donor-aware single-cell pseudobulk DE:** actual raw counts, donor and condition metadata, adequate biological replication, estimable design and sample-level reference validation.
2. **Variant readiness and consented annotation:** compressed/uncompressed VCF schema and reference checks, allele normalization, named annotation sources, explicit external transfer/network approval and nonclinical evidence boundaries.
3. **Experimental CRISPR QC/inference:** guide-count/library QC, replicate/design and control definitions, validated screen statistics; keep separate from simulation truth and matched-budget design demonstrations.
4. **Standalone spatial exploration:** assay-aware RNA/protein/panel intake, coordinates, neighborhoods and appropriate null models without pretending a lone object supplies a full target-validation bundle.
5. **Paired multiome and multi-view factor work:** measured sample/cell correspondence, modality QC, allowed missingness, stability and independently justified comparisons; do not fabricate pairing from cross-species/unmatched studies.
6. **Ranked enrichment and richer bulk designs:** explicitly distinct statistical methods, supported input/ranking rules and reference benchmarks; never silently substitute for the alpha's declared method.
7. **Advanced variant/VUS and tumor-board synthesis:** evidence provenance/dependence, calibration where meaningful, missingness, expert adjudication and separate governance. No clinical deployment follows from a research prototype.

Readiness inspection, complete-result querying and sourced method explanation are shared first-release essentials, not advanced deferrals. Broad FASTQ-to-results/HPC infrastructure, arbitrary generated-code execution, model upgrades as a substitute for deterministic fixes and more named agents merely for catalogue breadth are not first-release goals.

## Keeping this roadmap durable

The [tracking guide](tracking-guide.md) defines issue state and evidence rules. Change this roadmap only when outcomes, scientific support boundaries, admission gates or milestone strategy change. Put acceptance decisions, blocker details and PR/test/build evidence in the corresponding GitHub Issues; keep current workflow metadata in the live Project. If Project access is unavailable in a future session, report the blocker rather than claiming an update succeeded.
