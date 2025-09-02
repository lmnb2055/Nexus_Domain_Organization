# scripts/migrate_subdomains.py
import glob, yaml, re, os

# 簡單關鍵字 → dotted subdomain 映射（可自行擴充）
RULES = [
    (r"\bpm2\.?5\b|\bno2\b|air\s*pollution|ambient", "chemical.airpollution.ambient"),
    (r"\blead\b|\bpb\b|mercury|hg|cadmium|cd|arsenic|as|molybdenum", "chemical.metals"),
    (r"pfas|pfoa|pfos|pfhxs|pfna|pfunda", "chemical.persistent"),
    (r"pcb|pbde|ddt|dde|hcb|organochlor", "chemical.persistent"),
    (r"phthalate|dehp|mbzp|mibp|mnbp", "chemical.phthalates"),
    (r"phenol|bisphenol|bpa|paraben|triclosan", "chemical.phenols"),
    (r"\bnoise\b|dnl|l\w?night", "physical.noise"),
    (r"temperature\b|heat|cold|humidity|meteorolog", "climate.meteorological"),
    (r"extreme|wildfire|drought|heatwave|cold\s*snap", "climate.extremes"),
    (r"ndvi|green\s*space|blue\s*space|park|greenness", "built.environment"),
    (r"walkability|connectivity|building\s*density|urban\s*design|land\s*use|traffic", "built.struct.urbandesign"),
    (r"bus|transit|access\b", "built.access"),
    (r"microbiome|16s|shotgun", "biological.microbiome"),
    (r"omics|genomic|epigenomic|transcriptomic|proteomic|metabolomic", "biological.omics"),
    (r"smok|alcohol|diet|physical\s*activity|folic", "social.lifestyle"),
    (r"demographic|cultur", "social.cultural.demographics"),
    (r"stress|inequity|injustice|allostatic", "social.economic.stressors"),
]

def guess_key(item: str):
    s = item.lower()
    for pat, key in RULES:
        if re.search(pat, s):
            return key
    return None

def ensure_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

def main():
    for path in sorted(glob.glob("papers/*.yaml")):
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        subs = doc.get("subdomains")
        if not isinstance(subs, dict):
            continue

        normalized = {}
        # 支援兩種寫法：{domainGroup: [...] } 或 { dotted.key: [...] }
        for k, v in subs.items():
            items = ensure_list(v)
            if "." in k:
                # 已是 dotted，直接複製
                normalized.setdefault(k, [])
                normalized[k].extend(items)
            else:
                # 群組鍵，逐項嘗試分類
                for it in items:
                    it_str = str(it)
                    key = guess_key(it_str)
                    if key:
                        normalized.setdefault(key, [])
                        normalized[key].append(it)
                    else:
                        # 放入一個待人工處理的 bucket
                        normalized.setdefault(f"{k}.UNMAPPED", [])
                        normalized[f"{k}.UNMAPPED"].append(it)

        # 去重與排序（可選）
        for k in list(normalized.keys()):
            vals = []
            seen = set()
            for x in normalized[k]:
                xs = str(x)
                if xs not in seen:
                    seen.add(xs)
                    vals.append(x)
            normalized[k] = sorted(vals, key=lambda z: str(z).lower())

        # 寫回：新增 subdomains_normalized，不覆蓋原本 subdomains
        doc["subdomains_normalized"] = dict(sorted(normalized.items()))
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)

        print(f"✔ Migrated preview added to {os.path.basename(path)} (subdomains_normalized).")

if __name__ == "__main__":
    main()
