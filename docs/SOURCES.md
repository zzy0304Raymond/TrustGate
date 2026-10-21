# Sources and scope

The project reuses upstream simulated tasks, tools, and evaluators, and adds the MCP adapter, gateway policies, experiment manifests, study-specific attacks, analyses, and demonstrations.

- [AgentDojo](https://github.com/ethz-spylab/agentdojo): package 0.1.35, Workspace suite v1.2.2; native tools, environment, user tasks, and evaluators. See the upstream repository's license for benchmark and software terms.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk): package 1.26.0; stdio client/server transport. Architecture and tool concepts follow the [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25/architecture).
- [Protect AI prompt-injection detector](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2): fixed revision in `models/detector_revision.txt`; exact file hashes in the formal manifest. It is an English-language, existing classifier rather than a model trained by this project.
- [MCPTox](https://arxiv.org/abs/2508.14925) and [MCP-ITP](https://arxiv.org/abs/2601.07395): related tool-poisoning settings. This repository's payload templates were written for this simulated study and are not copies of either full benchmark implementation.
- [MCP-Guard](https://arxiv.org/abs/2508.10991) and [CaMeL](https://arxiv.org/abs/2503.18813): related staged screening and execution-policy approaches motivating the design. TrustGate does not implement CaMeL's complete information-flow machinery or claim equivalent guarantees.

No upstream package or model is relicensed here. Downloaded weights are not committed. The published results distinguish main experiments, development/pilot trials, supplemental model trials, and deterministic offline checks.
