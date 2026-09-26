"""將 data/questions.json 轉成 data/questions.js，讓網頁直接以 file:// 開啟也能載入題庫。

修改題庫後執行：python3 build.py
"""
import json
from pathlib import Path

root = Path(__file__).parent
data = json.loads((root / "data" / "questions.json").read_text(encoding="utf-8"))
js = "window.QUESTION_BANK = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
(root / "data" / "questions.js").write_text(js, encoding="utf-8")
total = sum(len(s["questions"]) for c in data["chapters"] for s in c["sections"])
print(f"wrote data/questions.js ({total} questions)")
