import ffmpeg


def convert_video_to_audio(video_path: str, output_path: str) -> str:
    try:
        audio_path = f'{output_path}.mp3'
        ffmpeg. output(audio_path, format='mp3').run(overwrite_output=True, quiet=True)
        return audio_path
    except Exception as e:
        raise RuntimeError(f'Error during conversion: {e}')
