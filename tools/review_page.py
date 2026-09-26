"""核對用：輸出某一頁的縮小圖，並列出草稿中落在這頁的題目，方便對照修正。

用法：python tools/review_page.py 14            → work/review/p0014.png + 印出該頁題目
      python tools/review_page.py 14 --width 900 → 調整圖片寬度（越小越省 token，但太小會看不清）
"""
import argparse
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"

ap = argparse.ArgumentParser()
ap.add_argument("page", type=int)
ap.add_argument("--width", type=int, default=1000)
a = ap.parse_args()

src = WORK / "pages" / f"p{a.page:04d}.png"
img = Image.open(src)
# 裁掉上下左右空白，再縮小
bbox = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox() or (0, 0, img.width, img.height)
img = img.crop(bbox)
h = int(img.height * a.width / img.width)
out = WORK / "review" / f"p{a.page:04d}.png"
out.parent.mkdir(parents=True, exist_ok=True)
img.resize((a.width, h)).save(out)
print(f"圖片：{out.relative_to(ROOT)}")

drafts = [json.load(open(f, encoding="utf-8")) for f in sorted((WORK / "draft").glob("*.json"))]
for c in drafts:
    for s in c["sections"]:
        for q in s["questions"]:
            if a.page in q.get("_pages", []):
                print(f"\n[{q['id']}] {q['question']}")
                for k, v in q["options"].items():
                    print(f"  ({k}) {v}")
                print(f"  答案：{q['answer'] or '？'}" + (f"　解析：{q['explanation']}" if q.get("explanation") else ""))
