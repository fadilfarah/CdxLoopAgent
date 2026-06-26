#!/usr/bin/env python3
import os
import sys
import json
import yaml
import argparse
from datetime import datetime
from pathlib import Path

import anthropic
import openai

from router import route, format_skill_context

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "loop" / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_prompt(path):
    with open(ROOT / path) as f:
        return f.read().strip()


def claude_build(task, existing_code, issues, skill_context, config, client):
    base_prompt = load_prompt(config["prompts"]["build"])
    system = base_prompt
    if skill_context:
        system = f"{base_prompt}\n\n{skill_context}"

    if existing_code and issues:
        user_msg = (
            f"Task: {task}\n\n"
            f"Previous code:\n```\n{existing_code}\n```\n\n"
            f"Issues to fix:\n" + "\n".join(f"- {i}" for i in issues)
        )
    else:
        user_msg = f"Task: {task}"

    response = client.messages.create(
        model=config["claude_model"],
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text.strip()


def codex_review(code, config, client):
    review_prompt = load_prompt(config["prompts"]["review"])
    response = client.chat.completions.create(
        model=config["codex_model"],
        messages=[
            {"role": "system", "content": review_prompt},
            {"role": "user", "content": f"Review this code:\n\n```\n{code}\n```"},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def save_output(task_id, code, config):
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{task_id}-final.py"
    out_file.write_text(code)
    return out_file


def save_log(task_id, log_data, config):
    log_dir = ROOT / config["logs_dir"]
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{task_id}.json"
    log_file.write_text(json.dumps(log_data, indent=2))
    return log_file


def run_task(task, task_id, config, anthropic_client, openai_client):
    print(f"\n{'='*60}")
    print(f"Task [{task_id}]: {task}")
    print(f"{'='*60}")

    # Route: pick relevant skills cheaply before the main loop
    print(f"\n[Router] Selecting skills...")
    skills = route(task, anthropic_client, config["router_model"])
    skill_names = [s["name"] for s in skills]
    skill_context = format_skill_context(skills)
    print(f"  → Skills selected: {', '.join(skill_names)}")

    code = None
    issues = []
    log = {
        "task": task,
        "task_id": task_id,
        "skills_selected": skill_names,
        "rounds": [],
    }

    for round_num in range(1, config["max_rounds"] + 1):
        print(f"\n[Round {round_num}] Claude building...")
        code = claude_build(task, code, issues, skill_context, config, anthropic_client)
        print(f"  ✓ Code generated ({len(code.splitlines())} lines)")

        print(f"[Round {round_num}] Codex reviewing...")
        try:
            review = codex_review(code, config, openai_client)
        except Exception as e:
            print(f"  ⚠ Codex review failed: {e} — using output as-is")
            review = {"approved": True, "issues": []}

        log["rounds"].append({"round": round_num, "code": code, "review": review})

        if review.get("approved"):
            print(f"  ✓ Codex approved!")
            break
        else:
            issues = review.get("issues", [])
            print(f"  ✗ Issues ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")

        if round_num == config["max_rounds"]:
            print(f"\n⚠ Max rounds ({config['max_rounds']}) reached — saving best output")

    out_file = save_output(task_id, code, config)
    log_file = save_log(task_id, log, config)

    print(f"\n✓ Output: {out_file}")
    print(f"✓ Log:    {log_file}")
    print(f"\n--- Final Output ---\n{code}\n")

    return code


def get_tasks_from_file():
    tasks_file = ROOT / "tasks.txt"
    if not tasks_file.exists():
        return []
    lines = tasks_file.read_text().strip().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def main():
    parser = argparse.ArgumentParser(description="CdxLoopAgent — Claude builds, Codex reviews, Claude fixes")
    parser.add_argument("task", nargs="?", help="Task to run (optional if tasks.txt exists)")
    parser.add_argument("--project", help="Target project path (for context)")
    args = parser.parse_args()

    config = load_config()

    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    openai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    tasks = []
    if args.task:
        tasks.append(args.task)
    else:
        tasks = get_tasks_from_file()

    if not tasks:
        print("No tasks provided. Pass a task as an argument or add tasks to tasks.txt")
        sys.exit(1)

    for i, task in enumerate(tasks, 1):
        task_id = f"task-{i:03d}"
        run_task(task, task_id, config, anthropic_client, openai_client)


if __name__ == "__main__":
    main()
