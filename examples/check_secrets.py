"""Check recognizable secret formats in this Git checkout and reachable history.

Never prints matched values. This is a bounded pattern check, not proof that no secret exists.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

PATTERNS = {
    "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "aws_access_key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "private_key": rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
    "openai_key": rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}",
    "slack_token": rb"xox[baprs]-[A-Za-z0-9-]{20,}",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def scan():
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    findings = []

    def check(data, label):
        for name, pattern in PATTERNS.items():
            if re.search(pattern, data):
                findings.append({"location": label, "pattern": name})

    files = [
        p
        for p in git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
        .decode()
        .split("\0")
        if p
    ]
    for name in files:
        path = root / name
        if path.is_file():
            check(path.read_bytes(), "worktree:" + name)
    blobs = 0
    for line in git("rev-list", "--objects", "--all").decode().splitlines():
        sha = line.split(" ", 1)[0]
        if git("cat-file", "-t", sha).strip() == b"blob":
            blobs += 1
            check(git("cat-file", "blob", sha), "history:" + sha)
    return {
        "scope": "Git worktree plus all locally reachable history; recognized patterns only; no matched values emitted",
        "worktree_files": len(files),
        "history_blobs": blobs,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()
    result = scan()
    content = json.dumps(result, indent=2)
    if args.output_file:
        with args.output_file.open("x", encoding="utf-8") as stream:
            stream.write(content)
    print(content)
    raise SystemExit(1 if result["findings"] else 0)


if __name__ == "__main__":
    main()
