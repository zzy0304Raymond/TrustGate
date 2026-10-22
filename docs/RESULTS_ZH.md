# Results and evidence

## Research questions

| Question | Main finding | Evidence |
|---|---|---|
| RQ1: Security | Output attack success is 10/90 without defense and 0/89 with TrustGate. Metadata attacks never succeed in any configuration, so they do not demonstrate an added security benefit. | [Main tables and six figures](../results/formal/analysis/README_ZH.md) |
| RQ2: Task utility and overhead | Benign completion is 46/60 without defense and 44/60 with TrustGate. Matched benign trials average about 9.04 additional seconds, 0.15 additional model calls, and 2,964 additional tokens. | [Platform and overhead analysis](../results/formal/overhead/README_ZH.md) |
| RQ2: False positives | 1/24 distinct benign descriptions is quarantined. Authorization rejects 0/31 executable reference calls; metadata quarantine affects 1/31 reference calls. | [False-positive counts and denominators](../results/formal/false_positives/README_ZH.md) |
| RQ3: Modules and failure mechanisms | Removing authorization produces 6/90 output attack successes. A recorded trace directly shows authorization denying an attack call. Independent gains from the other two modules remain unconfirmed. | [Ablations and mechanism evidence](../results/formal/mechanism_evidence/README_ZH.md) |

Attack fractions use valid trials. TrustGate has one additional timeout, which is not credited as successful defense. Benign completion uses the frozen native evaluator and does not guarantee factual correctness. The task-clustered interval for the incremental authorization effect includes zero. Direct mechanism traces and aggregate statistics address different levels of evidence.

## Datasets reported separately

| Dataset | Scope and purpose |
|---|---|
| [Original formal study](../results/formal/README_ZH.md) | 20 tasks, 60 attacks, seven configurations, three repetitions: 1,680 trials supporting the main conclusions |
| [52 selected reviews](../results/formal/review/README_ZH.md) | Targeted checks of failures, false positives, grading, and attack paths; not a sample for re-estimating overall success rates |
| [Metadata attack diagnosis](../results/formal/metadata_diagnosis/README_ZH.md) | 180 derived checks and 90 matched comparisons distinguishing visible payloads, exact attack goals, and legitimate calls to the same tool |
| [Separate metadata supplement](../results/metadata_supplement/README_ZH.md) | 12 development and 144 evaluation trials, retaining one timeout; attacks still never succeed without defense; a separate post-hoc audit examines incorrect answers that pass native grading |
| [Local/MCP validation](../results/transport_validation/README_ZH.md) | 48 model trials spanning six benign workflows and two output attacks; eight scripted paired controls check transport consistency |
| [Three demonstration cases](../demos/README_ZH.md) | Legitimate writes, execution authorization, and false quarantine with a grading blind spot; recorded replays and offline mechanism controls are identified separately |

The historical 102-trial MVP and 20 development readiness checks remain under `results/pilot/` and `results/readiness/`. They are excluded from the main study. The supplement and transport checks also do not increase the number of independent tasks in the main study.

## Interpretation limits

The evidence supports protection against the tested tool-output injections under these simulated tasks, attacks, and frozen permissions. It does not establish protection against all prompt injections. Metadata attacks provide no comparative evidence of additional protection. False quarantine, native grading false passes, and fields outside permission constraints remain documented. See [study limitations](KNOWN_LIMITATIONS_ZH.md).

Public statistics can be independently recomputed from committed data. Complete private states were used for the published derived checks; reproducing model trials generates new private records. See the [reproduction guide](REPRODUCE_ZH.md).
