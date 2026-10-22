# Interfaces common to five experiments

## Cases and shards

An execution case must include `case_id, workflow, task, surface, condition, repeat, transport`.`surface` is `benign/output/metadata`; the names of the seven conditions are fixed in `trustgate/planning.py` The model supplier prompt version threshold and budget come from the configuration list and must not be changed privately by node.

Official cases also include `slot_id, attack_case_id, split`, associated with frozen via attack_case_id `metadata_tool, output_tools, payload, goal, template_family`Official output of attack appends text returned by specified MCP without modifying backend data; native user task scorer remains unchanged, with attack objective determined by explicit state difference detection.

Each path only owns its own `runs/studies/<run-id>/shard-NN/`, no branch can share modifications to the same state.pickle. Model files are shared read-only.

## permissions

Permissions are determined from the original user request and the trusted resource directory before attack, with minimum inclusion of `origin, task_prompt, read_tools, writes`Write permissions constrain tools, objects, recipients, and parameters; reading of `ground_truth`, attacker targets, or hidden evaluation results is not allowed. Official compiler is `compile_policy(task, env, runtime, workflow)`; during actual execution only the frozen policy is read. Dynamically shared objects are allowed only if confirmed by a trusted backend that the newly created file matches the user request. The policy does not expand based on attack text.

## Detection

`Detector.score(text)` Return `score, blocked, seconds, windows`. The threshold is determined on the development set and cannot be adjusted after the test set is frozen; when the document exceeds one window, the entire text must be covered. Source attribution cannot fabricate credibility or grant additional permissions in the prompt.

## Output

Each result must include at least `case_id`case identity field,`status, native_utility, attacker_success, safe_completion, injection_reached_model, seconds, api_calls, cost_usd, result_dir`. Errors timeouts and rejections are recorded; failure to reach the injection point must not be conflated with ’attack blocked’.

The unified summary statistics use all planned cases as the denominator and additionally report the subset of executed/arrived cases. Group by task and pair-wise comparison conditions; three repetitions of the same attack do not count as three independent attack types. Report attack and output attack separately.

## Shared file modifications

Five members ran their data using the same frozen version without separately developing five modules. During formal execution, no individual modifications to the model, permissions, detectors, prompts, or main loop were allowed; any code changes required unified review and version update before re-publishing the checklist.

Each person writes only their own `experiments/deliveries/person-NN/` and the corresponding run directory. Results summary and reporting use all five sets to avoid inconsistent metrics from separate reporting.
