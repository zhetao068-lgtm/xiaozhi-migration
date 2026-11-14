"""用三个合成音生成小智 notify 示例所需的单声道 Ogg Opus。"""

import argparse
import math
import struct
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", default="ffmpeg")
    options = parser.parse_args()
    output = Path(__file__).resolve().with_name("study-chime.ogg")
    rate = 48000
    note_frames = rate // 2
    samples = bytearray()
    for frequency in (523.25, 659.25, 783.99):
        for frame in range(note_frames):
            t = frame / rate
            envelope = min(t * 60, 1) * math.exp(-t * 5) * min((0.5 - t) * 20, 1)
            samples.extend(struct.pack("<h", round(8000 * envelope * math.sin(math.tau * frequency * t))))
    subprocess.run([
        options.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
        "-c:a", "libopus", "-b:a", "24k", "-frame_duration", "20", str(output),
    ], input=samples, check=True)
    print(output)


if __name__ == "__main__":
    main()
