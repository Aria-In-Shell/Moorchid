"""Dotenv loader must let .env override empty Windows env vars."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class DotenvLoaderTests(unittest.TestCase):
    def test_env_file_overrides_empty_variable(self) -> None:
        from config import _load_dotenv

        previous = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = ""
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / ".env"
                path.write_text("DEEPSEEK_API_KEY=sk-from-file-not-placeholder\n", encoding="utf-8")
                _load_dotenv(path, override=True)
                self.assertEqual(os.environ.get("DEEPSEEK_API_KEY"), "sk-from-file-not-placeholder")
        finally:
            if previous is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
