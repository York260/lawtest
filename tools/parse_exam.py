"""解析單欄排版的考卷（如警察大學入學考試／警佐班試題）。
用法：python tools/parse_exam.py <key> <first> <last>   → work/exam/<key>.json
題號行：行首為「N.」且 N 為下一個預期題號；選項以 (A)…(E) 標記依序切開。"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import parse

ROOT = Path(__file__).resolve().parent.parent
Q_RE = re.compile(r"^(\d{1,2})\s*[\.．,]?\s*(.*)")
Q_BAD = re.compile(r"^[$S§sIl|Oo]\s*[\.．]\s*(.*)")
MARK = re.compile(r"[\(（]\s*([A-E])\s*[\)）]")


def split_opts(s):
    ms = list(MARK.finditer(s))
    pos, want = [], "A"
    for m in ms:
        if m.group(1) == want:
            pos.append(m); want = chr(ord(want) + 1)
    if len(pos) < 4:
        return None
    stem = s[:pos[0].start()]
    opts = {}
    for i, m in enumerate(pos):
        e = pos[i + 1].start() if i + 1 < len(pos) else len(s)
        opts[m.group(1)] = s[m.end():e]
    return stem, opts


def clean(t):
    t = parse.normalize(t)
    t = re.sub(r"[。．.]+$", "", t)
    return t.strip("，、 ")


def run(key, first, last):
    parse.TOPCUT = 0.04
    lines = []
    for p in range(first, last + 1):
        for l in parse.load_lines(p):
            l["page"] = p
            lines.append(l)
    txt = [(parse.text_of(l), l) for l in lines]
    qs, cur, expect = [], None, 1
    for t, l in txt:
        m = Q_RE.match(t)
        if not (m and int(m.group(1)) == expect):
            m = Q_BAD.match(t) if (cur is None or l["left"] <= cur["left"] + 8) else None
            if m:
                class _M:  # 題號被誤認成符號
                    def group(self, i, g=m): return str(expect) if i == 1 else g.group(1)
                m = _M()
        if m and int(m.group(1)) == expect and (cur is None or l["left"] <= cur["left"] + 25):
            cur = {"n": expect, "parts": [m.group(2)], "left": l["left"], "pages": {l["page"]}}
            qs.append(cur); expect += 1
        elif cur is not None:
            if re.match(r"^[一二三四五六七八九]、", t) or re.fullmatch(r"\d{1,3}", t):
                continue
            cur["parts"].append(t); cur["pages"].add(l["page"])
    out = []
    for q in qs:
        raw = "".join(q["parts"])
        r = split_opts(raw)
        item = {"n": q["n"], "pages": sorted(q["pages"])}
        if r:
            stem, o = r
            item["question"] = clean(stem)
            item["options"] = {k: clean(v) for k, v in o.items()}
            bad = [k for k, v in item["options"].items() if not v]
            if bad or not item["question"]:
                item["flag"] = "空白"
        else:
            item["question"] = clean(raw); item["options"] = {}; item["flag"] = "切不出選項"
        out.append(item)
    (ROOT / "work" / "exam").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(ROOT / "work" / "exam" / f"{key}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fl = [q["n"] for q in out if q.get("flag")]
    print(key, "題數", len(out), "有問題", fl)


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
