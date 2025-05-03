# file: services/video_creator.py | created: 2025-05-03 10:30 (UTC+3)

import subprocess
from pathlib import Path
from PIL import Image
import numpy as np
import tempfile
import logging

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTION = (1080, 1080)
DEFAULT_FPS = 30

def create_video_with_ffmpeg(
    post_id: str,
    image_paths: list,
    frame_duration: float = 2.0,
    transition_duration: float = 1.0,
    audio_enabled: bool = False
) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"ffmpeg_{post_id}_"))
    output_path = Path("output") / f"{post_id}_video.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        logger.info(f"🎞 Генерация кадров для поста {post_id}")
        frame_files = []

        for i, image_path in enumerate(image_paths):
            with Image.open(image_path) as img:
                img = img.convert("RGB").resize(DEFAULT_RESOLUTION)
                frame_file = temp_dir / f"frame_{i:04d}.png"
                img.save(frame_file)
                frame_files.append(frame_file)

        # Создание input.txt
        input_txt = temp_dir / "input.txt"
        with open(input_txt, "w") as f:
            for file in frame_files:
                f.write(f"file '{file}'\n")
                f.write(f"duration {frame_duration}\n")
            f.write(f"file '{frame_files[-1]}'\n")

        temp_video = temp_dir / "temp_video.mp4"
        cmd_video = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(input_txt),
            "-vsync", "vfr",
            "-pix_fmt", "yuv420p",
            "-vf", f"fps={DEFAULT_FPS}",
            "-s", f"{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}",
            str(temp_video)
        ]
        subprocess.run(cmd_video, check=True)

        if audio_enabled:
            audio_path = Path("assets/default.mp3")
            cmd_audio = [
                "ffmpeg", "-y",
                "-i", str(temp_video),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path)
            ]
            subprocess.run(cmd_audio, check=True)
        else:
            temp_video.rename(output_path)

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg ошибка: {e}")
        raise RuntimeError(f"FFmpeg error: {e}")
    finally:
        for f in temp_dir.glob("*"):
            f.unlink()
        temp_dir.rmdir()
