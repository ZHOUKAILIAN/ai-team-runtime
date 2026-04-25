from __future__ import annotations

import argparse
import re


PRERELEASE_PATTERN = re.compile(r"(a|alpha|b|beta|rc|pre|preview|dev)[.-]?\d+", re.IGNORECASE)


def is_prerelease_version(version: str) -> bool:
    return bool(PRERELEASE_PATTERN.search(version))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--github-args", action="store_true")
    args = parser.parse_args()

    if args.github_args:
        if is_prerelease_version(args.version):
            print("--prerelease --latest=false")
        return 0

    print("prerelease" if is_prerelease_version(args.version) else "stable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
