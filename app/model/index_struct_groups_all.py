from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "struct_groups.json"
OUT = ROOT / "struct_groups_indexed_all.json"

if not SRC.exists():
    print(f"Source not found: {SRC}")
    raise SystemExit(1)

text = SRC.read_text(encoding="utf-8")
try:
    data = json.loads(text)
except Exception as e:
    print(f"Failed to parse JSON: {e}")
    raise

if not isinstance(data, list):
    print("Source JSON is not an array; aborting.")
    raise SystemExit(1)

def entry_has_parallel(entry: dict) -> bool:

    ns = entry.get("node_summary")
    if isinstance(ns, dict):

        if ns.get("ParallelNode", 0) > 0:
            return True
    sk = entry.get("structure_key", "") or ""
    return "Parallel(" in sk

indexed = {}
for i, entry in enumerate(data):
    if entry is None:
        continue
    indexed[str(i)] = {
        "structure_key": entry.get("structure_key"),
        "representative_pattern": entry.get("representative_pattern"),
        "has_parallel": entry_has_parallel(entry),
    }

OUT.write_text(json.dumps(indexed, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(indexed)} indexed entries to {OUT}")
