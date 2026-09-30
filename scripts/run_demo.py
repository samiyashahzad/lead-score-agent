"""Fire all demo enquiries against the running API and print results."""
import json, httpx, sys

sys.stdout.reconfigure(encoding="utf-8")

with open("tests/demo_enquiries.json", encoding="utf-8") as f:
    demos = json.load(f)

base = "http://localhost:8000/qualify"
results = []

for i, demo in enumerate(demos, 1):
    label = demo["label"]
    body = demo["request"]
    print(f"\n{'='*60}")
    print(f"  [{i}/{len(demos)}] {label}")
    print(f"{'='*60}")
    print(f"  Company:  {body['company']}")
    print(f"  Inquiry:  {body['inquiry'][:80]}...")
    print()

    try:
        r = httpx.post(base, json=body, timeout=30)
        data = r.json()
        if r.status_code == 200:
            print(f"  Score:          {data['score']}")
            print(f"  Priority:       {data['priority']}")
            print(f"  Classification: {data['classification']}")
            print(f"  Confidence:     {data['confidence']}")
            print(f"  Next Action:    {data['next_action']}")
        else:
            print(f"  HTTP {r.status_code}: {json.dumps(data, indent=2)}")
        results.append({"label": label, "status": r.status_code, "response": data})
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"label": label, "status": "error", "response": str(e)})

print(f"\n{'='*60}")
print("  SUMMARY")
print(f"{'='*60}")
for res in results:
    if res["status"] == 200:
        d = res["response"]
        print(f"  {d['priority']:5s} | {d['score']:3d} | {d['classification']:14s} | {res['label']}")
    else:
        print(f"  ERR  | --- | {'':14s} | {res['label']}")
