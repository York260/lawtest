"""把 PDF 每頁轉成灰階圖片並用 Tesseract（繁中）辨識，結果存成 TSV（含每個字的位置與信心值）。

用法：python tools/ocr.py book.pdf [--first 1] [--last 700] [--workers 4]
輸出：work/pages/p0001.png、work/ocr/p0001.tsv（已存在的頁面會跳過，可中斷後續跑）
"""
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"


def ocr_page(pdf_path, pno, dpi):
    png = WORK / "pages" / f"p{pno:04d}.png"
    base = WORK / "ocr" / f"p{pno:04d}"
    if (base.with_suffix(".tsv")).exists():
        return pno, "skip"
    if not png.exists():
        doc = pymupdf.open(pdf_path)
        doc[pno - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY).save(png)
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    r = subprocess.run(
        ["tesseract", str(png), str(base), "-l", "chi_tra", "--psm", "6", "tsv"],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        return pno, "error: " + r.stderr.strip()[:200]
    return pno, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=0, help="最後一頁（預設到結尾）")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    if not shutil.which("tesseract"):
        sys.exit("找不到 tesseract，請先安裝（見 PIPELINE.md）")
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    if "chi_tra" not in langs:
        sys.exit("tesseract 缺少 chi_tra（繁體中文）語言檔，請先安裝（見 PIPELINE.md）")
    (WORK / "pages").mkdir(parents=True, exist_ok=True)
    (WORK / "ocr").mkdir(parents=True, exist_ok=True)
    n = len(pymupdf.open(a.pdf))
    last = min(a.last or n, n)
    pages = range(a.first, last + 1)
    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for pno, status in ex.map(lambda p: ocr_page(a.pdf, p, a.dpi), pages):
            done += 1
            if status.startswith("error"):
                print(f"p{pno}: {status}", flush=True)
            if done % 25 == 0 or done == len(pages):
                print(f"{done}/{len(pages)} 頁完成", flush=True)


if __name__ == "__main__":
    main()
