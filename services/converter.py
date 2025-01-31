from moviepy import VideoFileClip
from proglog import ProgressBarLogger


class ProgressLogger(ProgressBarLogger):

    def callback(self, **changes):
        for (parameter, value) in changes.items():
            print ('Parameter %s is now %s' % (parameter, value))

    def bars_callback(self, bar, attr, value, old_value=None):
        percentage = (value / self.bars[bar]['total']) * 100
        print(bar, attr, percentage)


def convert_video_to_audio(video_path: str, output_path: str) -> str:
    try:
        clip = VideoFileClip(video_path)
        audio_path = f'{output_path}.mp3'
        logger = ProgressLogger()
        clip.audio.write_audiofile(audio_path, logger=logger)
        clip.close()
        return audio_path
    except Exception as e:
        raise RuntimeError(f'Error during conversion: {e}')
