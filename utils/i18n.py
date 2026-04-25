import json
from pathlib import Path


class I18n:
    def __init__(self, default_lang: str = "en", locales_dir: str = "locales"):
        self.default_lang = default_lang
        self.locales: dict[str, dict] = {}
        self.LANGUAGES: list[str] = []
        self._load(locales_dir)

    def _load(self, locales_dir: str):
        for path in sorted(Path(locales_dir).glob("*.json")):
            lang = path.stem
            with open(path, encoding="utf-8") as f:
                self.locales[lang] = json.load(f)
            self.LANGUAGES.append(lang)

    def get_text(self, key: str, lang: str = "en") -> str:
        lang = lang or self.default_lang
        locale = self.locales.get(lang, {})
        return locale.get(key) or self.locales[self.default_lang].get(key) or key


i18n = I18n()
