"""Verify Group 9 API access with a tiny synthetic calendar task, not AgentDojo."""

import datetime
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = PROJECT_ROOT / ".secrets" / "openrouter_group9.key"
MODEL = "qwen/qwen3-30b-a3b-instruct-2507"
BASE_URL = "https://openrouter.ai/api/v1"
OUTPUT_DIR = PROJECT_ROOT / "runs" / "api_check"


def read_group_key():
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key.startswith("sk-or-v1-") or any(character.isspace() for character in key):
        raise ValueError("Expected an OpenRouter credential in the Group 9 key file")
    return key


def api_request(key, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def main():
    if not os.environ.get("PBS_JOBID"):
        raise SystemExit("Submit bootstrap/check_openrouter.pbs through PBS")
    if sys.version_info[:3] != (3, 10, 20):
        raise SystemExit("Python 3.10.20 is required")
    os.umask(0o077)
    key = read_group_key()
    started = time.monotonic()
    report = {
        "test_type": "synthetic_calendar_api_check_not_agentdojo",
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "group": 9,
        "model_requested": MODEL,
        "python": sys.version.split()[0],
        "host": socket.gethostname(),
        "pbs_job_id": os.environ["PBS_JOBID"],
        "model_calls": [],
        "status": "failed",
    }
    try:
        account = api_request(key, "/key")["data"]
        report["authentication"] = "accepted"
        report["key_limit_usd"] = account.get("limit")
        report["key_remaining_before_usd"] = account.get("limit_remaining")
        models = api_request(key, "/models")["data"]
        model = next(m for m in models if m["id"] == MODEL)
        if "tools" not in model.get("supported_parameters", []):
            raise ValueError("Selected model does not advertise tool support")
        # Restrict this check to a cheap model and two small requests, without retries.
        pricing = model["pricing"]
        if float(pricing["prompt"]) > 0.000001 or float(pricing["completion"]) > 0.000002:
            raise ValueError("Model price exceeds the bootstrap price ceiling")
        report["advertised_pricing_usd_per_token"] = {
            name: pricing[name] for name in ("prompt", "completion")
        }
        messages = [
            {"role": "system", "content": "Use the provided calendar tool to answer calendar questions. Base your answer on its returned data."},
            {"role": "user", "content": "How many appointments do I have on May 15th, 2024? Give me a short summary of each appointment."},
        ]
        tools = [{
            "type": "function",
            "function": {
                "name": "get_day_calendar_events",
                "description": "Retrieve appointments for a day from a simulated calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {"day": {"type": "string", "description": "Date as YYYY-MM-DD"}},
                    "required": ["day"],
                    "additionalProperties": False,
                },
            },
        }]
        for step in range(2):
            response = api_request(key, "/chat/completions", {
                "model": MODEL,
                "messages": messages,
                "tools": tools,
                "temperature": 0,
                "max_tokens": 512,
                "provider": {"require_parameters": True},
                "stream": False,
            })
            message = response["choices"][0]["message"]
            report["model_calls"].append({
                "step": step + 1,
                "model_returned": response.get("model"),
                "provider": response.get("provider"),
                "usage": response.get("usage", {}),
                "finish_reason": response["choices"][0].get("finish_reason"),
                "message": message,
            })
            if step == 0:
                calls = message.get("tool_calls") or []
                if len(calls) != 1:
                    raise ValueError("Expected one calendar tool request")
                call = calls[0]
                if call["function"]["name"] != "get_day_calendar_events":
                    raise ValueError("Unexpected tool requested")
                arguments = json.loads(call["function"]["arguments"])
                if arguments != {"day": "2024-05-15"}:
                    raise ValueError("Unexpected tool arguments")
                result = {"day": "2024-05-15", "events": [
                    {"title": "Team sync", "time": "09:00", "description": "Share progress updates."},
                    {"title": "Project planning", "time": "11:00", "description": "Agree on the next project tasks."},
                    {"title": "Reading session", "time": "15:00", "description": "Discuss an assigned paper."},
                ]}
                report["simulated_tool_result"] = result
                messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
            else:
                answer = message.get("content") or ""
                if message.get("tool_calls") or not answer.strip():
                    raise ValueError("Expected a final answer after the tool result")
                checks = {
                    "correct_count": bool(re.search(r"\b(?:3|three)\b", answer, re.I)),
                    "all_event_titles": all(event["title"].lower() in answer.lower() for event in result["events"]),
                }
                report["answer_checks"] = checks
                report["final_answer"] = answer
                report["status"] = "passed" if all(checks.values()) else "needs_review"
    except urllib.error.HTTPError as error:
        report["error"] = {"type": "HTTPError", "status": error.code}
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error).replace(key, "[REDACTED]")}
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    costs = [entry["usage"].get("cost") for entry in report["model_calls"]]
    report["reported_total_cost_usd"] = sum(costs) if costs and all(isinstance(cost, (int, float)) for cost in costs) else None
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / ("result_" + re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ["PBS_JOBID"]) + ".json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False).replace(key, "[REDACTED]") + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "model_calls": len(report["model_calls"]), "reported_total_cost_usd": report["reported_total_cost_usd"], "result_file": str(output)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
