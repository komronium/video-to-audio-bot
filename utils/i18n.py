import json
from pathlib import Path

class I18n:
    def __init__(self, default_lang='en', locales_dir='locales'):
        self.default_lang = default_lang
        self.locales = {}
        self.load_locales(locales_dir)

    def load_locales(self, locales_dir):
        for loc_file in Path(locales_dir).glob('*.json'):
            lang = loc_file.stem
            with open(loc_file, encoding='utf-8') as f:
                self.locales[lang] = json.load(f)

    def get_text(self, key, lang=None):
        lang = lang or self.default_lang
        return self.locales.get(lang, {}).get(key, self.locales[self.default_lang].get(key, key))


i18n = I18n()
