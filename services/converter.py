import asyncio
from pathlib import Path


class NoAudioError(Exception):
    pass


class VideoConverter:
    def __init__(self):
        Path("audios").mkdir(exist_ok=True)

    async def convert_video_to_audio(self, video_path: str, output_path: str) -> str:
        audio_path = f"{output_path}.mp3"

        cmd = [
            "ffmpeg", "-v", "error",
            "-threads", "1",
            "-i", video_path,
            "-vn", audio_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        err_text = stderr.decode()

        if process.returncode != 0:
            no_audio_hints = (
                "matches no streams",
                "does not contain any stream",
                "Output file does not contain",
            )
            if any(hint in err_text for hint in no_audio_hints):
                raise NoAudioError("Video has no audio stream")
            raise RuntimeError(f"ffmpeg failed: {err_text}")

        return audio_path
