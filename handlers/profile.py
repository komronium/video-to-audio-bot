from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def _fmt(n: int) -> str:
    return f"{n:,}"


@router.message(
    F.text.in_([i18n.get_text("profile-button", lang) for lang in i18n.LANGUAGES])
)
async def profile_handler(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    lang = await user_service.get_lang(message.from_user.id)

    if not user:
        return await message.answer("⚠️ Not registered.")

    conversions = await user_service.get_conversion_count(user.user_id)
    rank = await user_service.get_user_rank(user.user_id)
    total_users = await user_service.total_users()

    if user.is_premium:
        status = "👑 Premium"
        diamonds_text = "♾️"
    else:
        status = "Free"
        diamonds_text = str(user.diamonds or 0)

    text = i18n.get_text("profile", lang).format(
        name=user.name or "—",
        username=user.username or "N/A",
        user_id=user.user_id,
        conversions=_fmt(conversions),
        rank=rank or "—",
        total=_fmt(total_users),
        diamonds=diamonds_text,
        joined=user.joined_at.strftime("%d.%m.%Y"),
        status=status,
    )

    return await message.answer(text.strip())
