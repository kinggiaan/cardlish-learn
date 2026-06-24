"""Quick debug: check audio files for cards 43-48."""
import os

for n in range(43, 49):
    f = f"public/audio/{n:03d}_card.mp3"
    if os.path.exists(f):
        size = os.path.getsize(f)
        hdr = open(f, "rb").read(4)
        is_mp3 = hdr[:3] == b"ID3"
        print(f"  {f}: {size:,} bytes, header={hdr.hex()}, MP3={is_mp3}")
    else:
        print(f"  {f}: NOT FOUND")
