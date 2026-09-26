"""解析國家考試單選測驗題（題號在左、選項縮排；選項標記 OCR 常亂，沿用 parse.split_options 的容錯切法）。
用法：python tools/parse_natl.py <key> <first> <last>  → work/exam/<key>.json"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import parse

ROOT = Path(__file__).resolve().parent.parent


def run(key, first, last):
    parse.TOPCUT = 0.03
    lines = []
    for p in range(first, last + 1):
        for l in parse.load_lines(p):
            l["page"] = p; lines.append(l)
    txt = [(parse.text_of(l), l) for l in lines]
    start = next((i for i, (t, l) in enumerate(txt) if "測驗題部分" in t), None)
    if start is not None:
        i = start + 1
        while i < len(txt) and (txt[i][0].startswith(("(", "（", "己共", "共")) or "選擇題" in txt[i][0] or "2B" in txt[i][0] or "作答者" in txt[i][0]):
            i += 1
        txt = txt[i:]
    body_left = sorted(l["left"] for t, l in txt)[len(txt) // 2] if txt else 250
    qs, cur, expect = [], None, 1
    for t, l in txt:
        if re.match(r"^(頁次|代號)", t) or re.fullmatch(r"[\d\-:\s]{1,12}", t):
            continue
        m = re.match(r"^(\d{1,2})(?!\d)\s*[\.．]?\s*(.*)", t)
        if m and int(m.group(1)) == expect and l["left"] < body_left - 30:
            cur = {"n": expect, "parts": [m.group(2)], "pages": {l["page"]}}
            qs.append(cur); expect += 1
        elif cur is not None:
            cur["parts"].append(t); cur["pages"].add(l["page"])
    out = []
    for q in qs:
        raw = parse.normalize("".join(q["parts"]))
        item = {"n": q["n"], "pages": sorted(q["pages"])}
        sp = parse.split_options(raw, 4)
        if sp:
            stem, o, score = sp
            item["question"] = parse.clean_stem(stem)
            item["options"] = {k: parse.clean_option(v, k) for k, v in o.items()}
            item["score"] = round(score, 2)
            if any(not v for v in item["options"].values()) or score < 0.75:
                item["flag"] = "選項不確定"
        else:
            item["question"] = raw; item["options"] = {}; item["flag"] = "切不出選項"
        out.append(item)
    (ROOT / "work" / "exam").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(ROOT / "work" / "exam" / f"{key}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(key, "題數", len(out), "flag", [q["n"] for q in out if q.get("flag")])


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
