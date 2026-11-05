"""
Regenerates data/questionnaires.json from the hospital's seed_proms.py, so this
backend asks exactly what the nurse asks on the pre-visit call. Run it again
after changing an instrument in the hospital repo:

    python scripts/export_questionnaires.py

Only reads seed_proms.CONFIGS; importing it does not connect to any database.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOSPITAL_BACKEND = ROOT.parent / "orthopedic-opd-ai-test" / "backend"

sys.path.insert(0, str(HOSPITAL_BACKEND))
import seed_proms  # noqa: E402

output = {cfg["bodyArea"]: cfg for cfg in seed_proms.CONFIGS}
path = ROOT / "data" / "questionnaires.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(output)} questionnaires to {path}")
