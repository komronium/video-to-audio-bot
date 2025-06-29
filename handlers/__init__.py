from aiogram import Dispatcher

from . import start, help, stats, top, profile, subscription, video, post, premium, youtube, error, diamonds


def setup_handlers(dp: Dispatcher):
    dp.include_router(start.router)
    dp.include_router(help.router)
    dp.include_router(stats.router)
    dp.include_router(top.router)
    dp.include_router(profile.router)
    dp.include_router(subscription.router)
    dp.include_router(video.router)
    dp.include_router(post.router)
    dp.include_router(premium.router)
    dp.include_router(youtube.router)
    dp.include_router(error.router)
    dp.include_router(diamonds.router)
