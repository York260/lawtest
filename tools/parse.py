"""把 OCR 結果依 structure.json 切成題目，配上答案表，輸出草稿題庫與檢查報告。

用法：
  python tools/parse.py                 # 產生 work/draft.json、work/report.md、答案表裁圖
  python tools/parse.py --apply         # 另外把草稿合併進 data/questions.json（同 id 的章節會被取代）

版面假設（這本書的排版）：
- 題號凸出在左邊（懸掛縮排），續行的文字對齊在題號右邊 → 用行的左邊界判斷新題開始，並丟掉題號本身
- 每回題目結束後是「本回解答」表格（一行多個 N.(X)）→ 裁圖後用英文模式辨識
- 答案表之後若有「第N題」獨立成行，視為該題的疑點解析
"""
import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import pymupdf  # noqa: F401  (確保環境一致；裁圖用 PIL 較簡單)
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
KEYS = "ABCDE"
LOWCONF = float(__import__("os").environ.get("LOWCONF", 20))  # 低於此信心值的中文字列為可疑
MEANCONF = float(__import__("os").environ.get("MEANCONF", 80))

# ---------- 讀 TSV ----------


def load_lines(pno):
    """回傳該頁的文字行：[{top,bottom,left,right,words:[{text,left,right,conf}]}]，已去掉頁首。"""
    path = WORK / "ocr" / f"p{pno:04d}.tsv"
    rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    height = int(rows[0]["height"])
    lines = {}
    for r in rows:
        if r["level"] != "5" or not (r["text"] or "").strip():
            continue
        k = (r["block_num"], r["par_num"], r["line_num"])
        left, top = int(r["left"]), int(r["top"])
        w = {"text": r["text"].strip(), "left": left, "right": left + int(r["width"]),
             "top": top, "bottom": top + int(r["height"]), "conf": float(r["conf"])}
        lines.setdefault(k, []).append(w)
    out = []
    for ws in lines.values():
        ln = {"words": ws, "left": min(w["left"] for w in ws), "right": max(w["right"] for w in ws),
              "top": min(w["top"] for w in ws), "bottom": max(w["bottom"] for w in ws), "page": pno}
        if ln["top"] < height * 0.11:  # 頁首（Chapter X 章名 / 警察法規 頁碼）
            continue
        out.append(ln)
    out.sort(key=lambda l: l["top"])
    return out


def text_of(ln, min_center=None):
    s = ""
    for w in ln["words"]:
        if min_center is not None and (w["left"] + w["right"]) / 2 < min_center:
            continue
        s += w["text"]
    return s


CJK = re.compile(r"[一-鿿]")


def is_answer_row(s):
    n = s.count("(") + s.count("（")
    return (n >= 4 and len(CJK.findall(s)) < len(s) * 0.5 and len(s) >= 12) or n >= 7


