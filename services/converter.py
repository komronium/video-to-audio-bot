from moviepy import VideoFileClip


def convert_video_to_audio(video_path: str, output_path: str) -> str:
    try:
        clip = VideoFileClip(video_path)
        audio_path = f'{output_path}.mp3'
        clip.audio.write_audiofile(audio_path, logger=None)
        clip.close()
        return audio_path
    except Exception as e:
        raise RuntimeError(f'Error during conversion: {e}')
