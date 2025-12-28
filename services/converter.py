import requests
import ffmpeg
from pathlib import Path
from typing import List, Union
from config import settings


class VideoConverter:

    def __init__(self):
        self.output_dir = Path('videos')
        self.output_dir.mkdir(exist_ok=True)

    async def convert_video_to_audio(self, video_path: str, output_base: str, formats: List[str] = None) -> Union[str, dict]:
        """Convert input video to one or more audio formats.

        - `formats` is a list that can include `'mp3'` and/or `'voice'`.
          `'voice'` produces an OGG/OPUS file suitable for Telegram voice messages.
        - If only one format is requested, returns the output path string.
        - If multiple formats requested, returns a dict {format: path}.

        Returns a dict with `code='NO_AUDIO'` on no audio stream or
        `{'error':..., 'message':...}` on ffmpeg failure.
        """
        if formats is None:
            formats = ['mp3']

        try:
            probe = ffmpeg.probe(video_path)
            audio_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']

            if not audio_streams:
                return {'error': 'No audio stream', 'code': 'NO_AUDIO'}

            outputs = {}

            for fmt in formats:
                if fmt == 'mp3':
                    out_path = f"{output_base}.mp3"
                    try:
                        (
                            ffmpeg
                            .input(video_path)
                            .output(out_path, **{
                                'vn': None,
                                'acodec': 'libmp3lame',
                                'audio_bitrate': '192k',
                                'ar': 44100,
                                'ac': 2,
                                'loglevel': 'error'
                            })
                            .overwrite_output()
                            .run()
                        )
                    except ffmpeg.Error as e:
                        return {'error': 'Conversion failed', 'message': e.stderr.decode()}
                    outputs['mp3'] = out_path

                elif fmt == 'voice':
                    # Telegram voice messages: OGG container with OPUS codec, mono, 48000 Hz
                    out_path = f"{output_base}.ogg"
                    try:
                        (
                            ffmpeg
                            .input(video_path)
                            .output(out_path, **{
                                'vn': None,
                                'acodec': 'libopus',
                                'audio_bitrate': '64k',
                                'ar': 48000,
                                'ac': 1,
                                'format': 'ogg',
                                'loglevel': 'error'
                            })
                            .overwrite_output()
                            .run()
                        )
                    except ffmpeg.Error as e:
                        return {'error': 'Conversion failed', 'message': e.stderr.decode()}
                    outputs['voice'] = out_path

                else:
                    # unsupported format
                    continue

            if len(outputs) == 1:
                return next(iter(outputs.values()))
            return outputs

        except ffmpeg.Error as e:
            return {'error': 'Conversion failed', 'message': e.stderr.decode()}


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
      
