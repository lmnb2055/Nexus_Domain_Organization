# scripts/sync_taxonomy.py
import argparse
import glob
import os
from pathlib import Path
from typing import Dict, Set, Tuple

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_TAX_PATH = ROOT / "taxonomy" / "domains.yaml"
DEFAULT_PAPERS_GLOB = str(ROOT / "papers" / "*.yaml")


def load_yaml(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def ensure_taxonomy_struct(tax) -> Tuple[dict, Dict[str, dict]]:
    """
    正規化 taxonomy 結構並建立 domain 索引。
    結構：
      {
        version: 1,
        domains: [
          { name: <domain>, subdomains: [<tail1>, <tail2>, ...] }
        ]
      }
    """
    if not isinstance(tax, dict):
        tax = {}
    tax.setdefault("version", 1)
    tax.setdefault("domains", [])
    idx = {}
    # 允許 subdomains 缺漏或是 None
    for d in tax["domains"]:
        if not isinstance(d, dict):
            continue
        name = d.get("name")
        if not name:
            continue
        d.setdefault("subdomains", [])
        if not isinstance(d["subdomains"], list):
            d["subdomains"] = []
        idx[name] = d
    return tax, idx


def collect_from_papers(glob_pattern: str) -> Tuple[Set[str], Set[str]]:
    """回傳 (dotted_subdomains, domains_used)"""
    dotted = set()
    domains_used = set()

    # 同時支援 .yaml / .yml
    paths = sorted(list(glob.glob(glob_pattern)) + list(glob.glob(glob_pattern.replace("*.yaml", "*.yml"))))
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
        except Exception as e:
            print(f"⚠️ 跳過 {path}: {e}")
            continue

        if not isinstance(doc, dict):
            continue

        # 收集 domains
        if isinstance(doc.get("domains"), list):
            for x in doc["domains"]:
                if x:
                    domains_used.add(str(x).strip())
        if isinstance(doc.get("domain"), str):
            domains_used.add(doc["domain"].strip())

        # 收集 subdomains（只收點號鍵）
        subs = doc.get("subdomains")
        if isinstance(subs, dict):
            for k in subs.keys():
                k = str(k).strip()
                if "." in k:
                    dotted.add(k)
        elif isinstance(subs, list):
            for k in subs:
                k = str(k).strip()
                if "." in k:
                    dotted.add(k)
        elif isinstance(doc.get("subdomain"), str):
            k = doc["subdomain"].strip()
            if "." in k:
                dotted.add(k)

    return dotted, domains_used


def sync_taxonomy(
    tax_path: Path,
    papers_glob: str,
    write_full_keys: bool = False,
    dry_run: bool = False,
):
    # 載入/建立 taxonomy
    base = load_yaml(tax_path) or {"version": 1, "domains": []}
    tax, idx = ensure_taxonomy_struct(base)

    # 掃描 papers
    dotted, domains_used = collect_from_papers(papers_glob)

    added_domains = []
    added_subs = []

    # 先確保所有使用到的 domain 都存在
    for d in sorted(domains_used):
        if d not in idx:
            node = {"name": d, "subdomains": []}
            tax["domains"].append(node)
            idx[d] = node
            added_domains.append(d)

    # 將每個 dotted key 寫回 taxonomy
    for full in sorted(dotted):
        domain, tail = full.split(".", 1)
        if domain not in idx:
            node = {"name": domain, "subdomains": []}
            tax["domains"].append(node)
            idx[domain] = node
            added_domains.append(domain)

        subs = idx[domain].setdefault("subdomains", [])

        # two styles: store tail (default) or full key (optional)
        token = full if write_full_keys else tail

        if token not in subs:
            subs.append(token)
            added_subs.append(f"{domain}.{tail}")

    # 去重＆排序
    seen = set()
    ordered_domains = []
    for d in tax["domains"]:
        name = d.get("name")
        if name in seen:
            continue
        seen.add(name)
        # 去重 subdomains
        if isinstance(d.get("subdomains"), list):
            dedup = list(dict.fromkeys(d["subdomains"]))
            d["subdomains"] = sorted(dedup, key=lambda s: str(s).lower())
        ordered_domains.append(d)
    tax["domains"] = sorted(ordered_domains, key=lambda x: x.get("name", ""))

    # 輸出或 dry-run
    if dry_run:
        print("---- Dry run (未寫入) ----")
    else:
        dump_yaml(tax_path, tax)

    # 摘要
    print(f"Taxonomy 檔案: {tax_path}")
    print(f"掃描路徑:       {papers_glob}")
    print(f"新增 domains:   {len(added_domains)} -> {added_domains if added_domains else '—'}")
    print(f"新增 subdomains:{len(added_subs)} -> {added_subs if added_subs else '—'}")
    if write_full_keys:
        print("※ subdomains 以『完整鍵』寫入（e.g. chemical.metals）")
    else:
        print("※ subdomains 以『尾碼』寫入（e.g. metals）")


def parse_args():
    p = argparse.ArgumentParser(description="Sync taxonomy/domains.yaml from papers/*.yaml")
    p.add_argument(
        "--tax-path",
        type=Path,
        default=DEFAULT_TAX_PATH,
        help="taxonomy/domains.yaml 路徑（預設：taxonomy/domains.yaml）",
    )
    p.add_argument(
        "--papers-glob",
        type=str,
        default=DEFAULT_PAPERS_GLOB,
        help="要掃描的 papers 檔案路徑 glob（預設：papers/*.yaml）",
    )
    p.add_argument(
        "--full-keys",
        action="store_true",
        help="將 subdomains 以完整鍵寫入 taxonomy（預設寫入尾碼）。",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示將進行的變更，不寫回檔案。",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sync_taxonomy(
        tax_path=args.tax_path,
        papers_glob=args.papers_glob,
        write_full_keys=args.full_keys,
        dry_run=args.dry_run,
    )
