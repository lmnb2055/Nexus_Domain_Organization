# scripts/strip_subdomains_normalized.py
import glob, yaml
for p in glob.glob("papers/*.yaml"):
    with open(p, "r", encoding="utf-8") as f: doc = yaml.safe_load(f)
    if isinstance(doc, dict) and "subdomains_normalized" in doc:
        doc.pop("subdomains_normalized", None)
        with open(p, "w", encoding="utf-8") as f: yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)
        print("stripped:", p)
