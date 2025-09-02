#!/usr/bin/env python3
"""
Convert a CSV (domain, subdomain, indicator, paper) to a MarkMap Markdown and HTML.

Examples:
  # 最常見：專案根目錄下執行，會自動讀 plot/domain_subdomain_indicator.csv，輸出到 plot/
  python scripts/csv_to_markmap.py

  # 指定 CSV 與輸出資料夾
  python scripts/csv_to_markmap.py --csv plot/domain_subdomain_indicator.csv --out-dir plot

  # 自訂標題與 domain 排序（逗號分隔；未列到者自動排在後面；(none) 永遠最後）
  python scripts/csv_to_markmap.py --title "Exposome Mindmap" --domain-order chemical,physical,climate,social,built
"""

import argparse
from pathlib import Path
from textwrap import indent
import pandas as pd
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def _load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    # 欄位檢查
    req = ["domain", "subdomain", "indicator", "paper"]
    missing = [c for c in req if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    # 清理
    df = df.fillna("(none)")
    for col in req:
        df[col] = df[col].astype(str).str.strip()
    # 去重
    df = df.drop_duplicates().reset_index(drop=True)
    return df

def _domain_categories(df: pd.DataFrame, user_order: list[str] | None):
    present = [d for d in df["domain"].astype(str).unique()]
    if user_order and len(user_order) > 0:
        base = user_order
    else:
        base = ["chemical", "physical", "climate", "social", "built"]
    extras = sorted([d for d in present if d not in base and d != "(none)"])
    cats = base + extras + ["(none)"]
    return cats

def _sort_df(df: pd.DataFrame, user_order: list[str] | None) -> pd.DataFrame:
    cats = _domain_categories(df, user_order)
    df = df.copy()
    df["domain"] = pd.Categorical(df["domain"], categories=cats, ordered=True)
    return df.sort_values(["domain", "subdomain", "indicator", "paper"], kind="mergesort")

def build_markmap_markdown(df: pd.DataFrame, title: str = "Exposome Mindmap") -> str:
    parts = [f"# {title}", ""]
    for domain, g1 in df.groupby("domain", sort=False):
        parts.append(f"- {domain}")
        for sub, g2 in g1.groupby("subdomain", sort=True):
            parts.append(indent(f"- {sub}", "  "))
            for ind, g3 in g2.groupby("indicator", sort=True):
                parts.append(indent(f"- {ind}", "    "))
                papers = sorted(set(map(str, g3["paper"].tolist())))
                for p in papers:
                    parts.append(indent(f"- `{p}`", "      "))
    return "\n".join(parts)

def wrap_markmap_html(md_text: str, page_title: str = "Exposome Mindmap") -> str:
    safe_md = md_text.replace("</script>", "<\\/script>")
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>{page_title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body {{ height: 100%; margin: 0; background:#111; color:#eee; font-family: system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans", "Helvetica Neue", Arial; }}
    header {{ padding: 8px 12px; display:flex; gap:12px; align-items:center; border-bottom:1px solid #333; }}
    #wrap {{ height: calc(100% - 48px); }}
    #mindmap {{ width: 100%; height: 100%; }}
    select, button {{ background:#1b1b1b; color:#eee; border:1px solid #333; padding:6px 8px; border-radius:6px; }}
    .toolbar {{ margin-left:auto; display:flex; gap:8px; }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.17.2"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-toolbar@0.17.2/dist/index.umd.min.js"></script>
</head>
<body>
  <header>
    <strong>{page_title}</strong>
    <label>Domain:</label>
    <select id="domain">
      <option value="__all__">All</option>
    </select>
    <div class="toolbar" id="mm-toolbar"></div>
  </header>
  <div id="wrap">
    <svg id="mindmap"></svg>
  </div>

  <!-- 原始 Markdown 內文（供 JS 解析，不顯示） -->
  <script id="mm-md" type="text/markdown">
{safe_md}
  </script>

  <script>
  // 解析 Markdown -> 樹
  async function parseMarkdown(md) {{
    // 使用 markmap 的 autoloader已經掛載 window.markmap
    const {{ Transformer, Markmap }} = window.markmap;
    const transformer = new Transformer();
    const {{ root }} = transformer.transform(md);
    return {{ root, Markmap }};
  }}

  // 從 markdown 樹抓第一層（domain）節點清單
  function listDomains(root) {{
    const items = [];
    if (!root.children) return items;
    for (const c of root.children) {{
      if (c.type === 'heading' || c.depth === 1) continue;
      if (c.content) items.push(c.content);
    }}
    return items.sort();
  }}

  // 根據選取的 domain 產生子樹（__all__ = 原樹）
  function filterTreeByDomain(root, domain) {{
    if (domain === "__all__") return JSON.parse(JSON.stringify(root));
    const out = JSON.parse(JSON.stringify(root));
    out.children = (out.children || []).filter(c => c.content === domain);
    return out;
  }}

  (async () => {{
    const md = document.getElementById('mm-md').textContent;
    const {{ root, Markmap }} = await parseMarkdown(md);

    // 建立下拉選單
    const sel = document.getElementById('domain');
    const domains = listDomains(root);
    for (const d of domains) {{
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = d;
      sel.appendChild(opt);
    }}

    // 建立 SVG 與 Markmap
    const svg = document.getElementById('mindmap');
    const mm = Markmap.create(svg, {{ fit: true }}, root);

    // Toolbar
    if (window.markmap && window.markmap.Toolbar) {{
      const toolbar = new window.markmap.Toolbar();
      toolbar.attach(mm);
      document.getElementById('mm-toolbar').append(toolbar.render());
    }}

    // 切換 domain 時重新渲染
    sel.addEventListener('change', () => {{
      const dom = sel.value;
      const sub = filterTreeByDomain(root, dom);
      mm.setData(sub);
      mm.fit(); // 自動置中
    }});
  }})();
  </script>
</body>
</html>
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="Path to domain_subdomain_indicator.csv (若不提供，預設找 plot/domain_subdomain_indicator.csv)")
    ap.add_argument("--out-dir", default=str(ROOT / "plot"), help="輸出資料夾（預設：plot/）")
    ap.add_argument("--out-md", help="輸出 Markdown 檔名（預設：exposome_mindmap.md）")
    ap.add_argument("--out-html", help="輸出 HTML 檔名（預設：exposome_mindmap.html）")
    ap.add_argument("--title", default="Exposome Mindmap", help="心智圖標題")
    ap.add_argument("--domain-order", help="domain 排序（逗號分隔）。未列到者依字母序排在後面；(none) 永遠最後。")
    args = ap.parse_args()

    # CSV 路徑：未指定則找 plot/domain_subdomain_indicator.csv
    csv_path = Path(args.csv) if args.csv else (ROOT / "plot" / "domain_subdomain_indicator.csv")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_md = Path(args.out_md) if args.out_md else (out_dir / "exposome_mindmap.md")
    out_html = Path(args.out_html) if args.out_html else (out_dir / "exposome_mindmap.html")

    # domain 排序
    user_order = None
    if args.domain_order:
        user_order = [s.strip() for s in args.domain_order.split(",") if s.strip()]

    try:
        df = _load_csv(csv_path)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    df = _sort_df(df, user_order)
    md = build_markmap_markdown(df, title=args.title)
    out_md.write_text(md, encoding="utf-8")
    html = wrap_markmap_html(md, page_title=args.title)
    out_html.write_text(html, encoding="utf-8")

    print(f"✅ Saved Markdown: {out_md}")
    print(f"✅ Saved HTML:     {out_html}")
    print("👉 打開 HTML 檔即可在瀏覽器看到互動式心智圖（需要可連網以載入 markmap CDN）。")

if __name__ == "__main__":
    main()
