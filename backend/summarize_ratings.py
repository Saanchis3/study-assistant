import csv
import sys
from collections import Counter, defaultdict

filename = sys.argv[1]

with open(filename, newline="", encoding="utf-8-sig") as f:
    rows = [
        r for r in csv.DictReader(f)
        if r["correct"].strip() in ("0", "1")
        and r["useful"].strip() in ("0", "1")
    ]

if not rows:
    print("No rated rows found. Fill in the 'correct' and 'useful' columns with 0 or 1.")
    sys.exit(1)


def report(label, group):
    n = len(group)
    correct = sum(int(r["correct"]) for r in group)
    useful = sum(int(r["useful"]) for r in group)
    both = sum(
        1 for r in group
        if r["correct"] == "1" and r["useful"] == "1"
    )

    print(
        f"{label}: {n} cards | "
        f"correct {correct/n:.0%} | "
        f"useful {useful/n:.0%} | "
        f"both {both/n:.0%}"
    )


print("=== Overall ===")
report("All", rows)

print("\n=== By prompt version ===")
by_version = defaultdict(list)

for r in rows:
    by_version[r["prompt_version"]].append(r)

for v, group in sorted(by_version.items()):
    report(v, group)

print("\n=== By card type ===")
by_type = defaultdict(list)

for r in rows:
    by_type[r["card_type"]].append(r)

for t, group in sorted(by_type.items()):
    report(t, group)

print("\n=== Most common problems ===")
problems = Counter(
    r["problem"].strip().lower()
    for r in rows
    if r["problem"].strip()
)

for tag, count in problems.most_common():
    print(f"  {tag}: {count}")