from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parent
PLOTS = OUT / "plots"
PLOTS.mkdir(exist_ok=True)
W, H = 1200, 680
FONT = ImageFont.load_default(size=18)
SMALL = ImageFont.load_default(size=14)
COLORS = {"experiment": "#111111", "nominal": "#4472C4", "selected": "#D95F02"}


def canvas():
    image = Image.new("RGB", (W, H), "white")
    return image, ImageDraw.Draw(image)


def line_svg(points, color, width=2):
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def svg_doc(elements):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            '<rect width="100%" height="100%" fill="white"/>' + "".join(elements) + "</svg>\n")


def text_svg(x, y, value, size=16, anchor="start", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="#111">{escape(str(value))}</text>')


def bounds(values, pad=0.08):
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    return lo - pad * span, hi + pad * span


def map_points(xs, ys, box, xb=None, yb=None):
    left, top, right, bottom = box
    x0, x1 = xb or bounds(xs, 0)
    y0, y1 = yb or bounds(ys)
    return [
        (left + (x-x0)/(x1-x0)*(right-left), bottom - (y-y0)/(y1-y0)*(bottom-top))
        for x, y in zip(xs, ys)
    ]


def axes(draw, box, title, xlabel, ylabel, svg):
    left, top, right, bottom = box
    draw.rectangle(box, outline="#333", width=2)
    draw.text(((left+right)//2, top-42), title, font=FONT, fill="#111", anchor="mm")
    draw.text(((left+right)//2, bottom+35), xlabel, font=SMALL, fill="#111", anchor="mm")
    draw.text((left+8, top+8), ylabel, font=SMALL, fill="#111", anchor="la")
    svg.extend([
        f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" fill="none" stroke="#333" stroke-width="2"/>',
        text_svg((left+right)/2, top-22, title, 20, "middle", "bold"),
        text_svg((left+right)/2, bottom+38, xlabel, 15, "middle"),
        text_svg(left+8, top+20, ylabel, 15),
    ])


def spectrum(payload):
    image, draw = canvas(); svg = []
    box = (90, 130, 1140, 590)
    axes(draw, box, "Measured vs simulated HR03 - P05 spectrum", "Frequency (Hz, log2)",
         "Demeaned relative level (dB)", svg)
    freq = payload["frequency_hz"]
    xs = [__import__("math").log2(v) for v in freq]
    series = [
        ("Experiment primary", payload["experimental_primary_demeaned_db"], COLORS["experiment"]),
        ("Simulation nominal", payload["nominal_simulated_demeaned_db"], COLORS["nominal"]),
        ("Simulation selected", payload["selected_simulated_demeaned_db"], COLORS["selected"]),
    ]
    all_y = [v for _, ys, _ in series for v in ys if math.isfinite(v)]
    xb = (min(xs), max(xs)); yb = bounds(all_y, 0.04)
    cal_left = map_points([xs[147]], [yb[0]], box, xb, yb)[0][0]
    cal_right = map_points([xs[162]], [yb[0]], box, xb, yb)[0][0]
    draw.rectangle((cal_left, box[1], cal_right, box[3]), fill="#EEEEEE")
    svg.append(f'<rect x="{cal_left:.2f}" y="{box[1]}" width="{cal_right-cal_left:.2f}" height="{box[3]-box[1]}" fill="#eeeeee"/>')
    for i, (label, ys, color) in enumerate(series):
        finite_pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(y)]
        pts = map_points([x for x, _ in finite_pairs], [y for _, y in finite_pairs], box, xb, yb)
        draw.line(pts, fill=color, width=3)
        svg.append(line_svg(pts, color, 3))
        lx, ly = 115 + i*280, 55
        draw.line((lx, ly, lx+35, ly), fill=color, width=4); draw.text((lx+45, ly), label, font=SMALL, fill="#111", anchor="lm")
        svg.extend([f'<line x1="{lx}" y1="{ly}" x2="{lx+35}" y2="{ly}" stroke="{color}" stroke-width="4"/>', text_svg(lx+45, ly+5, label, 14)])
    for f in (200, 400, 800, 1600, 3200, 6400):
        x = map_points([__import__("math").log2(f)], [yb[0]], box, xb, yb)[0][0]
        draw.text((x, box[3]+10), str(f), font=SMALL, fill="#333", anchor="ma")
        svg.append(text_svg(x, box[3]+20, f, 13, "middle"))
    image.save(PLOTS / "measured_vs_simulated_spectrum.png")
    (PLOTS / "measured_vs_simulated_spectrum.svg").write_text(svg_doc(svg), encoding="utf-8")


def objective(payload, summary):
    image, draw = canvas(); svg = []
    samples = payload["objective_samples"]
    box = (80, 120, 680, 590)
    axes(draw, box, "Frozen objective samples", "Effective length delta (mm)", "Loss scale", svg)
    jvals = [float(x["J5_db"]) for x in samples]; j0, j1 = min(jvals), max(jvals)
    for item in samples:
        x = box[0] + (float(item["delta_mm"])+0.2)/0.4*(box[2]-box[0])
        y = box[3] - (float(item["loss_scale"])-0.5)/1.5*(box[3]-box[1])
        t = (float(item["J5_db"])-j0)/(j1-j0 or 1)
        color = (int(40+210*t), int(90+100*(1-t)), int(210-170*t))
        draw.ellipse((x-7,y-7,x+7,y+7), fill=color, outline="#222")
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="rgb{color}" stroke="#222"/>')
    profiles = summary["profiles"]
    for idx, (key, label) in enumerate((("delta_mm", "Delta profile"), ("loss_scale", "Loss profile"))):
        pbox = (760, 120+idx*290, 1140, 290+idx*290)
        axes(draw, pbox, label, key, "Profile J5 (dB)", svg)
        profile = profiles[key]["profile"]
        px = [float(k) for k in profile]; py = [float(profile[k]) for k in profile]
        pts = map_points(px, py, pbox, bounds(px, 0.02), bounds(py, 0.12))
        draw.line(pts, fill=COLORS["selected"], width=3)
        svg.append(line_svg(pts, COLORS["selected"], 3))
        for x,y in pts:
            draw.ellipse((x-4,y-4,x+4,y+4), fill=COLORS["selected"])
            svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{COLORS["selected"]}"/>')
    draw.text((80, 55), f"Jmin={j0:.4f} dB; selected=(+0.200 mm, 2.0000)", font=FONT, fill="#111")
    svg.append(text_svg(80, 62, f"Jmin={j0:.4f} dB; selected=(+0.200 mm, 2.0000)", 18, weight="bold"))
    image.save(PLOTS / "objective_surface_profile.png")
    (PLOTS / "objective_surface_profile.svg").write_text(svg_doc(svg), encoding="utf-8")


def bootstrap(payload, summary):
    image, draw = canvas(); svg = []
    panels = [
        ("Bootstrap delta estimates", payload["bootstrap_delta_mm"], (-0.2, 0.2), "mm"),
        ("Bootstrap loss estimates", payload["bootstrap_loss_scale"], (0.5, 2.0), "scale"),
    ]
    for idx, (title, values, lim, unit) in enumerate(panels):
        box = (80+idx*570, 125, 570+idx*570, 540)
        axes(draw, box, title, unit, "Count", svg)
        counts = {}
        for value in values: counts[value] = counts.get(value, 0) + 1
        max_count = max(counts.values())
        for value, count in counts.items():
            x = box[0] + (value-lim[0])/(lim[1]-lim[0])*(box[2]-box[0])
            y = box[3] - count/max_count*(box[3]-box[1]-20)
            draw.rectangle((x-18,y,x+18,box[3]), fill=COLORS["selected"])
            draw.text((x,y-8), str(count), font=SMALL, fill="#111", anchor="ms")
            svg.extend([f'<rect x="{x-18:.2f}" y="{y:.2f}" width="36" height="{box[3]-y:.2f}" fill="{COLORS["selected"]}"/>', text_svg(x,y-8,count,14,"middle")])
    flag = "NON-IDENTIFIABLE: both selected values hit upper bounds; correlation undefined"
    draw.text((W//2, 55), flag, font=FONT, fill="#A00000", anchor="mm")
    svg.append(text_svg(W/2, 62, flag, 19, "middle", "bold"))
    draw.text((W//2, 625), "2000 complete-curve bootstrap replicates; default_rng(250825)", font=SMALL, fill="#111", anchor="mm")
    svg.append(text_svg(W/2, 632, "2000 complete-curve bootstrap replicates; default_rng(250825)", 15, "middle"))
    image.save(PLOTS / "bootstrap_identifiability.png")
    (PLOTS / "bootstrap_identifiability.svg").write_text(svg_doc(svg), encoding="utf-8")


def main():
    payload = json.loads((OUT / "plot_payload.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "identifiability_summary.json").read_text(encoding="utf-8"))
    spectrum(payload)
    objective(payload, summary)
    bootstrap(payload, summary)


if __name__ == "__main__":
    main()