def body_left(lines):
    """續行文字的左邊界。把行首位置分群（相差 12px 內算同一群），取最大的兩群中偏右的那群。"""
    lefts = sorted(l["left"] for l in lines if len(text_of(l)) >= 3)
    if not lefts:
        return 0
    groups = [[lefts[0]]]
    for x in lefts[1:]:
        if x - groups[-1][-1] <= 12:
            groups[-1].append(x)
        else:
            groups.append([x])
    top2 = sorted(groups, key=len, reverse=True)[:2]
    body = max(top2, key=lambda g: g[0])
    return sorted(body)[len(body) // 2]


def is_start(l):
    """題號凸出在左邊：行首比續行左邊界往左 20–85px。"""
    return 20 <= l["L"] - l["left"] <= 85


# ---------- 文字正規化 ----------

PUNCT = {",": "，", "?": "？", ":": "：", ";": "；", "!": "！", "﹔": "；", "‧": "", "_": "", "|": "",
         "“": "", "”": "", "\"": "", "'": "", "`": "", "~": ""}


FIXES = {k: v for k, v in json.load(open(Path(__file__).with_name("fixes.json"), encoding="utf-8")).items()
         if not k.startswith("_")}


def normalize(s):
    s = re.sub(r"\s+", "", s)
    for a, b in FIXES.items():
        s = s.replace(a, b)
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    s = re.sub(r"(?<=[一-鿿])\.(?=[一-鿿]|$)", "。", s)
    s = s.replace("(", "（").replace(")", "）")
    return s


# ---------- 切選項 ----------

# 選項標記 (A)(B)(C)(D) 是斜體，常被認錯：(8 ($W (0 (Go GB 0 …，甚至只剩「（」或只剩「0」。
# 所以主要靠「一定依 A→B→C→D 的順序出現」來挑，字母只當加分參考。
LETTER_HINT = {"A": "Aa", "B": "Bb", "C": "Cc", "D": "Dd", "E": "EeFf"}
MARK_TAIL = re.compile(r"(?:[A-Da-dGOoyY人$W]|[0-9](?![0-9])){0,2}[）)]?")


def marker_candidates(s):
    """回傳 [(位置, 標記長度, {字母: 分數})]。"""
    cands = []
    for m in re.finditer(r"[（(]|GB|G0|Go|(?<=[\u4e00-\u9fff，。？：、」）])[0O](?=D?[\u4e00-\u9fff「])", s):
        p, tok = m.start(), m.group(0)
        if tok in "（(":
            inner = s[p + 1:p + 9]
            close = inner.find("）")
            # 一般括號「（市）」「（警察局）」：短距離內就有右括號、且裡面全是中文
            if close > 0 and CJK.fullmatch(inner[0]) and all(CJK.match(ch) for ch in inner[:close]):
                continue
            tail = MARK_TAIL.match(s, p + 1).group(0)
            span = 1 + len(tail)
            base = 1.0
        else:
            tail = tok
            span = len(tok) + (1 if s[p + len(tok):p + len(tok) + 1] in "D）)" else 0)
            base = 0.8
        scores = {}
        for k in KEYS:
            sc = base
            if any(ch in LETTER_HINT[k] for ch in tail[:2]):
                sc += 2
            scores[k] = sc
        # 「GB」幾乎都是 (B)；「0D」「OD」是 (D)
        if tok == "GB":
            scores["B"] += 1.5
        if re.match(r"[0O]D", s[p + (0 if tok not in "（(" else 1):p + 3]):
            scores["D"] += 1.5
        cands.append((p, span, scores))
    return cands


def split_options(s, m=4):
    """用動態規劃挑出依序出現的 A<B<C<D 四個標記。回傳 (stem, {A..D}, 信心分數) 或 None。"""
    cands = marker_candidates(s)
    n = len(cands)
    if n < m:
        return None
    NEG = -1e9
    # dp[j][i]：第 j 個標記（A=0..D=3）落在候選 i 的最佳分數
    dp = [[NEG] * n for _ in range(m)]
    back = [[-1] * n for _ in range(m)]
    for i in range(n):
        before = s[max(0, cands[i][0] - 2):cands[i][0]]
        dp[0][i] = cands[i][2]["A"] + (1.5 if re.search(r"[？：?:]", before) else 0)
    for j in range(1, m):
        k = KEYS[j]
        best, arg = NEG, -1
        for i in range(n):
            # 前一個標記至少要在 2 個字之前（選項不會是空的）
            for i2 in range(arg + 1, i):
                if cands[i2][0] + cands[i2][1] < cands[i][0] and dp[j - 1][i2] > best:
                    best, arg = dp[j - 1][i2], i2
            if best > NEG and cands[i][2][k] > 0:
                dp[j][i] = best + cands[i][2][k]
                back[j][i] = arg
    end = max(range(n), key=lambda i: dp[m - 1][i])
    if dp[m - 1][end] <= 0:
        return None
    idx = [0] * m
    idx[m - 1] = end
    for j in range(m - 1, 0, -1):
        idx[j - 1] = back[j][idx[j]]
    pos = [cands[i] for i in idx]
    stem = s[:pos[0][0]]
    opts = {}
    for j, (p, span, _) in enumerate(pos):
        e = pos[j + 1][0] if j < m - 1 else len(s)
        opts[KEYS[j]] = s[p + span:e]
    # 每個標記滿分 3（有對應字母），A 另有 1.5 題幹結尾加分
    score = dp[m - 1][end] / (3 * m + 1.5)
    return stem, opts, score


RESIDUE = {"A": r"^[人Aa]?", "B": r"^[8Bb]", "C": r"^[GgCc0O]", "D": r"^[0OD]{1,2}", "E": r"^[EeF]"}


def clean_option(t, k="A"):
    t = t.strip("，、 ")
    t = re.sub(r"[（(]+$", "", t)
    t = re.sub(r"^[@#＠]+[A-Ea-e0-9]?", "", t)
    t = re.sub(r"^[）)yY]+", "", t)
    t2 = re.sub(RESIDUE[k], "", t, count=1)
    if t2 and t2 != t and re.match(r"[一-鿿0-9「（]", t2) and not (t[:1] in "ABCDE" and re.match(r"[A-Z]", t[1:2] or "0")):
        if k != "A" or t[:1] in "人aA":
            t = t2
    t = re.sub(r"^0(?=[0-9])", "", t)  # 數字不會以 0 開頭，是標記殘渣
    t = re.sub(r"[。．.]+$", "", t)
    return t


def clean_stem(t):
    return t.strip()


# ---------- 答案表 ----------


def read_answers(lines, sid):
    rows = []
    for l in lines:  # 從答案表第一行開始，取連續的答案行
        if is_answer_row(text_of(l)):
            rows.append(l)
        elif rows:
            break
    if not rows:
        return {}, None
    page = rows[0]["page"]
    rows = [l for l in rows if l["page"] == page]
    img = Image.open(WORK / "pages" / f"p{page:04d}.png")
    pad = 20
    box = (max(0, min(l["left"] for l in rows) - pad), max(0, rows[0]["top"] - pad),
           min(img.width, max(l["right"] for l in rows) + pad * 4), min(img.height, rows[-1]["bottom"] + pad))
    crop_path = WORK / "answers" / f"{sid}.png"
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    img.crop(box).save(crop_path)
    out = subprocess.run(["tesseract", str(crop_path), "-", "-l", "eng", "--psm", "6",
                          "-c", "tessedit_char_whitelist=0123456789ABCD.()"],
                         capture_output=True, text=True).stdout
    found = {}
    for n, a in re.findall(r"(\d{1,3})\.?\(?([ABCD]{1,4})\)?", out):
        found.setdefault(int(n), "".join(sorted(set(a))))
    return found, crop_path


# ---------- 主流程 ----------


def parse_section(ch, sec):
    first, last = sec["pages"]
    lines = []
    for p in range(first, last + 1):
        pl = load_lines(p)
        L = body_left(pl)
        for l in pl:
            l["L"] = L
        lines.extend(pl)

    # 題目區在答案表之前
    # 答案表 = 連續 3 行以上「很多括號、很少中文」的行（避免把「(A)40歲(B)45歲…」這種選項行誤判）
    ans_i, run = len(lines), 0
    for i, l in enumerate(lines):
        t = text_of(l)
        run = run + 1 if is_answer_row(t) else 0
        if run >= 3:
            ans_i = i - 2
            break
        if t.count("(") + t.count("（") >= 7:  # 只有兩列的短答案表
            ans_i = i - (run - 1)
            break
    qlines, after = lines[:ans_i], lines[ans_i:]

    blocks = []
    for l in qlines:
        start = is_start(l)
        t = text_of(l, min_center=l["L"] - 2) if start else text_of(l)
        if start:
            blocks.append({"parts": [t], "lines": [l]})
        elif blocks:
            blocks[-1]["parts"].append(t)
            blocks[-1]["lines"].append(l)
        # 第一題之前的內容（章名、回次橫幅）直接略過

    answers, crop = read_answers(after, sec["id"])
    _mf = WORK / "answers.json"  # 人工看圖抄寫的答案（優先於 OCR）
    if _mf.exists():
        _m = json.load(open(_mf, encoding="utf-8")).get(sec["id"])
        if _m:
            answers = {i + 1: a for i, a in enumerate(_m)}
    multi = "多重" in sec["title"]

    questions, flags = [], []
    for n, b in enumerate(blocks, 1):
        raw = normalize("".join(b["parts"]))
        confs = [w["conf"] for l in b["lines"] for w in l["words"] if w["conf"] >= 0]
        conf = sum(confs) / len(confs) if confs else 0
        q = {"id": f"{sec['id']}-{n:02d}", "number": n, "question": raw, "options": {k: "" for k in KEYS[:4]},
             "answer": answers.get(n, ""),
             "_pages": sorted({l["page"] for l in b["lines"]}),
             "_box": [min(l["left"] for l in b["lines"]), b["lines"][0]["top"],
                      max(l["right"] for l in b["lines"]), b["lines"][-1]["bottom"]]}
        if multi:
            q["multi"] = True
        why = []
        sp = None
        if multi:
            sp = split_options(raw, 5)
            if sp and sp[2] < 0.5:
                sp = None
        if sp is None:
            sp = split_options(raw, 4)
        if sp:
            stem, opts, score = sp
            q["question"] = clean_stem(stem)
            q["options"] = {k: clean_option(v, k) for k, v in opts.items()}
            if multi and "E" not in q["options"] and "E" in (q["answer"] or ""):
                why.append("答案含 E 但只切出 4 個選項")
            if score < 0.75:
                why.append(f"選項標記不確定({score:.2f})")
            if any(len(v) == 0 for v in q["options"].values()):
                why.append("有空白選項")
        else:
            why.append("切不出四個選項")
        if not q["answer"]:
            why.append("答案表沒讀到這題")
        if conf < MEANCONF:
            why.append(f"OCR 信心偏低({conf:.0f})")
        low = [w["text"] for l in b["lines"] for w in l["words"]
               if 0 <= w["conf"] < LOWCONF and CJK.search(w["text"]) and w["left"] > l["L"]]
        if low:
            why.append("低信心字：" + "".join(low)[:12])
        if len(b["lines"]) > 1 and len(b["lines"][0]["words"]) and b["lines"][0]["page"] != b["lines"][-1]["page"]:
            why.append("跨頁")
        if why:
            q["_flags"] = why
            flags.append((q["id"], why))
        questions.append(q)

    # 疑點解析：答案表之後「第N題」獨立成行
    cur = None
    for l in after:
        t = normalize(text_of(l))
        m = re.fullmatch(r"第(\d{1,3})題", t)
        if m:
            cur = int(m.group(1))
            if 1 <= cur <= len(questions):
                questions[cur - 1]["explanation"] = ""
            else:
                cur = None
            continue
        if cur and not is_answer_row(t):
            questions[cur - 1]["explanation"] += t

    sec_flags = []
    if answers and len(answers) != len(questions):
        sec_flags.append(f"題數 {len(questions)} 與答案表讀到的 {len(answers)} 筆不一致")
    if not answers:
        sec_flags.append("找不到答案表")
    return {"id": sec["id"], "title": sec["title"], "questions": questions}, flags, sec_flags, crop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--structure", default=str(ROOT / "structure.json"))
    ap.add_argument("--only", help="只處理這個章節 id，例如 ch4")
    ap.add_argument("--force", action="store_true", help="覆蓋已存在的草稿（會丟掉你在草稿上做的修正！）")
    a = ap.parse_args()
    structure = json.load(open(a.structure, encoding="utf-8"))
    outdir = WORK / "draft"
    outdir.mkdir(parents=True, exist_ok=True)

    for ch in structure["chapters"]:
        if a.only and ch["id"] != a.only:
            continue
        path = outdir / f"{ch['id']}.json"
        if path.exists() and not a.force:
            print(f"{path.relative_to(ROOT)} 已存在，略過（要重新解析請加 --force，會覆蓋修正）")
            continue
        chap = {"id": ch["id"], "chapter": ch["chapter"], "title": ch["title"], "sections": []}
        report = [f"# Chapter {ch['chapter']} {ch['title']} 解析報告\n"]
        for sec in ch["sections"]:
            s, flags, sec_flags, crop = parse_section(ch, sec)
            chap["sections"].append(s)
            report.append(f"\n## {sec['title']}（{sec['id']}，PDF 第 {sec['pages'][0]}–{sec['pages'][1]} 頁）\n")
            report.append(f"- 題數：{len(s['questions'])}，答案表讀到：{sum(bool(q['answer']) for q in s['questions'])}")
            report.append(f"- 答案表裁圖：`{crop.relative_to(ROOT) if crop else '無'}`（一定要看圖核對答案）")
            for f in sec_flags:
                report.append(f"- ⚠️ {f}")
            for qid, why in flags:
                report.append(f"  - {qid}：{'、'.join(why)}")
        json.dump(chap, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        (outdir / f"{ch['id']}.report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        n = sum(len(s["questions"]) for s in chap["sections"])
        print(f"{ch['id']}：{len(chap['sections'])} 回、{n} 題 → {path.relative_to(ROOT)}、{ch['id']}.report.md")


if __name__ == "__main__":
    main()
