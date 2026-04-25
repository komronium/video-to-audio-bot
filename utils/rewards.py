from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message

from services.user_service import UserService
from utils.i18n import i18n


async def check_and_notify_rewards(
    message: Message,
    user_id: int,
    user_service: UserService,
    lang: str,
):
    should_reward, _ = await user_service.check_referral_reward(user_id)
    if should_reward:
        granted, inviter_user_id = await user_service.grant_referral_reward(user_id)
        if granted and inviter_user_id:
            inviter_lang = await user_service.get_lang(inviter_user_id)
            try:
                await message.bot.send_message(
                    inviter_user_id,
                    i18n.get_text("referral-inviter-bonus", inviter_lang),
                )
            except TelegramAPIError:
                pass
        await message.answer(i18n.get_text("referral-bonus", lang))

    milestone_diamonds = await user_service.check_milestone_rewards(user_id)
    if milestone_diamonds > 0:
        await user_service.grant_milestone_reward(user_id, milestone_diamonds)
        await message.answer(i18n.get_text("milestone-bonus", lang).format(milestone_diamonds))
