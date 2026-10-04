"""Check the measured baseline source/config bytes without inference or network."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "results/baselines/uia-local-reference-v1.json").read_text())
expected = dict(manifest["common_hashes"]["code_sha256"])
expected[manifest["recommended_config"]] = manifest["config_sha256"]
expected[manifest["repeat_config"]] = manifest["repeat_config_sha256"]
mismatches = [name for name, digest in expected.items()
              if not (root / name).is_file()
              or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
if mismatches:
    raise SystemExit("Baseline differs: " + ", ".join(mismatches))
print(f"Baseline source/config hashes match: {len(expected)}/{len(expected)}")
