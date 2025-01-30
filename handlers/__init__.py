from aiogram import Dispatcher

from . import start, stats, profile, subscription, video


def setup_handlers(dp: Dispatcher):
    dp.include_router(start.router)
    dp.include_router(stats.router)
    dp.include_router(profile.router)
    dp.include_router(subscription.router)
    dp.include_router(video.router)
