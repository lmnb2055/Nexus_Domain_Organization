# scripts/validate.py
import json, sys, glob
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCHEMA_PATH = ROOT / "schema" / "paper.schema.json"
TAXONOMY_PATH = ROOT / "taxonomy" / "domains.yaml"
print(f"Using schema: {SCHEMA_PATH.resolve()}")
print(f"Using taxonomy: {TAXONOMY_PATH.resolve()}")


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def iter_yaml_files():
    paths = sorted(list(glob.glob("papers/*.yaml")) + list(glob.glob("papers/*.yml")))
    for p in paths:
        yield Path(p)

def load_taxonomy():
    """
    產出：
      - allowed_domains: set[str]
      - allowed_subdomains_full: set[str]             # 'domain.tail' 形式
      - allowed_subdomains_by_domain: dict[str,set]   # domain -> set(tails)
    支援 taxonomy 兩種寫法：
      1) tail-only: e.g., {name: chemical, subdomains:[metals, airpollution.ambient]}
      2) full-key:  e.g., {name: chemical, subdomains:[chemical.metals, chemical.airpollution.ambient]}
    """
    t = load_yaml(TAXONOMY_PATH)
    allowed_domains = set()
    allowed_subdomains_full = set()
    allowed_subdomains_by_domain = {}

    for d in t.get("domains", []):
        dname = d.get("name")
        if not dname:
            continue
        allowed_domains.add(dname)
        tails = set()
        for s in d.get("subdomains", []) or []:
            s = str(s).strip()
            if not s:
                continue
            if s.startswith(dname + "."):  # full key
                allowed_subdomains_full.add(s)
                tails.add(s[len(dname) + 1:])
            else:
                tails.add(s)
                allowed_subdomains_full.add(f"{dname}.{s}")
        allowed_subdomains_by_domain[dname] = tails

    return {
        "allowed_domains": allowed_domains,
        "allowed_subdomains_full": allowed_subdomains_full,
        "allowed_subdomains_by_domain": allowed_subdomains_by_domain,
    }

def normalize_paper_domains(doc):
    ds = set()
    if "domains" in doc and isinstance(doc["domains"], list):
        ds.update([str(x).strip() for x in doc["domains"] if x])
    if "domain" in doc and isinstance(doc["domain"], str):
        ds.add(doc["domain"].strip())
    return ds

def normalize_paper_subdomains(doc):
    """
    只回傳 'domain.tail' 形式的鍵；群組鍵（如 'chemical'）一律忽略，不檢查。
    """
    keys_full = set()
    mapping = {}

    val = doc.get("subdomains")
    if isinstance(val, dict):
        for k, v in val.items():
            k = str(k).strip()
            mapping[k] = v
            if "." in k:
                keys_full.add(k)
    elif isinstance(val, list):
        for k in val:
            k = str(k).strip()
            mapping[k] = None
            if "." in k:
                keys_full.add(k)
    elif isinstance(doc.get("subdomain"), str):
        k = doc["subdomain"].strip()
        mapping[k] = None
        if "." in k:
            keys_full.add(k)

    return keys_full, mapping

def validate_against_schema(path: Path, doc, schema):
    v = Draft202012Validator(schema)
    errs = [f"{path}: {e.message}" for e in v.iter_errors(doc)]
    return errs

def validate_domains_and_subdomains(path: Path, doc, tax):
    errs = []
    allowed_domains = tax["allowed_domains"]
    allowed_subdomains_full = tax["allowed_subdomains_full"]
    allowed_subdomains_by_domain = tax["allowed_subdomains_by_domain"]

    paper_domains = normalize_paper_domains(doc)
    if not paper_domains:
        errs.append(f"{path}: missing 'domains' (or legacy 'domain').")
    else:
        for d in paper_domains:
            if d not in allowed_domains:
                errs.append(f"{path}: domain '{d}' not in taxonomy (allowed: {sorted(allowed_domains)}).")

    sub_full_keys, sub_map = normalize_paper_subdomains(doc)
    # 群組鍵已被忽略；現在僅檢查 dotted key
    for key in sub_full_keys:
        domain_prefix = key.split(".", 1)[0]
        if domain_prefix not in paper_domains:
            errs.append(f"{path}: subdomain '{key}' has domain '{domain_prefix}' not listed in 'domains'.")
        if key not in allowed_subdomains_full:
            errs.append(f"{path}: subdomain '{key}' not in taxonomy.")

        # 值的型別輕度檢查（常見：list/str/dict）
        val = sub_map.get(key)
        if val is not None and not isinstance(val, (list, tuple, set, dict, str, int, float)):
            errs.append(f"{path}: subdomain '{key}' value should be list/str/dict/number; got {type(val).__name__}.")

    return errs

def main():
    if not SCHEMA_PATH.exists():
        print(f"❌ Schema not found: {SCHEMA_PATH}")
        sys.exit(1)
    if not TAXONOMY_PATH.exists():
        print(f"❌ Taxonomy not found: {TAXONOMY_PATH}")
        sys.exit(1)

    schema = load_yaml(SCHEMA_PATH)
    taxonomy = load_taxonomy()

    files = list(iter_yaml_files())
    if not files:
        print("⚠️ No YAML files under papers/")
        sys.exit(1)

    all_errors = []
    for path in files:
        try:
            doc = load_yaml(path)
        except Exception as e:
            all_errors.append(f"{path}: cannot read YAML ({e})")
            continue

        # Schema 驗證
        all_errors.extend(validate_against_schema(path, doc, schema))
        # Domain/Subdomain 驗證（僅 dotted key）
        all_errors.extend(validate_domains_and_subdomains(path, doc, taxonomy))

    if all_errors:
        print("VALIDATION FAILED:")
        for e in all_errors:
            print(" -", e)
        sys.exit(1)

    print("✅ All papers passed validation.")

if __name__ == "__main__":
    main()
