"""Videoya BerxwedanNuce.com logosu ekler.

- Ortaya: büyük, yarı şeffaf filigran
- Üste (sol üst köşe): küçük, belirgin logo

Kullanım:
    python add_logo.py girdi.mov cikti.mp4                 # yazı logosu
    python add_logo.py girdi.mov cikti.mp4 --logo logo.png # resim logosu (PNG, şeffaf arka plan önerilir)

Gerekli: sistemde ffmpeg kurulu olmalı.
"""

import argparse
import os
import subprocess

TEXT = "BerxwedanNuce.com"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def find_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def text_filter(center_alpha, top_alpha):
    font = find_font()
    font_opt = f"fontfile={font}:" if font else ""
    center = (
        f"drawtext={font_opt}text='{TEXT}':fontcolor=white@{center_alpha}:"
        "fontsize=h/9:borderw=2:bordercolor=black@" f"{center_alpha / 2:.2f}:"
        "x=(w-text_w)/2:y=(h-text_h)/2"
    )
    top = (
        f"drawtext={font_opt}text='{TEXT}':fontcolor=white@{top_alpha}:"
        "fontsize=h/22:borderw=2:bordercolor=black@0.6:"
        "box=1:boxcolor=black@0.35:boxborderw=8:"
        "x=w*0.02:y=h*0.03"
    )
    return ["-vf", f"{center},{top}"]


def image_filter(logo, center_alpha, top_alpha):
    graph = (
        "[1:v]format=rgba,split[l1][l2];"
        # ortadaki filigran: videonun yüksekliğinin %45'i, yarı şeffaf
        f"[l1][0:v]scale2ref=w=oh*mdar:h=ih*0.45[c][base];"
        f"[c]colorchannelmixer=aa={center_alpha}[cw];"
        "[base][cw]overlay=(W-w)/2:(H-h)/2[v1];"
        # üstteki logo: videonun yüksekliğinin %14'ü
        f"[l2][v1]scale2ref=w=oh*mdar:h=ih*0.14[t][v2];"
        f"[t]colorchannelmixer=aa={top_alpha}[tw];"
        "[v2][tw]overlay=W*0.02:H*0.03[out]"
    )
    return ["-i", logo, "-filter_complex", graph, "-map", "[out]", "-map", "0:a?"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--logo", help="Logo resmi (PNG). Verilmezse yazı logosu kullanılır.")
    p.add_argument("--center-alpha", type=float, default=0.25, help="Ortadaki filigranın opaklığı (0-1)")
    p.add_argument("--top-alpha", type=float, default=0.9, help="Üstteki logonun opaklığı (0-1)")
    args = p.parse_args()

    cmd = ["ffmpeg", "-y", "-i", args.input]
    if args.logo:
        cmd += image_filter(args.logo, args.center_alpha, args.top_alpha)
    else:
        cmd += text_filter(args.center_alpha, args.top_alpha)
    cmd += [
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart",
        args.output,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
