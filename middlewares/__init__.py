from aiogram import Dispatcher
from aiogram.utils.i18n.core import I18n

from .i18n import I18nMiddleware
from .throttling import ThrottlingMiddleware
from .subscription import SubscriptionMiddleware
from .database import DatabaseMiddleware


def setup_middlewares(dp: Dispatcher):
    dp.message.middleware(I18nMiddleware(I18n))
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
