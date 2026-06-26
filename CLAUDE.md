# CdxLoopAgent

General-purpose loop agent: Claude builds code, Codex reviews it, Claude fixes — repeats until Codex approves.

## Local path
`/Users/f.ahmedwork/Desktop/Code/CdxLoopAgent`

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
```

## Usage

**Single task (CLI):**
```bash
python loop/run.py "Write a function that sorts a list of dicts by a given key"
```

**Batch tasks (file):**
```bash
# Add tasks to tasks.txt, one per line
python loop/run.py
```

## How it works
1. Claude builds the code
2. Codex reviews and returns `{approved, issues}`
3. If issues found → Claude fixes → back to Codex
4. Stops when Codex approves or max rounds (5) hit
5. Output saved to `output/`, logs to `logs/`

## Config
Edit `loop/config.yaml` to change models or max rounds.
