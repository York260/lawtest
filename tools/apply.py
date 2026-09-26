"""把核對完的章節草稿合併進 data/questions.json，並重新產生 data/questions.js。

用法：python tools/apply.py ch4 [ch5 ...]
會先檢查：每題都有題目、四個選項、答案（A–D）。有問題就列出並停止，不會寫入。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bank_path = ROOT / "data" / "questions.json"
bank = json.load(open(bank_path, encoding="utf-8"))

problems, chapters = [], []
for cid in sys.argv[1:]:
    chap = json.load(open(ROOT / "work" / "final" / f"{cid}.json", encoding="utf-8"))
    for s in chap["sections"]:
        for q in s["questions"]:
            for k in [k for k in q if k.startswith("_")]:
                del q[k]
            if not q["question"]:
                problems.append(f"{q['id']} 沒有題目")
            if not set("ABCD") <= set(q["options"]) or not set(q["options"]) <= set("ABCDE") or not all(q["options"].values()):
                problems.append(f"{q['id']} 選項不完整")
            if not re.fullmatch(r"[ABCDE]{1,5}", q["answer"] or ""):
                problems.append(f"{q['id']} 答案不是 A–E：{q['answer']!r}")
            if not q.get("explanation"):
                q.pop("explanation", None)
    chapters.append(chap)

if problems:
    print("以下題目還沒修好，未寫入：")
    print("\n".join("  " + p for p in problems))
    sys.exit(1)

ids = {c["id"] for c in chapters}
bank["chapters"] = sorted([c for c in bank["chapters"] if c["id"] not in ids] + chapters, key=lambda c: c["chapter"])
json.dump(bank, open(bank_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
n = sum(len(s["questions"]) for c in chapters for s in c["sections"])
print(f"已合併 {', '.join(sorted(ids))}（{n} 題）進 data/questions.json")
subprocess.run([sys.executable, str(ROOT / "build.py")], check=True)
