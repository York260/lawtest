# lawtest

警察法規選擇題刷題網站：`index.html` 讀取 `data/questions.js`（由 `data/questions.json` 經 `python build.py` 產生）。

## 把 PDF 轉成題庫

照 `PIPELINE.md` 操作。重點：

- 流程：`tools/ocr.py` → 建 `structure.json` → `tools/parse.py --only <章>` → 看圖核對修正 `work/draft/<章>.json` → `tools/apply.py <章>`
- 答案一定要對照 `work/answers/*.png` 裁圖核對
- 不要直接讀 PDF；看 `tools/review_page.py` 產生的縮圖，每頁看一次
- 一章一個對話，做完提交後 `/clear`
- Chapter 2 是人工校對版，不要用 OCR 結果覆蓋
- 不要提交 PDF 或 `work/`
