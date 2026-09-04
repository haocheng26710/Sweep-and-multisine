"""Inspect PDF layout and create a contact sheet from Poppler-rendered pages."""
from pathlib import Path
import json
import sys

import pdfplumber
from PIL import Image, ImageDraw

folder = Path(sys.argv[1]).resolve()
rows = []
with pdfplumber.open(folder / "root.pdf") as pdf:
    for number, page in enumerate(pdf.pages, 1):
        words = page.extract_words()
        lines = (page.extract_text() or "").splitlines()
        columns = []
        for left, right in ((45, 300), (311, 568)):
            intervals = [(w["top"], w["bottom"]) for w in words
                         if left <= (w["x0"]+w["x1"])/2 <= right and 35 < w["top"] < 755]
            intervals += [(img["top"], img["bottom"]) for img in page.images
                          if img["x0"] < right and img["x1"] > left]
            intervals.sort()
            gaps = []
            if intervals:
                bottom = intervals[0][1]
                for top, end in intervals[1:]:
                    if top-bottom > 28:
                        gaps.append([round(bottom, 1), round(top, 1), round(top-bottom, 1)])
                    bottom = max(bottom, end)
            columns.append(gaps)
        rows.append({"pdf_page": number, "word_count": len(words), "first_lines": lines[:3],
                     "last_lines": lines[-3:], "largest_internal_gaps_pt": columns,
                     "text_max_y": round(max([w["bottom"] for w in words], default=0), 2),
                     "images": [{k: round(image[k], 2) for k in ("x0", "x1", "top", "bottom")}
                                for image in page.images]})
(folder / "layout_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
images = sorted(folder.glob("page-*.png"))
if images:
    thumb_w, thumb_h = 340, 440
    sheet = Image.new("RGB", (3*thumb_w, ((len(images)+2)//3)*(thumb_h+25)), "#cdd1d4")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(images):
        with Image.open(path) as im:
            im.thumbnail((thumb_w-8, thumb_h-8))
            x, y = (i % 3)*thumb_w+4, (i // 3)*(thumb_h+25)+22
            sheet.paste(im, (x, y))
            draw.text((x+6, y-17), f"PDF page {i+1}", fill="black")
    sheet.save(folder / "contact.png")
print(json.dumps(rows, ensure_ascii=True))
