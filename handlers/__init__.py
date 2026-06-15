from aiogram import Dispatcher

from . import (
    admin,
    contest,
    diamonds,
    error,
    fallback,
    help,
    post,
    profile,
    promo,
    referral,
    social,
    start,
    stats,
    subscription,
    top,
    video,
)


def setup_handlers(dp: Dispatcher):
    dp.include_router(start.router)
    dp.include_router(help.router)
    dp.include_router(stats.router)
    dp.include_router(top.router)
    dp.include_router(profile.router)
    dp.include_router(subscription.router)
    dp.include_router(video.router)
    # Admin flows that hold FSM state must register before the broadcast
    # handler — otherwise their text inputs get swallowed as broadcast content.
    dp.include_router(promo.router)
    dp.include_router(contest.router)
    dp.include_router(post.router)
    dp.include_router(social.router)
    dp.include_router(referral.router)
    dp.include_router(error.router)
    dp.include_router(diamonds.router)
    dp.include_router(admin.router)
    # Catch-all — must stay last so it only sees genuinely unhandled messages
    dp.include_router(fallback.router)
