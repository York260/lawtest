# 題庫轉檔流程（本機 Claude Code 操作手冊）

把掃描版《警察法規選擇題彙編》PDF 轉成 `data/questions.json`，給 `index.html` 刷題用。
流程是：**Tesseract OCR（免費、本機）→ 程式切題 → Claude 看圖核對修正 → 合併進題庫**。

## 實測品質（前 27 頁、100 題，對照人工校對版本）

| 項目 | 結果 |
|---|---|
| OCR 速度 | 約 0.6 秒／頁（4 核心），700 頁約 7–10 分鐘 |
| 切題 | 100/100 題正確切出 |
| 題幹文字相似度 | 97.5% |
| 選項文字相似度 | 95% |
| 整題（題幹＋四個選項）完全正確 | 51/100（其餘多半是 1–2 個錯字，例如「羈押」變「國押」） |
| 答案表 | 94/100（6 題沒讀到；讀到的也可能錯，**一定要看圖核對**） |
| 可疑題標記 | 會標出約八成題目；Tesseract 的信心值分不太出對錯，所以**建議逐頁核對** |

## 0. 安裝（第一次）

- Python 3.10 以上：`pip install pymupdf pillow`
- Tesseract ＋ 繁體中文語言檔：
  - macOS：`brew install tesseract tesseract-lang`
  - Windows：安裝 UB Mannheim 版 Tesseract，安裝時勾選 Chinese (Traditional)，並把安裝資料夾加入 PATH
  - Ubuntu：`sudo apt install tesseract-ocr tesseract-ocr-chi-tra`
- 確認：`tesseract --list-langs` 要看得到 `chi_tra`

## 1. 放 PDF

把整本 PDF 放在 repo 根目錄，命名為 `book.pdf`。`.gitignore` 已排除 `*.pdf` 和 `work/`，不會被提交。

## 2. 建立 structure.json（章節與頁碼對照）

章名與「衝刺第X回」是美術字，OCR 讀不到，所以要從目錄手動建立對照表。

1. 看目錄頁（PDF 前幾頁）取得每回的**書本頁碼**。
2. 找出書本頁碼與 PDF 頁碼的差值（例如書本第 5 頁 = PDF 第 13 頁，差 8）。後段若有插頁，差值可能會變，每章開頭都要抽查一頁確認。
3. 寫成 `structure.json`。`pages` 是 **PDF 頁碼**，從該回第一題那頁，到該回答案表（與疑點解析）那頁：

```json
{
  "chapters": [
    {
      "id": "ch4", "chapter": 4, "title": "社會秩序維護法",
      "sections": [
        { "id": "ch4-r1", "title": "衝刺第一回", "pages": [149, 156] },
        { "id": "ch4-r2", "title": "衝刺第二回", "pages": [157, 163] },
        { "id": "ch4-m",  "title": "多重選擇題", "pages": [219, 226] }
      ]
    }
  ]
}
```

- 回次標題含「多重」的會自動當作複選題，答案可以是 `ABD` 這種多個字母。
- 第 2 章已經人工校對完成，不要再放進 structure.json（放了也不會覆蓋，除非你對它執行 apply）。

## 3. OCR（整本一次跑完）

```
python tools/ocr.py book.pdf
```

輸出在 `work/pages/`（頁面圖）與 `work/ocr/`（辨識結果）。已完成的頁面會跳過，可以中斷後再跑。

## 4. 解析一章

```
python tools/parse.py --only ch4
```

產生：
- `work/draft/ch4.json`：草稿題庫，每題附 `_pages`（所在頁）與 `_flags`（可疑原因）
- `work/draft/ch4.report.md`：每回題數、答案表讀到幾筆、可疑題清單
- `work/answers/ch4-r1.png`：每回答案表的裁圖

重跑不會覆蓋已存在的草稿，除非加 `--force`（會丟掉修正）。

## 5. 核對修正（Claude 做這步）

**先處理答案**：逐一打開 `work/answers/<回次id>.png`，對照草稿中每題的 `answer` 並修正。這是最重要的一步，錯的答案會誤導刷題。

**再逐頁核對文字**：

```
python tools/review_page.py 149
```

這會輸出 `work/review/p0149.png`（裁掉空白、寬 1000px），並印出草稿中落在這頁的題目。打開圖片對照後，直接編輯 `work/draft/ch4.json` 修正錯字、錯切的選項、漏掉的疑點解析。

- 只改錯的地方，不要重打整題。
- 選項文字不含「(A)」標記，也不含結尾句號。
- 題目中的標點用全形：「，」「？」「：」「（）」「「」」。
- 同樣的錯字若反覆出現（例如「沒人處分」→「沒入處分」），加進 `tools/fixes.json`，之後其他章節重新解析就會自動修正。

## 6. 合併進題庫

```
python tools/apply.py ch4
```

會先檢查每題都有題目、四個選項和 A–D 答案；沒過就列出題號、不寫入。通過後會更新 `data/questions.json` 並自動執行 `build.py`。然後打開 `index.html` 抽查幾題，再提交：

```
git add data/ structure.json tools/fixes.json
git commit -m "新增 Chapter 4 社會秩序維護法"
```

## 省 token 的原則

- 不要直接讀 PDF，一律看 `work/review/` 的縮圖或 `work/answers/` 的裁圖。
- 每頁只看一次；圖片寬 1000px 就看得清楚，看不清再用 `--width 1300` 重出那一頁。
- **一章一個對話**：做完一章、提交後用 `/clear` 清掉對話再做下一章，避免上下文越積越多。
- 不需要重新評估 OCR 準確率（已經測過）。

## 評估工具（調整解析程式時才用）

`tools/eval_sample.py` 用人工校對過的第 2 章評分：

```
python tools/ocr.py sample.pdf --first 13 --last 26   # 用前 27 頁的 PDF
python tools/parse.py --structure <含 ch2 的 structure> --only ch2 --force
python tools/eval_sample.py work/draft/ch2.json data/questions.json
```

⚠️ 評估完要刪掉 `work/draft/ch2.json`，**不要**對 ch2 執行 apply，否則會用 OCR 版本蓋掉人工校對版本。
