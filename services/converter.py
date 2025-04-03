import asyncio
import requests
import urllib.parse
import ffmpeg
from pathlib import Path
from requests.exceptions import MissingSchema
from config import settings


class VideoConverter:

    def __init__(self):
        self.output_dir = Path('videos')
        self.output_dir.mkdir(exist_ok=True)

    async def convert_video_to_audio(self, video_path: str, output_path: str) -> str:
        try:
            audio_path = f'{output_path}.mp3'
            process = (
                ffmpeg
                .input(video_path)
                .output(audio_path, format='mp3')
                .run_async(pipe_stdout=True, pipe_stderr=True)
            )
            _, error = process.communicate()

            if process.returncode != 0:
                return {
                    'error': 'Conversion failed',
                    'message': error.decode('utf-8')
                }
            
            return audio_path
        except Exception as e:
            raise RuntimeError(f'Error during conversion: {e}')


    async def get_youtube_video(self, video_id: str):
        done = False

        while not done:
            url = f'https://youtube-mp36.p.rapidapi.com/dl?id={video_id}'
            headers = {
                'x-rapidapi-host': settings.API_HOST,
                'x-rapidapi-key': settings.API_KEY,
            }

            response = requests.get(url, headers=headers)
            done = response.json().get('status') != 'processing'
        if response.status_code != 200:
            raise RuntimeError(f'Error fetching video: {response.status_code}')
        
        audio_data = response.json()
        
        return audio_data
      
