"""Run one native AgentDojo task through OpenRouter, on a PBS compute node."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[1]))
from release_integrity import recorded_digest
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import socket
import sys
import time
import urllib.error
import urllib.request

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, load_system_message
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop, ToolsExecutor
from agentdojo.benchmark import benchmark_suite_without_injections
from agentdojo.functions_runtime import FunctionCall
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import get_text_content_as_str, text_content_block_from_string

ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://openrouter.ai/api/v1/chat/completions"


def plain_content(message):
    content = message.get("content")
    return get_text_content_as_str(content) if content is not None else None


def api_message(message):
    role = message["role"]
    result = {"role": role, "content": plain_content(message)}
    if role == "assistant" and message.get("tool_calls"):
        result["tool_calls"] = [
            {"id": call.id, "type": "function", "function": {
                "name": call.function, "arguments": json.dumps(call.args)}}
            for call in message["tool_calls"]
        ]
    elif role == "tool":
        result["tool_call_id"] = message["tool_call_id"]
        if message.get("error"):
            result["content"] = message["error"]
    return result


def json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(type(value).__name__)


class OpenRouterLLM(BasePipelineElement):
    def __init__(self, config, key, output):
        self.config = config
        self.key = key
        self.output = output
        self.name = "openrouter_qwen3_30b_a3b_instruct_2507_no_defense"
        self.calls = []
        self.messages = []
        self.attempts = 0

    def save_json(self, path, data):
        encoded = json.dumps(data, indent=2, ensure_ascii=False, default=json_default)
        path.write_text(encoded.replace(self.key, "[REDACTED]") + "\n", encoding="utf-8")

    def query(self, query, runtime, env, messages, extra_args):
        self.messages = list(messages)
        if self.attempts >= self.config["max_model_calls"]:
            raise RuntimeError("Model call budget exhausted")
        payload = {
            "model": self.config["model"],
            "messages": [api_message(message) for message in messages],
            "tools": [{"type": "function", "function": {
                "name": function.name,
                "description": function.description,
                "parameters": function.parameters.model_json_schema(),
            }} for function in runtime.functions.values()],
            "temperature": self.config["temperature"],
            "max_tokens": self.config["max_output_tokens"],
            "provider": {"order": [self.config["provider"]], "allow_fallbacks": False, "require_parameters": True},
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        if len(body) > self.config["max_request_bytes"]:
            raise RuntimeError("Request exceeds the pilot input size budget")
        self.attempts += 1
        step = self.attempts
        self.save_json(self.output / f"request_{step:02d}.json", payload)
        request = urllib.request.Request(API_URL, data=body, headers={
            "Authorization": "Bearer " + self.key, "Content-Type": "application/json",
        })
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                completion = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(8192).decode("utf-8", errors="replace")
            self.save_json(self.output / f"error_{step:02d}.json", {"status": error.code, "body": detail})
            raise RuntimeError(f"OpenRouter HTTP error {error.code}; see error_{step:02d}.json") from None
        self.save_json(self.output / f"response_{step:02d}.json", completion)
        message = completion["choices"][0]["message"]
        self.calls.append({
            "step": step, "model": completion.get("model"),
            "provider": completion.get("provider"), "usage": completion.get("usage", {}),
            "finish_reason": completion["choices"][0].get("finish_reason"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "available_tool_count": len(payload["tools"]),
        })
        calls = []
        for call in message.get("tool_calls") or []:
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict) or not call.get("id"):
                raise ValueError("Invalid tool call returned by model")
            calls.append(FunctionCall(function=call["function"]["name"], args=arguments, id=call["id"]))
        content = message.get("content")
        assistant = {"role": "assistant", "content": [text_content_block_from_string(content)] if content else None, "tool_calls": calls or None}
        self.messages = [*messages, assistant]
        self.save_json(self.output / "api_usage.json", self.calls)
        return query, runtime, env, self.messages, extra_args


class CaptureEnvironment(BasePipelineElement):
    def __init__(self, pipeline, llm):
        self.pipeline = pipeline
        self.llm = llm
        self.name = pipeline.name
        self.unchanged = None

    def query(self, query, runtime, env, messages=None, extra_args=None):
        messages = [] if messages is None else messages
        extra_args = {} if extra_args is None else extra_args
        before = env.model_dump(mode="json")
        self.llm.save_json(self.llm.output / "environment_before.json", before)
        try:
            result = self.pipeline.query(query, runtime, env, messages, extra_args)
            env = result[2]
            return result
        finally:
            after = env.model_dump(mode="json")
            self.llm.save_json(self.llm.output / "environment_after.json", after)
            self.unchanged = before == after


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    if not os.environ.get("PBS_JOBID"):
        raise SystemExit("A PBS compute-node allocation is required")
    if platform.python_version() != "3.10.20":
        raise SystemExit("Python 3.10.20 is required")
    os.umask(0o077)
    config = json.loads((ROOT / "configs/first_task.json").read_text())
    actual_version = importlib.metadata.version("agentdojo")
    if actual_version != config["agentdojo_version"]:
        raise SystemExit("AgentDojo version differs from the saved configuration")
    suite = get_suite(config["benchmark_version"], config["suite"])
    task = suite.get_user_task_by_id(config["task"])
    if arguments.check_only:
        suite.load_and_inject_default_environment({})
        print(json.dumps({"check": "passed", "agentdojo": actual_version, "benchmark": config["benchmark_version"], "task": task.ID, "prompt": task.PROMPT, "model_calls": 0}))
        return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    tag = now.strftime("%Y%m%dT%H%M%S%fZ")
    job = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ["PBS_JOBID"])
    output = ROOT / "runs" / "first_task" / (tag + "_" + job)
    output.mkdir(parents=True, exist_ok=False)
    key = (ROOT / ".secrets/openrouter_group9.key").read_text().strip()
    if not key.startswith("sk-or-v1-"):
        raise SystemExit("Invalid Group 9 credential configuration")
    llm = OpenRouterLLM(config, key, output)
    pipeline = AgentPipeline([
        SystemMessage(load_system_message(None)), InitQuery(), llm,
        ToolsExecutionLoop([ToolsExecutor(), llm], max_iters=config["max_model_calls"] - 1),
    ])
    pipeline.name = llm.name
    captured = CaptureEnvironment(pipeline, llm)
    summary = {
        "status": "failed", "started_at_utc": now.isoformat(), "config": config,
        "python": platform.python_version(), "agentdojo": actual_version,
        "host": socket.gethostname(), "pbs_job_id": os.environ["PBS_JOBID"],
        "task_prompt": task.PROMPT, "attack_applied": False,
        "script_sha256": recorded_digest(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
    }
    started = time.monotonic()
    try:
        with OutputLogger(str(output / "agentdojo_logs")):
            results = benchmark_suite_without_injections(
                captured, suite, logdir=output / "agentdojo_logs", force_rerun=False,
                user_tasks=[config["task"]], benchmark_version=config["benchmark_version"],
            )
        success = results["utility_results"][(config["task"], "")]
        summary["native_task_success"] = success
        summary["status"] = "passed" if success else "task_failed"
        # Native security=True in no-attack mode is not a measured defense result.
    except Exception as error:
        summary["error"] = {"type": type(error).__name__, "message": str(error).replace(key, "[REDACTED]")}
    summary["environment_unchanged"] = captured.unchanged
    summary["model_calls"] = llm.calls
    summary["model_attempts"] = llm.attempts
    summary["tool_calls"] = [
        {"name": call.function, "arguments": call.args}
        for message in llm.messages if message["role"] == "assistant"
        for call in message.get("tool_calls") or []
    ]
    finals = [plain_content(message) for message in llm.messages if message["role"] == "assistant" and not message.get("tool_calls")]
    summary["final_answer"] = finals[-1] if finals else None
    summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
    costs = [call["usage"].get("cost") for call in llm.calls]
    summary["reported_total_cost_usd"] = sum(costs) if costs and all(isinstance(cost, (int, float)) for cost in costs) else None
    summary["prompt_tokens"] = sum(call["usage"].get("prompt_tokens", 0) for call in llm.calls)
    summary["completion_tokens"] = sum(call["usage"].get("completion_tokens", 0) for call in llm.calls)
    llm.save_json(output / "summary.json", summary)
    llm.save_json(output / "trajectory.json", llm.messages)
    print(json.dumps({"status": summary["status"], "result": str(output / "summary.json"), "model_calls": len(llm.calls), "cost_usd": summary["reported_total_cost_usd"], "error": summary.get("error")}))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
