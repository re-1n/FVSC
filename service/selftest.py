"""Self-retrieval test: ingest whitepaper into FVSC and query it."""
import httpx, sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.chdir(os.path.dirname(os.path.dirname(__file__)))

BASE = "http://127.0.0.1:8765"
client = httpx.Client(timeout=120.0)

# Create space
r = client.post(f"{BASE}/spaces", json={"name": "fvsc_docs", "dim": 64})
print("create:", r.status_code, r.json())

# Read whitepaper
with open("FVSC whitepaper.md", encoding="utf-8") as f:
    text = f.read()
print(f"whitepaper: {len(text):,} chars")

# Ingest
t0 = time.time()
r = client.post(f"{BASE}/spaces/fvsc_docs/ingest", json={
    "text": text,
    "source_id": "whitepaper",
    "format": "md",
})
data = r.json()
elapsed = time.time() - t0
print(f"ingest: {data['chunks_added']} chunks, {data['concepts_total']} concepts in {elapsed:.1f}s")

# Retrieve
for query in ["энтропия", "полиcемия", "матрицы плотности", "фон нейман"]:
    r = client.post(f"{BASE}/spaces/fvsc_docs/retrieve", json={
        "query": query,
        "top_k": 3,
    })
    if r.status_code != 200:
        print(f"retrieve '{query}': error {r.status_code} {r.text}")
        continue
    hits = r.json()["hits"]
    print(f"\nRetrieve '{query}': {len(hits)} hits")
    for h in hits:
        print(f"  [{h['score']:.2f}] {h['matched_concepts']}")
        print(f"    {h['text'][:200]}...")

print("\nDone.")
