"""Print JSON object key/type structure without scalar values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def shape(value: object, depth: int = 0) -> object:
    if isinstance(value, dict):
        if depth >= 3:
            return "<object>"
        return {str(key): shape(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0], depth + 1)] if value else []
    return f"<{type(value).__name__}>"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    value = json.loads(args.path.read_text(encoding="utf-8"))
    print(json.dumps(shape(value), indent=2))


if __name__ == "__main__":
    main()
