# 題庫資料格式（給網站開發者）

`data/questions.json`（由 `build.py` 轉成 `data/questions.js`）的結構：

```
{ chapters: [ { id, chapter, title, sections: [ { id, title, questions: [ Question ] } ] } ] }
```

## Question 欄位

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 唯一，例如 `ch4-r2-05`、`ex-n111-24` |
| `number` | int | **原書／原考卷上的題號**（考古題與 id 尾碼一致） |
| `question` | string | 題幹。特殊題會在最後加括號備註，例如「（本題有兩個答案，答B或D皆給分）」 |
| `options` | object | `A`–`D`，複選題另有 `E` |
| `answer` | string | 主要答案。單選如 `"B"`，複選如 `"ACE"`；**一律給分的題為空字串 `""`** |
| `multi` | bool（選填） | 複選題（畫面顯示【複選】） |
| `accepted` | string[]（選填） | **所有給分的答案**，只有特殊題才有，例如 `["B","D"]`、`["BC","BCD"]`。第一個等於 `answer` |
| `full_credit` | bool（選填） | `true`＝本題無正確答案、**一律給分**（此時 `answer=""`、`accepted=[]`） |
| `explanation` | string（選填） | 疑點解析（只有第 2 章前兩回有） |

## 批改規則
- 一般題：`mine === answer`。
- 有 `accepted`：`accepted.includes(mine)` 即算對。
- `full_credit`：不論作答一律算對，顯示「本題無正確答案，一律給分」。
- 單選題的 `accepted` 偶爾含 `"AB"`、`"AC"` 這類組合（原始答案表如此標示），單選介面無法選到，忽略即可；題幹備註只列可選的單一答案。

## 目前 `index.html` 的相容處理
已加入 `isCorrect()`、`correctKeys()`、`answerText()`，會讀 `accepted` 與 `full_credit`，其餘顯示細節請自行調整。

## 特殊題清單（共 20 題）
`ex-2j111-38`、`ex-2j115-20`、`ex-zb114-02`、`ex-n109-08`、`ex-n111-24`、`ex-n113-19`、`ex-n114-10`、`ex-n114-14`、`ex-n114-15`、`ex-n114-23`、`ex-s109-01`、`ex-s109-10`、`ex-s111-04`、`ex-s111-05`、`ex-s114-05`、`ex-u111-02`、`ap-107s-09`、`ap-107s-10`、`ap-108z-27`、`ap-108z-28`。
