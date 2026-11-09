"""Print a redacted summary of the runtime configuration. Never echoes secrets."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    from config import _load_dotenv as load_env

    load_env(path, override=True)


def _mask(key: str | None) -> str:
    if not key:
        return "(missing)"
    visible = 4
    if len(key) <= visible * 2:
        return f"<{key[:0]}{'*' * len(key)}> (len={len(key)})"
    return f"{key[:visible]}...{key[-visible:]} (len={len(key)})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Moorchid configuration sanity check")
    parser.add_argument(
        "--config",
        action="store_true",
        help="Print the full as_dict() configuration",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    _load_dotenv(project_root / ".env")

    from config import reset_config, get_config

    reset_config()
    cfg = get_config()

    print("Moorchid configuration")
    print("-" * 48)
    print(f"  database_path      : {cfg.database_path}")
    print(f"  chroma_persist_dir : {cfg.chroma_persist_dir}")
    print(f"  vector_store_type  : {cfg.vector_store_type}")
    print(f"  collection_name    : {cfg.vector_collection_name}")
    print()
    print("  DeepSeek")
    print(f"    enabled          : {cfg.deepseek_enabled}")
    print(f"    api_key          : {_mask(cfg.deepseek_api_key)}")
    print(f"    base_url         : {cfg.deepseek_base_url}")
    print(f"    model            : {cfg.deepseek_model}")
    print(f"    timeout_seconds  : {cfg.deepseek_timeout_seconds}")
    print()
    print("  ZhipuAI")
    print(f"    enabled          : {cfg.zhipuai_enabled}")
    print(f"    api_key          : {_mask(cfg.zhipuai_api_key)}")
    print(f"    base_url         : {cfg.zhipuai_base_url}")
    print(f"    model            : {cfg.zhipuai_model}")
    print(f"    timeout_seconds  : {cfg.zhipuai_timeout_seconds}")
    print()
    print("  Behaviour")
    print(f"    allow_demo_fallback : {cfg.allow_demo_fallback}")

    if args.config:
        print()
        print("Raw configuration (excluding secrets)")
        import json

        snapshot = cfg.as_dict()
        deepseek = snapshot["deepseek"].copy()
        zhipuai = snapshot["zhipuai"].copy()
        deepseek["api_key_masked"] = _mask(cfg.deepseek_api_key)
        zhipuai["api_key_masked"] = _mask(cfg.zhipuai_api_key)
        deepseek.pop("api_key", None)
        zhipuai.pop("api_key", None)
        snapshot["deepseek"] = deepseek
        snapshot["zhipuai"] = zhipuai
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))

    warnings: list[str] = []
    if not cfg.deepseek_enabled:
        warnings.append("- DEEPSEEK_API_KEY missing: Soul Chat will fall back to the demo reply.")
    if not cfg.zhipuai_enabled:
        warnings.append(
            "- ZHIPUAI_API_KEY missing: Embeddings will fall back to the deterministic hash model."
        )
    if warnings:
        print()
        print("Notes")
        for line in warnings:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())