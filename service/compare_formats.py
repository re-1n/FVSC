"""Compare format_adapter (new MD) vs plain text on whitepaper retrieval quality."""
import httpx, sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.chdir(os.path.dirname(os.path.dirname(__file__)))

BASE = "http://127.0.0.1:8765"
client = httpx.Client(timeout=120)

with open("FVSC whitepaper.md", encoding="utf-8") as f:
    text = f.read()
print(f"Whitepaper: {len(text):,} chars\n")

# ── Ingest new MD (format_adapter) ──
client.post(f"{BASE}/spaces", json={"name": "md_new", "dim": 64})
t0 = time.time()
r = client.post(f"{BASE}/spaces/md_new/ingest", json={
    "text": text, "source_id": "wp", "format": "md",
})
md_data = r.json()
md_time = time.time() - t0
print(f"MD (format_adapter): {md_data['chunks_added']} chunks, {md_data['concepts_total']} concepts in {md_time:.1f}s")

# ── Ingest plain ──
client.post(f"{BASE}/spaces", json={"name": "plain_ref", "dim": 64})
t0 = time.time()
r = client.post(f"{BASE}/spaces/plain_ref/ingest", json={
    "text": text, "source_id": "wp", "format": "plain",
})
plain_data = r.json()
plain_time = time.time() - t0
print(f"PLAIN:               {plain_data['chunks_added']} chunks, {plain_data['concepts_total']} concepts in {plain_time:.1f}s")

print()

# ── Retrieval comparison ──
queries = [
    "энтропия фон нейман",
    "матрицы плотности",
    "полисемия",
    "контейнер",
    "сравнение карт смыслов",
    "временная динамика",
]

for query in queries:
    print(f'--- "{query}" ---')
    for space, label in [("md_new", "MD_new"), ("plain_ref", "PLAIN")]:
        r = client.post(f"{BASE}/spaces/{space}/retrieve", json={"query": query, "top_k": 2})
        if r.status_code != 200:
            print(f"  {label}: ERROR {r.status_code}")
            continue
        hits = r.json()["hits"]
        print(f"  {label} ({len(hits)} hits):")
        for h in hits[:2]:
            print(f"    [{h['score']:.2f}] {h['matched_concepts']}")
            snippet = h['text'][:150].replace('\n', ' ')
            print(f"    \"{snippet}...\"")
    print()

print("Done.")
