"""Small command-line entry point; run from the experiment repository."""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from .config import build_settings, load_config
from .data import prepare_corpus
from .runner import inspect_ollama, run


def main():
    # Upstream parse_text uses Path.open() without an encoding. Windows defaults
    # can silently decode UTF-8 scientific symbols as CP1252 without raising.
    # Restart before importing/using PaperQA; changing PYTHONUTF8 in-process is insufficient.
    if not sys.flags.utf8_mode:
        child = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "paperqa_reflect.cli", *sys.argv[1:]],
            check=False,
        )
        raise SystemExit(child.returncode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "prepare-smoke", "prepare-corpus", "run"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/local-qwen3-8b.json"))
    parser.add_argument(
        "--source", type=Path, help="Optional existing copy of the exact fixture PDF"
    )
    parser.add_argument("--limit", type=int, default=1, help="Questions to run; default 1")
    parser.add_argument("--question-id", help="Run one particular question from the configured set")
    parser.add_argument(
        "--allow-holdout",
        action="store_true",
        help="Intentionally evaluate the reserved set after freezing model selection",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    root = args.root.resolve()
    config_path = root / args.config
    config = load_config(config_path)
    if args.command in {"prepare-smoke", "prepare-corpus"}:
        docs = prepare_corpus(root, config, args.source)
        print(f"Verified {len(docs)} source document(s) in {root / config.corpus_dir}")
    elif args.command == "doctor":
        info = inspect_ollama(config)
        settings = build_settings(config, root, root / ".cache/doctor", root / ".cache/unused.csv")
        settings.make_aviary_tool_selector("ToolSelector")
        settings.get_embedding_model()
        print(
            json.dumps(
                {
                    "status": "ready",
                    "ollama": info,
                    "python_utf8_mode": sys.flags.utf8_mode,
                    "note": "Configuration/API compatibility and installed models checked; no inference.",
                },
                indent=2,
            )
        )
    else:
        if config.split == "holdout" and not args.allow_holdout:
            parser.error(
                "Reserved questions require --allow-holdout; do not use them for model selection."
            )
        _, success = asyncio.run(run(config, config_path, root, args.limit, args.question_id))
        raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
