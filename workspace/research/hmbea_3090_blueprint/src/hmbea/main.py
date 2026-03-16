from __future__ import annotations

import argparse
import json
from typing import Any

from .graph import GraphRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the HMBEA single-3090 blueprint graph.")
    parser.add_argument("request", help="User task to process")
    args = parser.parse_args()

    runtime = GraphRuntime()
    graph = runtime.build()
    result: dict[str, Any] = graph.invoke({"raw_request": args.request, "retries": 0})
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
