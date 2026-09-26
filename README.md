# 警察法規刷題

依章節分類的警察法規選擇題庫與靜態刷題網頁。

- `data/questions.json`：題庫（章節 → 回次 → 題目，含選項、答案、疑點解析）
- `data/questions.js`：由 `build.py` 從 JSON 產生，讓網頁直接雙擊開啟（file://）也能載入
- `index.html`：刷題網頁

## 使用方式

直接用瀏覽器開啟 `index.html`（或部署到 GitHub Pages）。

1. 勾選章節／回次（可整章全選、可選擇題目隨機排序）
2. 一題一題作答，可上一題／下一題或點題號跳題；鍵盤 A–D 或 1–4 選答、←/→ 換題
3. 右上角 A− / A＋ 調整文字大小（會記住設定）
4. 全部寫完按「交卷批改」，顯示答對題數／全部題數，並逐題列出你的答案與正確答案，可只看錯題或只重做錯題
5. 中途離開會保留作答進度，下次開啟可繼續

## 題庫格式

```json
{
  "chapters": [
    {
      "id": "ch2", "chapter": 2, "title": "警察法",
      "sections": [
        {
          "id": "ch2-r1", "title": "衝刺第一回",
          "questions": [
            { "id": "ch2-r1-01", "number": 1, "question": "…",
              "options": { "A": "…", "B": "…", "C": "…", "D": "…" },
              "answer": "A", "explanation": "（選填）" }
          ]
        }
      ]
    }
  ]
}
```

新增或修改題目後執行 `python3 build.py` 重新產生 `data/questions.js`。

目前收錄：Chapter 2 警察法（衝刺第一回、第二回，共 100 題）。

## 轉換更多章節

見 `PIPELINE.md`（Tesseract OCR → 程式切題 → 看圖核對 → 合併）。
