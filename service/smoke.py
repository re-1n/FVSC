#!/usr/bin/env python3
"""Manual smoke test script — uses httpx to test the running FVSC service."""

import httpx
import time

BASE = "http://127.0.0.1:8765"

def main():
    # 1. Create space
    r = httpx.post(f"{BASE}/spaces", json={"name": "smoke", "dim": 32})
    assert r.status_code in (201, 409), f"create: {r.status_code}"
    print("1. Created space:", r.json())

    # 2. Ingest
    r = httpx.post(f"{BASE}/spaces/smoke/ingest", json={
        "text": "Свобода требует ответственности. Ответственность включает долг и мужество. Любовь дает свободу и требует терпения.",
        "source_id": "note1",
        "format": "plain",
    })
    assert r.status_code == 200, f"ingest: {r.status_code} {r.text}"
    data = r.json()
    assert data["chunks_added"] > 0, "no chunks added"
    assert data["concepts_total"] > 0, "no concepts"
    print(f"2. Ingested: {data['chunks_added']} chunks, {data['concepts_total']} concepts")

    # 3. Query contains
    r = httpx.get(f"{BASE}/spaces/smoke/concepts/свобода/contains?top_k=5")
    assert r.status_code == 200, f"contains: {r.status_code} {r.text}"
    contains = r.json()
    print(f"3. свобода contains: {contains}")

    # 4. Query polysemy
    r = httpx.get(f"{BASE}/spaces/smoke/concepts/свобода/polysemy")
    assert r.status_code == 200, f"polysemy: {r.status_code} {r.text}"
    print(f"4. свобода polysemy: {r.json()}")

    # 5. Report
    r = httpx.get(f"{BASE}/spaces/smoke/concepts/свобода/report")
    assert r.status_code == 200, f"report: {r.status_code} {r.text}"
    rep = r.json()
    assert rep["found"], f"concept not found in report: {rep}"
    print(f"5. Report: term={rep['term']}, components={rep['component_count']}, poly={rep['polysemy']}")
    print(f"   contains: {rep['contains']}")
    print(f"   contained_in: {rep['contained_in']}")

    # 6. Similarity
    r = httpx.get(f"{BASE}/spaces/smoke/similarity?a=свобода&b=ответственность")
    assert r.status_code == 200, f"similarity: {r.status_code} {r.text}"
    print(f"6. Similarity свобода-ответственность: {r.json()}")

    # 7. Retrieve
    r = httpx.post(f"{BASE}/spaces/smoke/retrieve", json={"query": "ответственность", "top_k": 3})
    assert r.status_code == 200, f"retrieve: {r.status_code} {r.text}"
    result = r.json()
    print(f"7. Retrieve 'ответственность': {len(result['hits'])} hits")
    for h in result["hits"]:
        print(f"   [{h['score']}] {h['source_id']}: {h['text'][:80]}...")

    # 8. Cross-space compare
    # Create second space with contrasting text
    httpx.post(f"{BASE}/spaces", json={"name": "smoke2", "dim": 32})
    httpx.post(f"{BASE}/spaces/smoke2/ingest", json={
        "text": "Свобода не требует ответственности. Свобода это одиночество. Ответственность разрушает свободу.",
        "source_id": "note2",
        "format": "plain",
    })
    r = httpx.get(f"{BASE}/compare?a=smoke&b=smoke2&top_k=10")
    assert r.status_code == 200, f"compare: {r.status_code} {r.text}"
    comp = r.json()
    print(f"8. Compare smoke vs smoke2:")
    print(f"   shared: {comp['shared_concepts']}")
    print(f"   divergent_count: {len(comp['divergent'])}")
    if comp["divergent"]:
        d0 = comp["divergent"][0]
        print(f"   first divergent: {d0.get('term', d0)}")

    # 9. Save + persistence check
    r = httpx.post(f"{BASE}/spaces/smoke/save")
    print(f"9. Save: {r.json()}")

    # 10. List spaces
    r = httpx.get(f"{BASE}/spaces")
    spaces = r.json()
    print(f"10. Spaces: {len(spaces)} total")
    for s in spaces:
        print(f"    {s['name']}: concepts={s.get('concept_count')}, chunks={s.get('chunk_count')}, _on_disk={s.get('_on_disk', False)}")

    # Cleanup test spaces
    httpx.delete(f"{BASE}/spaces/smoke")
    httpx.delete(f"{BASE}/spaces/smoke2")
    print("11. Cleaned up test spaces. All OK.")

if __name__ == "__main__":
    main()
