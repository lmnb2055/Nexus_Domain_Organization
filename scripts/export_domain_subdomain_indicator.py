# scripts/export_domain_subdomain_indicator.py
"""
將 repo 內的資料整理成一張 CSV：
domain, subdomain, indicator, paper

- 掃描來源：
  - taxonomy/domains.yaml（可無）
  - papers/*.yaml, *.yml
- 產出：
  - plot/domain_subdomain_indicator.csv  (預設)
- 使用方式：
  python scripts/export_domain_subdomain_indicator.py
  python scripts/export_domain_subdomain_indicator.py --out figures/dsi.csv
  python scripts/export_domain_subdomain_indicator.py --only-dotted   # 僅輸出有點號的 subdomain
"""

import argparse
import glob
from pathlib import Path
import yaml
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAPERS_GLOB_YAML = str(ROOT / "papers" / "*.yaml")
PAPERS_GLOB_YML  = str(ROOT / "papers" / "*.yml")

# 你指定的固定排序
DOMAIN_ORDER = ["chemical", "physical", "climate", "social", "built"]

def load_yaml(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def _normalize_indicator_item(it):
    # 支援 list[str] 或 list[dict{name: ...}]
    if isinstance(it, dict):
        name = it.get("name")
        return str(name).strip() if name else None
    return str(it).strip() if str(it).strip() else None

def collect_rows(only_dotted: bool = False):
    rows = []
    paper_files = sorted(list(glob.glob(PAPERS_GLOB_YAML)) + list(glob.glob(PAPERS_GLOB_YML)))

    for p in paper_files:
        paper_id = Path(p).stem
        doc = load_yaml(Path(p)) or {}
        if not isinstance(doc, dict):
            continue

        # domains
        p_domains = []
        if isinstance(doc.get("domains"), list):
            p_domains = [str(x).strip() for x in doc["domains"] if str(x).strip()]
        elif isinstance(doc.get("domain"), str):
            p_domains = [doc["domain"].strip()]
        # 落空處理
        if not p_domains:
            p_domains = ["(none)"]

        # subdomains：允許 dict / list / 單字串
        # 若為 dict，順便把 value 當作該 subdomain 的 indicators 來源
        subdomain_to_inds = {}  # k: subdomain, v: list[indicator]
        subs = doc.get("subdomains")
        if isinstance(subs, dict):
            for k, v in subs.items():
                s = str(k).strip()
                if not s:
                    continue
                # value 可能是 list[str] 或 list[dict{name}]
                inds_list = []
                if isinstance(v, list):
                    for it in v:
                        nm = _normalize_indicator_item(it)
                        if nm:
                            inds_list.append(nm)
                # 若 value 不是 list，略過（保持空清單）
                subdomain_to_inds[s] = inds_list
        elif isinstance(subs, list):
            for k in subs:
                s = str(k).strip()
                if s:
                    subdomain_to_inds[s] = []
        elif isinstance(doc.get("subdomain"), str):
            s = doc["subdomain"].strip()
            if s:
                subdomain_to_inds[s] = []

        # 頂層 indicators（保留相容）
        top_inds = []
        inds = doc.get("indicators") or []
        if isinstance(inds, list):
            for it in inds:
                nm = _normalize_indicator_item(it)
                if nm:
                    top_inds.append(nm)

        # only_dotted：只留帶點號 subdomain
        if only_dotted and subdomain_to_inds:
            subdomain_to_inds = {k: v for k, v in subdomain_to_inds.items() if "." in k}

        # 若完全沒 subdomain，至少放一個佔位
        if not subdomain_to_inds:
            subdomain_to_inds = {"(none)": []}

        # 將 domain/subdomain 對齊：只保留「subdomain 前綴對應的 domain」
        aligned_pairs = []
        for d in p_domains:
            matched = [s for s in subdomain_to_inds.keys() if s == "(none)" or s.startswith(d + ".")]
            if not matched:
                matched = ["(none)"]
            for s in matched:
                aligned_pairs.append((d, s))

        # 每個 pair 產生列；indicator 以 subdomain 的 list 為優先，若為空則回退用頂層 indicators；再不然 "(none)"
        for d, s in aligned_pairs:
            inds_here = subdomain_to_inds.get(s, [])
            if not inds_here:
                inds_here = top_inds[:] if top_inds else ["(none)"]
            for ind in inds_here:
                rows.append({
                    "domain": d,
                    "subdomain": s,
                    "indicator": ind,
                    "paper": paper_id
                })

    return rows

def sort_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 基礎優先順序（你原本的五大類）
    base = ["chemical", "physical", "climate", "social", "built"]

    # 目前資料中實際出現的所有 domain
    present = [d for d in df["domain"].astype(str).unique()]

    # 把除了 base 與 "(none)" 以外的其餘 domain 依字母序排在後面
    extras = sorted([d for d in present if d not in base and d != "(none)"])

    # "(none)" 永遠放最後
    categories = base + extras + ["(none)"]

    df["domain"] = pd.Categorical(df["domain"], categories=categories, ordered=True)
    df = df.sort_values(["domain", "subdomain", "indicator", "paper"], kind="mergesort")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default=str(ROOT / "plot" / "domain_subdomain_indicator.csv"),
                        help="輸出 CSV 路徑（預設：plot/domain_subdomain_indicator.csv）")
    parser.add_argument("--only-dotted", action="store_true",
                        help="只輸出帶點號的 subdomain（忽略 'chemical' 這種群組鍵）")
    args = parser.parse_args()

    rows = collect_rows(only_dotted=args.only_dotted)
    df = pd.DataFrame(rows, columns=["domain", "subdomain", "indicator", "paper"])

    # 去重 & 排序
    df = df.drop_duplicates().reset_index(drop=True)
    df = sort_frame(df)

    out_path = Path(args.out)
    ensure_parent(out_path)
    df.to_csv(out_path, index=False)
    print(f"✅ CSV saved: {out_path}  ({len(df)} rows)")

    # 預覽
    with pd.option_context("display.max_rows", 20, "display.max_columns", 10, "display.width", 120):
        print(df.head(20))

if __name__ == "__main__":
    main()
