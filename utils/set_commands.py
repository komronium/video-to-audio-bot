from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

# Per-language command descriptions; "en" is also the default fallback
_COMMANDS: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("start", "Restart the bot"),
        ("help", "How to use"),
        ("profile", "Your profile and diamonds"),
        ("diamonds", "Buy diamonds"),
        ("referral", "Invite friends, earn diamonds"),
        ("top", "Top users"),
        ("stats", "Bot statistics"),
        ("lang", "Change language"),
    ],
    "uz": [
        ("start", "Botni qayta ishga tushirish"),
        ("help", "Qanday ishlatiladi"),
        ("profile", "Profil va olmoslaringiz"),
        ("diamonds", "Olmos sotib olish"),
        ("referral", "Do'st taklif qilib olmos oling"),
        ("top", "Eng faol foydalanuvchilar"),
        ("stats", "Bot statistikasi"),
        ("lang", "Tilni o'zgartirish"),
    ],
    "ru": [
        ("start", "Перезапустить бота"),
        ("help", "Как пользоваться"),
        ("profile", "Профиль и алмазы"),
        ("diamonds", "Купить алмазы"),
        ("referral", "Пригласить друзей и получить алмазы"),
        ("top", "Топ пользователей"),
        ("stats", "Статистика бота"),
        ("lang", "Сменить язык"),
    ],
    "ar": [
        ("start", "إعادة تشغيل البوت"),
        ("help", "طريقة الاستخدام"),
        ("profile", "ملفك الشخصي وألماسك"),
        ("diamonds", "شراء الألماس"),
        ("referral", "ادعُ أصدقاءك واكسب الألماس"),
        ("top", "أفضل المستخدمين"),
        ("stats", "إحصائيات البوت"),
        ("lang", "تغيير اللغة"),
    ],
    "fa": [
        ("start", "راه‌اندازی مجدد ربات"),
        ("help", "نحوه استفاده"),
        ("profile", "پروفایل و الماس‌های شما"),
        ("diamonds", "خرید الماس"),
        ("referral", "دعوت دوستان و دریافت الماس"),
        ("top", "برترین کاربران"),
        ("stats", "آمار ربات"),
        ("lang", "تغییر زبان"),
    ],
    "id": [
        ("start", "Mulai ulang bot"),
        ("help", "Cara penggunaan"),
        ("profile", "Profil & berlian Anda"),
        ("diamonds", "Beli berlian"),
        ("referral", "Undang teman, dapatkan berlian"),
        ("top", "Pengguna teratas"),
        ("stats", "Statistik bot"),
        ("lang", "Ganti bahasa"),
    ],
}


async def set_default_commands(bot: Bot):
    scope = BotCommandScopeAllPrivateChats()
    for lang, commands in _COMMANDS.items():
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in commands],
            scope=scope,
            language_code=None if lang == "en" else lang,
        )
