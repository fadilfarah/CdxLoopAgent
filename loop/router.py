#!/usr/bin/env python3
"""
Skill router — reads the task, picks 1-3 relevant ARIS skills, returns their prompts.
Keeps token cost low by loading only what's needed.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent

SKILL_REGISTRY = {
    "idea-creator": {
        "description": "Generate novel research ideas and directions",
        "keywords": ["idea", "brainstorm", "novel", "propose", "direction", "research question"],
        "file": "skills/idea-creator.md",
    },
    "idea-discovery": {
        "description": "Discover unexplored gaps in existing literature",
        "keywords": ["gap", "discover", "unexplored", "literature", "survey", "find ideas"],
        "file": "skills/idea-discovery.md",
    },
    "research-lit": {
        "description": "Literature review and novelty analysis",
        "keywords": ["literature", "paper", "review", "related work", "novelty", "prior work", "arxiv"],
        "file": "skills/research-lit.md",
    },
    "experiment-queue": {
        "description": "Plan and run ML experiments in a queue",
        "keywords": ["experiment", "train", "run", "gpu", "baseline", "ablation", "benchmark"],
        "file": "skills/experiment-queue.md",
    },
    "auto-review-loop": {
        "description": "Cross-model review loop for improving outputs iteratively",
        "keywords": ["review", "improve", "loop", "iterate", "feedback", "score", "quality"],
        "file": "skills/auto-review-loop.md",
    },
    "paper-write": {
        "description": "Write or improve sections of a research paper",
        "keywords": ["paper", "write", "abstract", "introduction", "section", "draft", "manuscript"],
        "file": "skills/paper-write.md",
    },
    "paper-claim-audit": {
        "description": "Audit claims and citations in a paper for accuracy",
        "keywords": ["claim", "audit", "citation", "fact-check", "verify", "citation-audit"],
        "file": "skills/paper-claim-audit.md",
    },
    "kill-argument": {
        "description": "Adversarial review — find weaknesses in arguments or code",
        "keywords": ["adversarial", "weakness", "attack", "flaw", "critique", "kill", "challenge"],
        "file": "skills/kill-argument.md",
    },
    "proof-checker": {
        "description": "Verify mathematical proofs and logical correctness",
        "keywords": ["proof", "theorem", "math", "logic", "verify", "formal", "correctness"],
        "file": "skills/proof-checker.md",
    },
    "rebuttal": {
        "description": "Draft responses to reviewer critiques",
        "keywords": ["rebuttal", "reviewer", "response", "reply", "criticism", "defend"],
        "file": "skills/rebuttal.md",
    },
    "code-build": {
        "description": "General software engineering and code generation",
        "keywords": ["code", "function", "class", "build", "implement", "script", "api", "debug", "fix"],
        "file": None,  # No skill file needed — uses default Claude build prompt
    },
}


def route(task: str, client, model: str, max_skills: int = 2) -> list[dict]:
    """
    Use a cheap Claude call to pick the most relevant skills for the task.
    Returns list of {name, description, prompt} dicts.
    """
    skill_list = "\n".join(
        f"- {name}: {meta['description']}"
        for name, meta in SKILL_REGISTRY.items()
    )

    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=(
            "You are a task router. Given a task, select the 1-3 most relevant skills from the list. "
            f"Respond ONLY with a JSON array of skill names, e.g. [\"code-build\", \"auto-review-loop\"]. "
            f"Max {max_skills} skills.\n\nAvailable skills:\n{skill_list}"
        ),
        messages=[{"role": "user", "content": f"Task: {task}"}],
    )

    raw = response.content[0].text.strip()
    try:
        selected = json.loads(raw)
    except Exception:
        selected = ["code-build"]

    result = []
    for name in selected[:max_skills]:
        if name not in SKILL_REGISTRY:
            continue
        meta = SKILL_REGISTRY[name]
        prompt = load_skill_prompt(meta["file"], name)
        result.append({"name": name, "description": meta["description"], "prompt": prompt})

    return result if result else [{"name": "code-build", "description": "General code generation", "prompt": None}]


def load_skill_prompt(skill_file: str | None, name: str) -> str | None:
    """Load skill prompt from file, or return None to use default."""
    if skill_file is None:
        return None
    path = ROOT / skill_file
    if path.exists():
        return path.read_text().strip()
    return None


def format_skill_context(skills: list[dict]) -> str:
    """Format selected skills into a context block for the build prompt."""
    if not skills or all(s["prompt"] is None for s in skills):
        return ""
    lines = ["## Active Skills\n"]
    for skill in skills:
        if skill["prompt"]:
            lines.append(f"### {skill['name']}: {skill['description']}\n{skill['prompt']}\n")
        else:
            lines.append(f"### {skill['name']}: {skill['description']}\n")
    return "\n".join(lines)
