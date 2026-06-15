from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from services.user_service import UserService
from utils.i18n import i18n
from utils.streak import STREAK_REWARDS, update_streak


def _next_streak_milestone(current: int) -> tuple[int, int] | None:
    """Closest upcoming milestone above the current streak (days, reward)."""
    upcoming = [(d, r) for d, r in STREAK_REWARDS.items() if d > current]
    if not upcoming:
        return None
    return min(upcoming, key=lambda dr: dr[0])


async def check_and_notify_rewards(
    bot: Bot,
    chat_id: int,
    user_id: int,
    user_service: UserService,
    lang: str,
):
    # Referral reward
    should_reward, _ = await user_service.check_referral_reward(user_id)
    if should_reward:
        granted, inviter_user_id = await user_service.grant_referral_reward(user_id)
        if granted and inviter_user_id:
            inviter_lang = await user_service.get_lang(inviter_user_id)
            try:
                await bot.send_message(
                    inviter_user_id,
                    i18n.get_text("referral-inviter-bonus", inviter_lang),
                )
            except TelegramAPIError:
                pass
        await bot.send_message(chat_id, i18n.get_text("referral-bonus", lang))

    # Milestone reward
    milestone_diamonds = await user_service.check_milestone_rewards(user_id)
    if milestone_diamonds > 0:
        await user_service.grant_milestone_reward(user_id, milestone_diamonds)
        await bot.send_message(
            chat_id, i18n.get_text("milestone-bonus", lang).format(milestone_diamonds)
        )

    # Streak reward (no-op when Redis is down)
    streak_days, streak_reward = await update_streak(user_id)
    if streak_reward > 0:
        await user_service.add_diamonds(user_id, streak_reward, record_payment=False)
        await bot.send_message(
            chat_id,
            i18n.get_text("streak-bonus", lang).format(n=streak_days, reward=streak_reward),
        )
    elif streak_days >= 2:
        # Habit hook: show progress to the next streak milestone so the user
        # knows there's a concrete reward waiting if they come back tomorrow.
        upcoming = _next_streak_milestone(streak_days)
        if upcoming:
            target_days, target_reward = upcoming
            try:
                await bot.send_message(
                    chat_id,
                    i18n.get_text("streak-progress", lang).format(
                        n=streak_days,
                        days_left=target_days - streak_days,
                        reward=target_reward,
                    ),
                )
            except TelegramAPIError:
                pass
