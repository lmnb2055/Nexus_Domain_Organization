# scripts/debug_schema.py
import json, re
from pathlib import Path

p = Path("schema/paper.schema.json")
print("Load:", p.resolve())
schema = json.loads(p.read_text(encoding="utf-8"))

sub = schema["properties"]["subdomains"]
patts = list((sub.get("patternProperties") or {}).keys())
print("patternProperties keys:", patts)
print("additionalProperties on subdomains:", sub.get("additionalProperties"))

# 檢查 Conceptual 分支是否「已移除 enum」
oneofs = schema["properties"]["data"]["oneOf"]
conceptual = oneofs[0]["properties"]
print("Conceptual.study_type:", conceptual["study_type"])

print("\n判斷：")
ok_relaxed = any(re.fullmatch(r"^[a-zA-Z0-9]+$", k) for k in patts) and sub.get("additionalProperties") == True
print("  subdomains 放寬：", "✅" if ok_relaxed else "❌")
print("  study_type 是自由文字：", "✅" if conceptual["study_type"].get("enum") is None else "❌")
