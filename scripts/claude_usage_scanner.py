#!/usr/bin/env python3
"""Local-only Claude Code usage scanner. It never estimates account quota."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

HOME = Path.home()
BASE = Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude"))
COLOR = "#D97757"
QUOTA_NOTE = "Claude quota is not estimated."


def stamp(value) -> float:
    if isinstance(value, (int, float)):
        return float(value) / (1000 if value > 1e10 else 1)
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0
    return 0


def text(value, limit: int = 140) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def local_day(timestamp: float, fallback: float) -> dt.date:
    return dt.datetime.fromtimestamp(timestamp or fallback).date()


def recent_days(today: dt.date, prompts: Counter, steps: Counter) -> list[dict]:
    rows = []
    for offset in range(6, -1, -1):
        day = today - dt.timedelta(days=offset)
        key = str(day)
        rows.append({
            "date": key,
            "messageCount": prompts[key],
            "prompts": prompts[key],
            "steps": steps[key],
        })
    return rows


def blank_model(name: str) -> dict:
    return {
        "name": name,
        "prompts": 0,
        "steps": 0,
        "todayPrompts": 0,
        "todaySteps": 0,
        "weekPrompts": 0,
        "weekSteps": 0,
        "inputTokens": 0,
        "outputTokens": 0,
        "cachedTokens": 0,
        "color": COLOR,
    }


def claude_active() -> bool:
    try:
        return bool(subprocess.run(["pgrep", "-x", "claude"], capture_output=True, timeout=1).stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def scan(base: Path) -> dict:
    today = dt.date.today()
    week = {str(today - dt.timedelta(days=i)) for i in range(7)}
    daily_prompts: Counter = Counter()
    daily_steps: Counter = Counter()
    models: dict[str, dict] = {}
    tools: Counter = Counter()
    sessions = []

    def bucket(name: str) -> dict:
        return models.setdefault(name, blank_model(name))

    def add_prompt(model: str, day: dt.date) -> None:
        row = bucket(model)
        key = str(day)
        row["prompts"] += 1
        daily_prompts[key] += 1
        if day == today:
            row["todayPrompts"] += 1
        if key in week:
            row["weekPrompts"] += 1

    def add_step(model: str, day: dt.date) -> None:
        row = bucket(model)
        key = str(day)
        row["steps"] += 1
        daily_steps[key] += 1
        if day == today:
            row["todaySteps"] += 1
        if key in week:
            row["weekSteps"] += 1

    projects = base / "projects"
    paths = projects.glob("**/*.jsonl") if projects.exists() else []
    for path in paths:
        prompts = 0
        tokens = 0
        updated = path.stat().st_mtime
        model = ""
        preview = ""
        pending: list[dt.date] = []
        try:
            for line in path.open(encoding="utf-8", errors="replace"):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                message = row.get("message") or {}
                role = message.get("role") or row.get("role")
                day = local_day(stamp(row.get("timestamp")), updated)
                if role == "user":
                    prompts += 1
                    pending.append(day)
                    content = message.get("content", row.get("content", ""))
                    if not preview:
                        preview = text(content if isinstance(content, str) else "Prompt")
                seen = message.get("model") or row.get("model") or ""
                if seen:
                    model = str(seen)
                if role == "assistant" and model:
                    add_step(model, day)
                    while pending:
                        add_prompt(model, pending.pop(0))
                usage = message.get("usage") or row.get("usage") or {}
                input_tokens = int(usage.get("input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)
                cached = int(usage.get("cache_read_input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
                piece = input_tokens + output_tokens + cached
                tokens += piece
                if piece and model:
                    target = bucket(model)
                    target["inputTokens"] += input_tokens
                    target["outputTokens"] += output_tokens
                    target["cachedTokens"] += cached
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools[text(block.get("name"), 60)] += 1
        except OSError:
            continue
        if pending:
            target_name = model or "Claude"
            for day in pending:
                add_prompt(target_name, day)
        if prompts or tokens:
            sessions.append({
                "conversationId": path.stem,
                "title": preview or "Claude session",
                "preview": preview or "Claude session",
                "workspace": "",
                "workspaceName": path.parent.name,
                "updated_at": dt.datetime.fromtimestamp(updated).isoformat(),
                "stepCount": prompts,
                "model": model or "Claude",
                "tokenCount": tokens,
                "isActive": False,
            })

    # Recent Claude Code builds keep a per-session key under ~/.claude/sessions
    # even when the transcript has not been written yet. Those files are local
    # activity, but they have no prompt or token counts.
    if not sessions and (base / "sessions").exists():
        for path in (base / "sessions").glob("*.key"):
            try:
                updated = path.stat().st_mtime
            except OSError:
                continue
            sessions.append({
                "conversationId": path.stem,
                "title": "Claude session",
                "preview": "Local Claude session state",
                "workspace": "",
                "workspaceName": "Claude Code",
                "updated_at": dt.datetime.fromtimestamp(updated).isoformat(),
                "stepCount": 0,
                "model": "Claude",
                "tokenCount": 0,
                "isActive": False,
            })

    active = claude_active()
    sessions.sort(key=lambda item: item["updated_at"], reverse=True)
    if active and sessions:
        sessions[0]["isActive"] = True
    total_tokens = sum(item["tokenCount"] for item in sessions)
    total_prompts = sum(daily_prompts.values())
    total_steps = sum(daily_steps.values())
    model_list = sorted(models.values(), key=lambda item: (item["prompts"], item["steps"], item["name"]), reverse=True)
    return {
        "ready": True,
        "active": active,
        "activeStatus": "Working" if active else "Idle",
        "hasActiveSession": active,
        "hasLocalStats": bool(sessions),
        "canKill": False,
        "tierLabel": "Anthropic · local usage",
        "currentModel": sessions[0]["model"] if sessions else "Claude",
        "todayPrompts": daily_prompts[str(today)],
        "todaySessions": sum(1 for item in sessions if str(item["updated_at"]).startswith(str(today))),
        "todaySteps": daily_steps[str(today)],
        "todayTotalTokens": total_tokens,
        "todayTokensByModel": {item["name"]: item["inputTokens"] + item["outputTokens"] + item["cachedTokens"] for item in model_list},
        "recentDays": recent_days(today, daily_prompts, daily_steps),
        "totalPrompts": total_prompts,
        "totalSessions": len(sessions),
        "totalSteps": total_steps,
        "activeSessions": [item for item in sessions if item["isActive"]],
        "recentSessions": sessions[:10],
        "toolUsage": dict(tools.most_common(12)),
        "modelUsage": {item["name"]: item for item in model_list},
        "modelList": model_list,
        "quotaGroups": [],
        "quotaNote": QUOTA_NOTE,
        "limits": [],
        "recentWorkspaces": [],
        "premiumRequests": 0,
        "planTier": "",
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "quotaUpdatedAt": "",
        "usageStatusText": "Local usage only — Claude quota is not estimated." if sessions else "",
        "authHelpText": "",
    }


def main() -> None:
    print(json.dumps(scan(BASE), separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
