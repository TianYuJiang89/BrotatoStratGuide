# Python environment

Run every Python command through the repo-local `.venv` (never the base interpreter).

## Setup (once per clone)

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install --upgrade pip
```

Git Bash on Windows calls `./.venv/Scripts/python` (not `./.venv/bin/python`).

## Use

- Run scripts: `./.venv/Scripts/python scripts/build.py --slug cyborg`
- Run tests: `./.venv/Scripts/python -m pytest -q`
- Install a package: `./.venv/Scripts/python -m pip install <pkg>`
- If an agent session needs packages, install them inside `.venv` in that session; leave the base environment untouched.

`.venv/` is gitignored and never committed.
