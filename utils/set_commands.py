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


# Shown above the START button when a user opens the bot for the first time
# (≤512 chars). The single biggest profile-visitor → user conversion lever.
_DESCRIPTIONS: dict[str, str] = {
    "en": "🎬 Send me any video — or a YouTube, TikTok or Instagram link — and I'll turn it into audio (MP3) in seconds.\n\n🎙 Play it instantly or save the file.\n⚡ 3 free conversions every day.\n\n👉 Tap START to begin!",
    "uz": "🎬 Menga istalgan videoni — yoki YouTube, TikTok, Instagram havolasini — yuboring, men uni bir necha soniyada audioga (MP3) aylantiraman.\n\n🎙 Darhol tinglang yoki faylni saqlang.\n⚡ Har kuni 3 ta bepul.\n\n👉 Boshlash uchun START bosing!",
    "ru": "🎬 Отправьте мне любое видео — или ссылку YouTube, TikTok, Instagram — и я превращу его в аудио (MP3) за секунды.\n\n🎙 Слушайте сразу или сохраните файл.\n⚡ 3 бесплатные конвертации каждый день.\n\n👉 Нажмите START, чтобы начать!",
    "ar": "🎬 أرسل لي أي فيديو — أو رابط YouTube أو TikTok أو Instagram — وسأحوّله إلى صوت (MP3) خلال ثوانٍ.\n\n🎙 استمع فوراً أو احفظ الملف.\n⚡ 3 تحويلات مجانية كل يوم.\n\n👉 اضغط START للبدء!",
    "fa": "🎬 هر ویدیویی برایم بفرست — یا لینک YouTube، TikTok یا Instagram — تا در چند ثانیه آن را به صدا (MP3) تبدیل کنم.\n\n🎙 فوراً گوش بده یا فایل را ذخیره کن.\n⚡ هر روز ۳ تبدیل رایگان.\n\n👉 برای شروع START را بزن!",
    "id": "🎬 Kirim video apa saja — atau tautan YouTube, TikTok, Instagram — dan saya ubah jadi audio (MP3) dalam hitungan detik.\n\n🎙 Putar langsung atau simpan filenya.\n⚡ 3 konversi gratis setiap hari.\n\n👉 Tekan START untuk mulai!",
}

# Shown under the bot name in the profile / chat list (≤120 chars)
_SHORT_DESCRIPTIONS: dict[str, str] = {
    "en": "Turn any video or YouTube/TikTok/Instagram link into audio (MP3) in seconds. 🎬→🎵",
    "uz": "Istalgan video yoki YouTube/TikTok/Instagram havolasini soniyalarda audioga aylantiring. 🎬→🎵",
    "ru": "Видео или ссылку YouTube/TikTok/Instagram — в аудио (MP3) за секунды. 🎬→🎵",
    "ar": "حوّل أي فيديو أو رابط YouTube/TikTok/Instagram إلى صوت (MP3) خلال ثوانٍ. 🎬→🎵",
    "fa": "هر ویدیو یا لینک YouTube/TikTok/Instagram را در چند ثانیه به صدا تبدیل کن. 🎬→🎵",
    "id": "Ubah video atau tautan YouTube/TikTok/Instagram jadi audio (MP3) dalam detik. 🎬→🎵",
}


async def set_default_commands(bot: Bot):
    scope = BotCommandScopeAllPrivateChats()
    for lang, commands in _COMMANDS.items():
        code = None if lang == "en" else lang
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in commands],
            scope=scope,
            language_code=code,
        )
        await bot.set_my_description(_DESCRIPTIONS[lang], language_code=code)
        await bot.set_my_short_description(_SHORT_DESCRIPTIONS[lang], language_code=code)
