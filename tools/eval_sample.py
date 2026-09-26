"""用人工校對過的題庫（標準答案）評估 parse.py 的輸出準確率。

用法：python tools/eval_sample.py work/draft/ch2.json data/questions.json
"""
import difflib
import json
import re
import sys

draft = json.load(open(sys.argv[1], encoding="utf-8"))
gold = json.load(open(sys.argv[2], encoding="utf-8"))
G = {q["id"]: q for c in gold["chapters"] for s in c["sections"] for q in s["questions"]}
D = {q["id"]: q for c in draft.get("chapters", [draft]) for s in c["sections"] for q in s["questions"]}


def n(s):
    return re.sub(r"[\s，,。？?：:；;、（）()「」]", "", s)


def ratio(a, b):
    return difflib.SequenceMatcher(None, n(a), n(b), autojunk=False).ratio()


common = [k for k in G if k in D]
print(f"標準 {len(G)} 題，解析出 {len(D)} 題，對得上 {len(common)} 題")
ans_ok = sum(D[k]["answer"] == G[k]["answer"] for k in common)
stem = [ratio(D[k]["question"], G[k]["question"]) for k in common]
opts = [ratio(D[k]["options"][x], G[k]["options"][x]) for k in common for x in "ABCD"]
exact = sum(all(n(D[k]["options"][x]) == n(G[k]["options"][x]) for x in "ABCD") and n(D[k]["question"]) == n(G[k]["question"]) for k in common)
flagged = [k for k in common if D[k].get("_flags")]
bad = [k for k in common if min([ratio(D[k]["question"], G[k]["question"])] + [ratio(D[k]["options"][x], G[k]["options"][x]) for x in "ABCD"]) < 0.9]
print(f"答案正確 {ans_ok}/{len(common)}")
print(f"題幹平均相似度 {sum(stem)/len(stem):.3f}，選項平均相似度 {sum(opts)/len(opts):.3f}")
print(f"整題（題幹+四選項）完全正確 {exact}/{len(common)}")
print(f"被標為可疑 {len(flagged)} 題；明顯有錯（任一欄相似度<0.9）{len(bad)} 題，其中未被標出 {len([k for k in bad if k not in flagged])} 題")
for k in [k for k in bad if k not in flagged][:8]:
    print("  未標出：", k)
