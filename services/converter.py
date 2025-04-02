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
        link = audio_data.get('link')

        try:     
            response = requests.get(link)
        except MissingSchema as e:
            return {
                'error': 'Invalid URL',
                'link': link,
                'message': str(e)
            }
        
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            filename = urllib.parse.unquote(content_disposition.split('filename=')[1].strip('"'))
            file_path = self.output_dir / filename
            with open(file_path, 'wb') as f:
                f.write(response.content)
        else:
            raise RuntimeError('No filename in response headers')
        
        audio_data['file_path'] = str(file_path)
        return audio_data
      
