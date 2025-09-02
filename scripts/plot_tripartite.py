# scripts/plot_tripartite.py
# Tripartite network: Domains → Subdomains → Indicators

import glob, yaml
from pathlib import Path
import matplotlib.pyplot as plt

# ---------- paths ----------
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
tax_path = ROOT / "taxonomy" / "domains.yaml"
papers_glob_yaml = str(ROOT / "papers" / "*.yaml")
papers_glob_yml  = str(ROOT / "papers" / "*.yml")

# output folder -> {repo_root}/plot/domain_subdomain_indicator.png
OUT_DIR = ROOT / "plot"
OUT_DIR.mkdir(parents=True, exist_ok=True)
img_path = OUT_DIR / "domain_subdomain_indicator.png"

# ---------- load taxonomy ----------
taxonomy = {}
if tax_path.exists():
    with open(tax_path, "r", encoding="utf-8") as f:
        taxonomy = yaml.safe_load(f) or {}
else:
    taxonomy = {"domains": []}

# domains / subdomains(from taxonomy)
domains = []
subdomains = []  # list[(domain, tail)]
for d in taxonomy.get("domains", []):
    dname = d.get("name")
    if not dname:
        continue
    domains.append(dname)
    for tail in d.get("subdomains", []) or []:
        if isinstance(tail, str):
            if tail.startswith(dname + "."):  # allow full key in taxonomy
                tail = tail[len(dname) + 1:]
            subdomains.append((dname, tail))

# ---------- collect indicators from papers ----------
indicator_to_domains = {}  # {indicator_name: set(domains)}
paper_files = sorted(list(glob.glob(papers_glob_yaml)) + list(glob.glob(papers_glob_yml)))

for p in paper_files:
    with open(p, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    p_domains = []
    if isinstance(doc.get("domains"), list):
        p_domains = [str(x).strip() for x in doc["domains"] if x]
    elif isinstance(doc.get("domain"), str):
        p_domains = [doc["domain"].strip()]

    inds = doc.get("indicators") or []
    if isinstance(inds, list):
        for it in inds:
            name = it.get("name") if isinstance(it, dict) else str(it)
            if not name:
                continue
            indicator_to_domains.setdefault(name, set()).update(p_domains)

indicators = sorted(indicator_to_domains.keys())

# ---------- build & draw ----------
# Try to use networkx if available
use_nx = True
try:
    import networkx as nx
except Exception:
    use_nx = False

if use_nx:
    G = nx.Graph()

    # nodes
    for d in sorted(set(domains)):
        G.add_node(f"D:{d}", layer=0, label=d)
    for d, tail in sorted(set(subdomains)):
        G.add_node(f"S:{d}.{tail}", layer=1, label=f"{d}.{tail}")
        G.add_edge(f"D:{d}", f"S:{d}.{tail}")
    for name, dset in sorted(indicator_to_domains.items(), key=lambda kv: kv[0].lower()):
        G.add_node(f"I:{name}", layer=2, label=name)
        for d in dset:
            if f"D:{d}" in G:
                G.add_edge(f"D:{d}", f"I:{name}")

    # layout: x=0 domains, x=1 subdomains, x=2 indicators
    def stack_positions(nodes, x):
        n = len(nodes)
        if n == 0: return {}
        ys = [i - (n-1)/2 for i in range(n)]
        return {nodes[i]: (x, ys[i]) for i in range(n)}

    dom_nodes = [n for n, data in G.nodes(data=True) if data.get("layer") == 0]
    sub_nodes = [n for n, data in G.nodes(data=True) if data.get("layer") == 1]
    ind_nodes = [n for n, data in G.nodes(data=True) if data.get("layer") == 2]

    pos = {}
    pos.update(stack_positions(sorted(dom_nodes), x=0.0))
    pos.update(stack_positions(sorted(sub_nodes), x=1.0))
    pos.update(stack_positions(sorted(ind_nodes), x=2.0))

    plt.figure(figsize=(16, max(6, len(dom_nodes)*0.4 + len(sub_nodes)*0.25 + len(ind_nodes)*0.12)))
    nx.draw_networkx_edges(G, pos, alpha=0.3, width=1.0)
    nx.draw_networkx_nodes(G, pos, nodelist=dom_nodes, node_size=800, alpha=0.9)
    nx.draw_networkx_nodes(G, pos, nodelist=sub_nodes, node_size=600, alpha=0.9)
    nx.draw_networkx_nodes(G, pos, nodelist=ind_nodes, node_size=600, alpha=0.9)
    labels = {n: G.nodes[n].get("label", n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(str(img_path), dpi=200, bbox_inches="tight")
    print(f"✅ Saved figure: {img_path}")

else:
    # fallback text layout
    plt.figure(figsize=(16, 9))
    x_positions = [0.1, 0.5, 0.9]
    for i, d in enumerate(sorted(set(domains))):
        plt.text(x_positions[0], 0.95 - i*0.05, d, ha="left", va="top", fontsize=10)
    for i, (d, tail) in enumerate(sorted(set(subdomains))):
        plt.text(x_positions[1], 0.95 - i*0.03, f"{d}.{tail}", ha="center", va="top", fontsize=8)
    for i, name in enumerate(indicators):
        plt.text(x_positions[2], 0.95 - i*0.02, name, ha="right", va="top", fontsize=8)
    plt.title("Domains — Subdomains — Indicators (aggregated)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(str(img_path), dpi=200, bbox_inches="tight")
    print(f"✅ Saved figure: {img_path}")
