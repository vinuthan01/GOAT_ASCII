"""Makes the half-original / half-ASCII preview clips used by the sample tiles.

Needs: ffmpeg, numpy, opencv-python, pillow.
Usage: python tools/make_previews.py SOURCE.mp4 assets/samples/NAME-preview.mp4 SECONDS [START_SECONDS] [CROP]
  Optional env SPLIT (0-1) sets where the original/ASCII divider sits (default 0.5).
  CROP is optional ffmpeg crop "w:h:x:y" to centre on the subject, e.g. "1240:723:2600:60".
Then grab a poster:  ffmpeg -ss 2.5 -i assets/samples/NAME-preview.mp4 -frames:v 1 -q:v 5 assets/samples/NAME.jpg
"""
import os, subprocess, sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

CHARS = " .,:;!+*ivxyzuwXZCJLQ0OZmwqpdbkhao#%&@$"   # same ramp as the app
W, H, CW, CH, FPS = 720, 420, 8, 14, 18
COLS, ROWS = W // CW, H // CH
CYAN = (108, 245, 224)

font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 13)
atlas = np.zeros((len(CHARS), CH, CW), np.float32)
for i, c in enumerate(CHARS):
    if c == " ": continue
    im = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(im).text((CW / 2, CH / 2), c, font=font, fill=255, anchor="mm")
    atlas[i] = np.asarray(im, np.float32) / 255.0

def ascii_frame(rgb):
    """rgb: H x W x 3 uint8 -> ASCII picture (H x W x 3 uint8), same shading rules as the app."""
    small = cv2.resize(rgb, (COLS, ROWS), interpolation=cv2.INTER_AREA).astype(np.float32)
    lum = (0.2126 * small[..., 0] + 0.7152 * small[..., 1] + 0.0722 * small[..., 2]) / 255.0
    p = np.pad(lum, 1, mode="edge")
    left, right, above, below = p[1:-1, :-2], p[1:-1, 2:], p[:-2, 1:-1], p[2:, 1:-1]
    local = (left + right + above + below) / 4
    edge = np.minimum(1, np.abs(right - left) * 2.2 + np.abs(below - above) * 2.2 + np.abs(lum - local) * 1.4)
    tonal = np.clip((lum - 0.025) * 1.12, 0, 1)
    shade = tonal ** 0.76 * (0.34 + 0.66 * np.minimum(1, edge * 2.6))
    idx = 1 + np.minimum(len(CHARS) - 2, np.floor(shade * (len(CHARS) - 2)).astype(np.int32))
    idx[(small.max(axis=2) < 10) | (shade < 0.045)] = 0
    col = np.clip(small * 1.3, 0, 255)                       # a touch brighter: tiny glyphs look dim otherwise
    masks = atlas[idx]                                        # ROWS x COLS x CH x CW
    img = masks[..., None] * col[:, :, None, None, :]         # ROWS x COLS x CH x CW x 3
    img = img.transpose(0, 2, 1, 3, 4).reshape(ROWS * CH, COLS * CW, 3)
    glow = cv2.GaussianBlur(img, (0, 0), 3.0)
    return np.clip(img + glow * 0.45, 0, 255).astype(np.uint8)

def compose(rgb):
    out = rgb.copy()
    a = ascii_frame(rgb)
    mid = int(W * float(os.environ.get("SPLIT", 0.5)))   # SPLIT=0.8 moves the divider right when the subject sits on the right
    out[:, mid:] = a[:, mid:]
    glow = np.zeros_like(out, np.float32); glow[:, mid - 1:mid + 1] = CYAN
    glow = cv2.GaussianBlur(glow, (0, 0), 5)
    out = np.clip(out.astype(np.float32) + glow * 1.2, 0, 255).astype(np.uint8)
    out[:, mid - 1:mid + 1] = CYAN
    return out

def run(src, dst, seconds, ss=0.0, crop=None):
    vf = (f"crop={crop}," if crop else "") + f"scale={W}:{H}:flags=area,fps={FPS}"
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(ss), "-i", src, "-t", str(seconds), "-an",
                            "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "29", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        enc.stdin.write(compose(np.frombuffer(buf, np.uint8).reshape(H, W, 3)).tobytes()); n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    print(dst, n, "frames")

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]) if len(sys.argv)>4 else 0.0, sys.argv[5] if len(sys.argv)>5 else None)
