import ffmpeg
from yt_dlp import YoutubeDL


def convert_video_to_audio(video_path: str, output_path: str) -> str:
    try:
        audio_path = f'{output_path}.mp3'
        ffmpeg.input(video_path).output(audio_path, format='mp3').run(overwrite_output=True, quiet=True)
        return audio_path
    except Exception as e:
        raise RuntimeError(f'Error during conversion: {e}')


def get_youtube_video(video_url: str):
    output_path = 'videos/%(title)s.%(ext)s'

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': output_path
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        print(ydl.prepare_filename(info))
        filename = ydl.prepare_filename(info)

    return filename
