import asyncio
import ffmpeg
from pathlib import Path
from yt_dlp import YoutubeDL


class VideoConverter:

    def __init__(self):
        self.output_dir = Path('videos')
        self.output_dir.mkdir(exist_ok=True)

    async def convert_video_to_audio(self, video_path: str, output_path: str) -> str:
        try:
            audio_path = f'{output_path}.mp3'
            await asyncio.to_thread(
                ffmpeg.input(video_path)
                .output(audio_path, format='mp3')
                .run,
                overwrite_output=True, 
                quiet=True
            )
            return audio_path
        except Exception as e:
            raise RuntimeError(f'Error during conversion: {e}')


    async def get_youtube_video(self, video_url: str):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'outtmpl': str(self.output_dir / '%(title)s.%(ext)s'),
            'cookiefile': 'cookies.txt',
            'noplaylist': True,
            'extract_flat': False
        }

        try:
            def download():
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    path = ydl.prepare_filename(info)
                    filename = info.get('title')
                    return path, filename
                
            path, filename = await asyncio.to_thread(download)
            return path, filename
        except Exception as e:
            raise RuntimeError(f'Error during downloading: {e}')
