import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from enum import Enum
from PIL import Image, ImageOps
import json

logger = logging.getLogger(__name__)

class VideoAspectRatio(Enum):
    SQUARE = "square"        # 1:1 (1080x1080)
    HORIZONTAL = "horizontal" # 16:9 (1920x1080)
    VERTICAL = "vertical"    # 9:16 (1080x1920)
    CUSTOM = "custom"        # Custom resolution

class VideoSettings:
    def __init__(
        self,
        frame_duration: float = 3.0,
        transition_duration: float = 1.0,
        transition_type: str = "fade",
        aspect_ratio: str = "square",
        custom_width: Optional[int] = None,
        custom_height: Optional[int] = None,
        transition_params: Dict = None,
        background_color: str = "#000000",
        loop: bool = True
    ):
        self.frame_duration = frame_duration
        self.transition_duration = transition_duration
        self.transition_type = transition_type.lower()
        self.aspect_ratio = VideoAspectRatio(aspect_ratio.lower())
        self.custom_width = custom_width
        self.custom_height = custom_height
        self.transition_params = transition_params or {}
        self.background_color = background_color
        self.loop = loop

    @classmethod
    def from_dict(cls, data: dict) -> "VideoSettings":
        return cls(**{
            "frame_duration": data.get("frame_duration", 3.0),
            "transition_duration": data.get("transition_duration", 1.0),
            "transition_type": data.get("transition_type", "fade"),
            "aspect_ratio": data.get("aspect_ratio", "square"),
            "custom_width": data.get("custom_width"),
            "custom_height": data.get("custom_height"),
            "transition_params": data.get("transition_params", {}),
            "background_color": data.get("background_color", "#000000"),
            "loop": data.get("loop", True)
        })

    def to_dict(self) -> dict:
        return {
            "frame_duration": self.frame_duration,
            "transition_duration": self.transition_duration,
            "transition_type": self.transition_type,
            "aspect_ratio": self.aspect_ratio.value,
            "custom_width": self.custom_width,
            "custom_height": self.custom_height,
            "transition_params": self.transition_params,
            "background_color": self.background_color,
            "loop": self.loop
        }

    def get_resolution(self) -> Tuple[int, int]:
        resolutions = {
            VideoAspectRatio.SQUARE: (1080, 1080),
            VideoAspectRatio.HORIZONTAL: (1920, 1080),
            VideoAspectRatio.VERTICAL: (1080, 1920),
            VideoAspectRatio.CUSTOM: (
                self.custom_width or 1080, 
                self.custom_height or 1080
            )
        }
        return resolutions.get(self.aspect_ratio, (1080, 1080))

TRANSITION_CONFIG = {
    "fade": {"params": "", "supported_options": []},
    "slide": {"params": ":direction=right", "supported_options": ["direction"]},
    "wipe": {"params": ":direction=right", "supported_options": ["direction"]},
    "circleopen": {"params": "", "supported_options": []},
    "zoom": {"params": "", "supported_options": []},
    "distance": {"params": ":distance_threshold=0.5", "supported_options": ["distance_threshold"]},
    "hlslice": {"params": ":slice_count=10", "supported_options": ["slice_count"]},
    "rectcrop": {"params": ":rect_width=0.5:rect_height=0.5", "supported_options": ["rect_width", "rect_height"]},
    "smoothness": {"params": ":smoothness=0.5", "supported_options": ["smoothness"]}
}

def prepare_image(
    image_path: Path,
    output_path: Path,
    resolution: Tuple[int, int],
    background_color: str = "#000000"
) -> bool:
    """Подготавливает изображение с заполнением всего кадра без черных рамок"""
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            # Используем fit вместо thumbnail для полного заполнения
            img = ImageOps.fit(
                img, 
                resolution, 
                method=Image.LANCZOS,
                bleed=0.0,
                centering=(0.5, 0.5)
            )
            img.save(output_path, quality=95)
            return True
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {e}")
        return False

