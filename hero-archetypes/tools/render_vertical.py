"""Optional 9:16 Shorts cut (~60 s) built around the Zelda section.

Segments (narration-anchored, edit SEGMENTS below): the hook, the Hero of Time
section and the "problems are soluble" payoff. The 16:9 frames are placed on a
tall paper background with a title above and big burned-in captions below.
Output: final/hero_archetypes_vertical.mp4
"""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import collage as C  # noqa: E402
import render as R  # noqa: E402

ROOT = R.ROOT
SEGMENTS = [("0", "s1e+0.5"), ("s3-0.3", "s3e+0.6"), ("s7.5-0.3", "s7.8e+0.9"), ("s8.2-0.2", "s8.2e+1.2")]
W, H, FPS = 1080, 1920, 30


def srt_cues():
    txt = (ROOT / "final" / "captions.srt").read_text(encoding="utf-8")
    cues = []
    for block in txt.strip().split("\n\n"):
        lines = block.splitlines()
        a, b = re.findall(r"(\d+):(\d+):(\d+),(\d+)", lines[1])
        ts = [int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in (a, b)]
        cues.append((ts[0], ts[1], " ".join(lines[2:])))
    return cues


def main():
    from moviepy.editor import AudioFileClip, VideoClip, concatenate_audioclips
    segs = [(R.T(a), R.T(b)) for a, b in SEGMENTS]
    total = sum(b - a for a, b in segs)
    rend = R.Renderer("final")
    pal = R.CFG["palettes"]["hyrule"]
    bg = C.paper_texture(W, H, pal, seed=21).convert("RGBA")
    title = C.caption_image("Why does Link\nfeel so familiar?", "title", R.CFG, 1.0, pal, size=86, seed=3)
    title = title.rotate(-2, resample=Image.BICUBIC, expand=True)
    bg.alpha_composite(title, ((W - title.width) // 2, 150))
    tag = C.caption_image("The hero with a thousand faces", "type", R.CFG, 1.0, pal, size=34, seed=5)
    bg.alpha_composite(tag, ((W - tag.width) // 2, 150 + title.height + 20))
    cues = srt_cues()
    fnt = C.font(R.CFG["fonts"]["caption"], 64)
    cap_cache = {}

    def src_time(t):
        for a, b in segs:
            if t < b - a:
                return a + t
            t -= b - a
        return segs[-1][1]

    def caption_for(ts):
        for a, b, text in cues:
            if a <= ts < b:
                return text
        return None

    def make_frame(t):
        ts = src_time(t)
        frame = bg.copy()
        hz = Image.fromarray(rend.frame(ts)).resize((1000, 563), Image.LANCZOS).convert("RGBA")
        card = Image.new("RGBA", (hz.width + 28, hz.height + 28), (250, 248, 240, 255))
        card.alpha_composite(hz, (14, 14))
        card = card.rotate(1.2, resample=Image.BICUBIC, expand=True)
        frame.alpha_composite(card, ((W - card.width) // 2, 620))
        text = caption_for(ts)
        if text:
            if text not in cap_cache:
                words, lines, cur = text.upper().split(), [], ""
                for w_ in words:
                    if fnt.getlength(cur + " " + w_) > W - 160 and cur:
                        lines.append(cur)
                        cur = w_
                    else:
                        cur = (cur + " " + w_).strip()
                lines.append(cur)
                im = Image.new("RGBA", (W, 90 * len(lines) + 40), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                for i, ln in enumerate(lines):
                    d.text((W // 2, 20 + i * 90), ln, font=fnt, fill=(255, 255, 255, 255), anchor="ma",
                           stroke_width=7, stroke_fill=(20, 20, 20, 255))
                cap_cache[text] = im
            im = cap_cache[text]
            frame.alpha_composite(im, (0, 1330))
        return np.asarray(frame.convert("RGB"))

    wav = ROOT / "build" / "mix.wav"
    if not wav.exists():
        R.mix_audio(wav)
    audio = AudioFileClip(str(wav))
    aud = concatenate_audioclips([audio.subclip(a, min(b, audio.duration)) for a, b in segs])
    clip = VideoClip(make_frame, duration=total).set_audio(aud)
    out = ROOT / "final" / "hero_archetypes_vertical.mp4"
    clip.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", audio_bitrate="192k", preset="medium",
                         ffmpeg_params=["-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"], threads=4, logger=None)
    print("wrote", out.relative_to(ROOT), f"({total:.1f}s)")


if __name__ == "__main__":
    main()
