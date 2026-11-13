"""Execute P1 scripts using the existing Docker Compose MongoDB service."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
SCRIPTS = {"setup": "database/setup.js", "queries": "queries/mongo.js", "verify": "queries/verify.js"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=SCRIPTS)
    args = parser.parse_args()
    script = (ROOT / SCRIPTS[args.command]).read_bytes()
    result = subprocess.run([
        "docker", "compose", "-f", str(ROOT / "compose.yaml"),
        "exec", "-T", "mongodb", "mongosh", "--quiet", "--file", "/dev/stdin"
    ], input=script)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