def build_transition_params(transition_type: str, custom_params: Dict) -> str:
    """Строит строку параметров перехода с валидацией"""
    config = TRANSITION_CONFIG.get(transition_type.lower(), TRANSITION_CONFIG["fade"])
    base_params = config["params"]
    
    valid_params = {
        k: v for k, v in custom_params.items() 
        if k in config["supported_options"]
    }
    
    if valid_params:
        custom_str = ":".join(f"{k}={v}" for k, v in valid_params.items())
        return f"{base_params}:{custom_str}" if base_params else f":{custom_str}"
    return base_params

def create_video(
    images: List[Path],
    output_path: Path,
    settings: VideoSettings,
    music_path: Optional[Path] = None,
    fps: int = 30
) -> bool:
    """Создает видео с плавными переходами и зацикленностью (если loop=True)"""
    if not images or len(images) < 2:
        logger.error("❌ Need at least 2 images for video")
        return False

    temp_dir = Path(tempfile.mkdtemp(prefix="video_"))
    try:
        ffmpeg_check = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if ffmpeg_check.returncode != 0:
            logger.error(f"FFmpeg not available: {ffmpeg_check.stderr}")
            return False

        resolution = settings.get_resolution()
        logger.info(f"🎬 Creating {resolution[0]}x{resolution[1]} video")

        input_files = []
        for i, img_path in enumerate(images):
            frame_file = temp_dir / f"frame_{i:03d}.jpg"
            if prepare_image(img_path, frame_file, resolution, settings.background_color):
                input_files.append(frame_file)

        if len(input_files) < 2:
            logger.error("❌ Not enough valid images after processing")
            return False

        filter_complex = []
        inputs = []
        duration = settings.frame_duration + settings.transition_duration
        transition_params = build_transition_params(settings.transition_type, settings.transition_params)

        for idx, frame_path in enumerate(input_files):
            inputs.extend(["-loop", "1", "-t", str(duration), "-i", str(frame_path)])

        # Создаем цепочку переходов
        for i in range(len(input_files) - 1):
            current = f"[v{i}]" if i > 0 else f"[0:v]"
            next_input = f"[{i+1}:v]"
            out = f"[v{i+1}]"
            offset = i * settings.frame_duration
            filter_complex.append(
                f"{current}{next_input}xfade=transition={settings.transition_type}:"
                f"duration={settings.transition_duration}:offset={offset:.2f}{transition_params}{out}"
            )

        # Зацикливаем: добавляем последний переход imgN → img0
        if settings.loop:
            last = f"[v{len(input_files) - 1}]"
            first = f"[0:v]"
            filter_complex.append(
                f"{last}{first}xfade=transition={settings.transition_type}:"
                f"duration={settings.transition_duration}:offset={(len(input_files) - 1) * settings.frame_duration:.2f}"
                f"{transition_params}[final]"
            )
            map_to = "final"
        else:
            map_to = f"v{len(input_files) - 1}"

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *inputs,
            "-filter_complex", "; ".join(filter_complex),
            "-map", f"[{map_to}]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]

        # Добавляем аудио только если явно передано
        if music_path and music_path.exists():
            cmd += [
                "-i", str(music_path),
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest"
            ]
        else:
            cmd.append("-an")  # без звука — зацикленное видео в Telegram

        cmd.append(str(output_path))

        logger.debug(f"[FFMPEG] Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error (code {result.returncode}): {result.stderr}")
            return False

        logger.info(f"✅ Video successfully created: {output_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Video creation failed: {e}", exc_info=True)
        return False

    finally:
        for file in temp_dir.glob("*"):
            try:
                file.unlink()
            except Exception:
                pass
        try:
            temp_dir.rmdir()
        except Exception:
            pass


def check_ffmpeg_available() -> bool:
    """Проверяет доступность FFmpeg в системе"""
    try:
        return subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True
        ).returncode == 0
    except Exception:
        return False