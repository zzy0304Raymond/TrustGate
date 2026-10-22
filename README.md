# TrustGate

A prompt-injection defense gateway for MCP-connected agents, evaluated in AgentDojo's simulated email, calendar, and cloud-drive workspace.

TrustGate combines source labels, tool-metadata screening, and authorization before tool execution. Permissions are fixed from the legitimate request and a trusted pre-attack resource catalog. Tool text cannot expand them. All writes affect simulated objects.

## Start here

| Purpose | Entry point |
|---|---|
| Understand the system and evaluation | [System and experiment design](docs/SYSTEM.md) |
| Reproduce published statistics without an API key | [Reproduction guide](docs/REPRODUCE_ZH.md) |
| Inspect results, plots, and limitations | [Results overview](docs/RESULTS_ZH.md) |
| Run the three demonstrations | [Demo guide](demos/README_ZH.md) · [Standalone page](demos/index.html) |
| Run the frozen model experiments | [Formal experiment instructions](docs/FORMAL_START_ZH.md) |
| Check platform compatibility | [Environment requirements](docs/CROSS_PLATFORM_CHECKLIST_ZH.md) |

## Main findings

The frozen main study contains **1,680 trials**: 20 tasks, 60 attack cases, seven configurations, and three repetitions. The two attack surfaces are reported separately. One infrastructure timeout is retained and excluded from valid-trial comparisons.

| Configuration | Benign task completion | Output attack success | Safe completion under output attack | Metadata attack success |
|---|---:|---:|---:|---:|
| No defense | 46/60 | 10/90 | 61/90 | 0/90 |
| Prompt defense | 40/60 | 13/90 | 50/90 | 0/90 |
| Classifier | 28/60 | 13/90 | 39/90 | 0/90 |
| TrustGate | 44/60 | 0/89 | 68/89 | 0/90 |
| Without provenance | 43/60 | 0/90 | 66/90 | 0/90 |
| Without metadata screening | 43/60 | 0/90 | 67/90 | 0/90 |
| Without authorization | 43/60 | 6/90 | 67/90 | 0/90 |

Attack and safe-completion columns use valid trials. For TrustGate, safe completion over the 90 planned output trials is 68/90. Task completion uses the frozen native evaluator; trajectory audits identify limitations in that evaluator.

The evidence supports a security benefit on the tested output injections and directly demonstrates an authorization check stopping an attempted attack. Independent gains from provenance and metadata screening are not established. Metadata attacks also failed without defense, including the separate supplement, so that surface does not demonstrate an added security benefit. Normal tool quarantine and task-quality failures remain part of the findings.

[Paired estimates and mechanism evidence](results/formal/mechanism_evidence/README_ZH.md) · [Six result figures](results/formal/analysis/README_ZH.md) · [Overhead and sensitivity](results/formal/overhead/README_ZH.md) · [False positives](results/formal/false_positives/README_ZH.md)

## Reproduce

The reference runtime is **Python 3.10.20**, with pinned dependencies. Computation uses CPUs; a GPU is not required. Vanda jobs must run through PBS.

```bash
git clone https://github.com/zzy0304Raymond/TrustGate.git
cd TrustGate
# On Vanda, after installing the pinned environment:
qsub -P personal-YOUR_ACCOUNT scripts/reproduce.pbs
```

This entry point verifies and rebuilds public results without model API calls. For full offline MCP, detector, and permission checks, configure the pinned detector directory and use the full mode described in the [reproduction guide](docs/REPRODUCE_ZH.md). Model experiments are an explicit separate command and require an authorized API credential. New outputs go under ignored `runs/` directories.

## Repository layout

| Directory | Contents |
|---|---|
| `trustgate/` | Frozen experiment runner, permissions, budget control, manifests, and result export |
| `experiments/mvp/` | Shared agent loop, MCP servers, simulated state, and detector implementation |
| `data/formal/`, `configs/`, `assignments/` | Tasks, attacks, permissions, settings, and frozen trial manifests |
| `experiments/deliveries/` | Five complete public trial datasets and execution provenance |
| `results/` | Main analysis, supplemental studies, diagnostic evidence, and validation results |
| `review-data/` | Selected case evidence supporting failure and mechanism analysis |
| `scripts/`, `tests/` | Reproduction entry points, platform adapters, and regression tests |
| `demos/`, `docs/` | Recorded demonstrations, runtime instructions, system design, and limitations |

The historical pilot and later supplemental studies are separate datasets. Failed trials are retained. Public results can be verified from the committed data; complete raw requests, responses, workspace snapshots, credentials, and model weights are excluded. Re-running the model experiment produces a new sample and need not reproduce identical answers.

The English publication preserves the original measurements and experiment identities. See [language revision and artifact integrity](docs/ENGLISH_RELEASE.md) for the exact mapping between original and translated files.

## Sources

The benchmark and native evaluators come from [AgentDojo](https://github.com/ethz-spylab/agentdojo); tool transport uses the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk); metadata screening uses a pinned [Protect AI DeBERTa detector](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2). The study's attacks are documented adaptations of tool-poisoning settings, not a reproduction of an external benchmark's complete attack suite. See [sources and scope](docs/SOURCES.md). Upstream software, model weights, and benchmark data retain their respective licenses.
