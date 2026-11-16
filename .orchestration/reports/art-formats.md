# Art format bake-off (AC-9)

Subject: `gears` (the busiest of the three: 8 gears, ~38k edges per frame). Source: the same
master, 300 frames at 1200x1200, 30 fps, 10 s, over black (`art/.cache/gears/black/`).
Reproduce with `python3 art/tools/bakeoff.py gears` (`--fresh` to re-encode).

Owner decides the delivery format from this. **The default stays VP9 WebM + H.264 MP4.**

## Table

| Format | File | Size | vs 1.5 MB budget | Encoder and settings | Visual notes at 200% | Browser support |
| --- | --- | --- | --- | --- | --- | --- |
| H.264 MP4 (delivered) | `loop.mp4` | 1,390,593 B (1.33 MB) | fits | Blender FFmpeg (x264), High, yuv420p, faststart; CRF 23 overshoots, so 1119 kbps average | Keyframe (frame 1) close to the master. Between keyframes (frame 150) dim interior lines get faint blocky noise and slight softening; bright lines hold. | Everywhere (Safari, Chrome, Firefox, Edge, iOS, Android) |
| VP9 WebM (delivered) | `loop.webm` | 1,462,635 B (1.39 MB) | fits | Blender FFmpeg (libvpx-vp9), CRF 32 overshoots, so ~865-984 kbps average | Cleaner than H.264 at the same size: dim lines stay continuous, less noise between keyframes. | Chrome, Edge, Firefox; Safari 14.1+ on macOS 11.3+, iOS 17.4+ |
| AV1 WebM | `loop_av1.webm` | 1,067,544 B (1.02 MB) | fits with room | Blender FFmpeg (AV1), 900 kbps target (lands at ~850 kbps) | Best of the videos at the smallest size: smooth, no visible blocking; very slight smoothing of the dimmest lines. | Chrome 70+, Edge, Firefox 67+; Safari 17+ only on devices with AV1 hardware decode (M3 Macs, iPhone 15 Pro and later) |
| Animated WebP | `loop.webp` | 57,384,814 B (54.73 MB) | ~36x over | libwebp `img2webp -lossy -q 70 -m 6`, 33 ms frames | Each frame coded on its own: crisp, close to the master, faint ringing next to bright lines. | Chrome, Edge, Firefox 65+, Safari 14+ |
| Animated AVIF | `loop.avif` | 45,713,413 B (43.60 MB) | ~29x over | libheif `heif-enc -S --fps 30 -q 60` (defaults, not tuned for inter-frame coding) | Close to the master on frame 1; size shows the sequence was coded with little inter-frame prediction. | Chrome 85+ (animated 93+), Firefox 113+, Safari 16.4+ |
| GIF | `loop.gif` | 115,748,589 B (110.39 MB) | ~74x over | ImageMagick, 64 grey levels, no dither, `-layers OptimizeTransparency`, 1/30 s delay | Banding in the dim lines (64 levels), hard edges lose their anti-aliasing tails; 1-bit transparency only. | Everywhere, but browsers clamp very short delays on some platforms |

Sizes are bytes on disk. Encodes live in `art/.cache/bakeoff/gears/` (ignored by git).

## Crops

- `art-shots/gears-formats-200pct.png`: the same 200x200 region of frame 1 from every format,
  at 200%, next to the master PNG. Frame 1 is a keyframe for the videos (their best case).
- `art-shots/gears-video-frame150-200pct.png`: frame 150 (mid-GOP) of the three videos next
  to the master, which shows the real difference between them.

## Reading it

- Only the three video codecs fit the 1.5 MB budget at 1200 px. The image formats are
  30-75x larger because they cannot predict one frame from the last as well (WebP, GIF) or
  were not set up to (this AVIF).
- At equal size AV1 > VP9 > H.264 on these thin dim lines. AV1 cannot be the only format
  (Safari support is hardware-dependent), so the useful options are:
  1. **VP9 WebM + H.264 MP4** (current default): good everywhere; the MP4 fallback is the
     weakest at 200% but fine at 100%.
  2. **AV1 WebM + H.264 MP4**: smaller and cleaner for Chrome/Firefox/new Apple devices;
     same MP4 fallback.
  3. All three (`<source>` order AV1, VP9, H.264).
- The pipeline can produce AV1 already (`encode.py` profile `av1`); switching is a one-line
  change in `pipeline.py`.

## Tools

H.264, VP9 and AV1: Blender 5.2's bundled FFmpeg. GIF: ImageMagick 7.1.2 (Homebrew).
Animated WebP: libwebp 1.6.0 `img2webp` (Homebrew). Animated AVIF: libheif 1.21.2
`heif-enc` (Homebrew). All were already installed; nothing was downloaded. The Homebrew
`ffmpeg` was not used.

Browser support is from general knowledge of current browser releases, not tested in
browsers in this session.
