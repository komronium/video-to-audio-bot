from aiogram import Router, types
import re

router = Router()

YOUTUBE_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|shorts\/|live\/|c\/|@)|youtu\.be\/)([\w\-]+)"
)
