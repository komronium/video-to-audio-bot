import requests
import ffmpeg
from pathlib import Path
from config import settings


class VideoConverter:

    def __init__(self):
        self.output_dir = Path('videos')
        self.output_dir.mkdir(exist_ok=True)

    async def convert_video_to_audio(self, video_path: str, output_path: str) -> str:
        try:
            probe = ffmpeg.probe(video_path)
            audio_streams = [
                s for s in probe.get('streams', [])
                if s.get('codec_type') == 'audio'
            ]

            if not audio_streams:
                return {
                    'error': 'No audio stream',
                    'code': 'NO_AUDIO',
                }

            audio_path = f'{output_path}.aac'

            (
                ffmpeg
                .input(video_path)
                .output(
                    audio_path,
                    vn=None,            # video butunlay o‘chadi
                    acodec='copy',      # 🔥 re-encode YO‘Q
                    loglevel='error'
                )
                .overwrite_output()
                .run()
            )

            return audio_path

        except ffmpeg.Error as e:
            return {
                'error': 'Conversion failed',
                'message': e.stderr.decode()
            }


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
      
