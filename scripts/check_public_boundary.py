"""Reject product paths in the commit history selected for public publication."""

import argparse
import subprocess
import sys


def git(*args):
    return subprocess.check_output(["git", *args], text=True).splitlines()


def check_commits(commits):
    failures = []
    for commit in sorted(set(commits)):
        paths = git("ls-tree", "-r", "--name-only", commit)
        forbidden = [path for path in paths if "copilomics" in path.lower()]
        if forbidden:
            failures.append((commit, forbidden))
    for commit, paths in failures:
        print(f"Blocked: prototype paths in public commit {commit}:", file=sys.stderr)
        for path in paths:
            print(f"  {path}", file=sys.stderr)
    return not failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()
    if args.all:
        commits = git("rev-list", "--all")
    else:
        commits = []
        for line in sys.stdin:
            _, local_sha, _, remote_sha = line.split()
            if set(local_sha) == {"0"}:
                continue
            revision = local_sha if set(remote_sha) == {"0"} else f"{remote_sha}..{local_sha}"
            commits.extend(git("rev-list", revision))
    if not check_commits(commits):
        return 1
    print(f"Public repository boundary passed ({len(set(commits))} commits).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
