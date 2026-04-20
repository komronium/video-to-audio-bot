# Project Structure (Proposed Clean Architecture)

## Current vs Proposed

```
CURRENT                          PROPOSED
───────────────────────────────────────────────────────
video-to-audio-bot/              video-to-audio-bot/
├── config.py                    ├── config.py           ✅ keep
├── main.py                      ├── main.py             ✅ keep
├── requirements.txt             ├── requirements.txt    ✅ keep
│
├── database/                    ├── database/           ✅ keep
│   ├── models.py                │   ├── models.py
│   └── session.py               │   └── session.py
│
├── services/                    ├── services/           ✅ keep
│   ├── user_service.py          │   ├── user_service.py
│   ├── converter.py             │   ├── converter.py
│   └── redis_queue.py           │   └── queue.py        ← rename
│
├── handlers/                    ├── handlers/           ✅ keep
│   ├── __init__.py              │   ├── __init__.py
│   ├── start.py                 │   ├── start.py
│   ├── video.py                 │   ├── video.py
│   ├── youtube.py               │   ├── youtube.py
│   ├── diamonds.py              │   ├── diamonds.py
│   ├── profile.py               │   ├── profile.py
│   ├── stats.py                 │   ├── stats.py
│   ├── post.py                  │   ├── broadcast.py    ← rename
│   ├── top.py                   │   └── admin.py        ← merge top+admin
│   ├── admin.py                 │
│   ├── help.py                  │   (help, subscription, error → merge into start.py)
│   ├── subscription.py          │
│   └── error.py                 │
│
├── keyboards/                   ├── keyboards/          ✅ keep
├── middlewares/                 ├── middlewares/        ✅ keep
├── states/                      ├── states/             ✅ keep
├── locales/                     ├── locales/            ✅ keep
├── utils/                       ├── utils/              ✅ keep
│
└── webapp/                      └── admin/              ← rename webapp → admin
    ├── api.py                       ├── api.py
    ├── requirements.txt             └── frontend/
    └── frontend/
```

## Priority Changes

### 1. Rename `webapp/` → `admin/`
```bash
mv webapp admin
# Update systemd service WorkingDirectory if needed
```

### 2. Merge small handlers
- `help.py` + `subscription.py` + `error.py` → merge into `start.py` or a single `misc.py`
- `top.py` → merge into `stats.py`
- `post.py` → rename to `broadcast.py` (clearer intent)

### 3. Rename `redis_queue.py` → `queue.py`

### 4. Bot requirements
Currently there are TWO requirements.txt:
- `/requirements.txt` — bot dependencies  
- `/webapp/requirements.txt` — admin API dependencies

**Option A (simple):** Keep separate — run bot and admin in separate venvs  
**Option B (unified):** Merge into one `requirements.txt`

## What NOT to change
- `config.py` — already clean with pydantic Settings
- `database/` — models are fine
- `services/` — clean separation of concerns
- `middlewares/` — good structure
- `locales/` — i18n works fine

## Handler consolidation detail

### `misc.py` (new, replaces help + subscription + error)
```python
# handlers/misc.py
@router.message(Command("help"))      # from help.py
@router.message(Command("start"))     # keep in start.py
@router.errors()                      # from error.py
@router.message(F.text == "Subscribe")  # from subscription.py
```

### `stats.py` (absorbs top.py)
```python
# Currently stats.py has /stats command
# top.py has /top command  
# → merge both into stats.py
```

## Code quality improvements

### 1. Type hints everywhere
```python
# Current
async def get_user(self, user_id: int):
    ...
    return result.scalars().first()  # return type unknown

# Better  
async def get_user(self, user_id: int) -> User | None:
    ...
```

### 2. Constants file
```python
# constants.py
MAX_FILE_SIZE = 26_214_400  # 25 MB
DAILY_LIMIT = 5
MAX_QUEUE_SIZE = 50
MAX_CONCURRENT = 5
DIAMOND_PRICES = {1: 2, 3: 5, 5: 8, 10: 15, 20: 28, 50: 70}
LIFETIME_STARS = 200
```

### 3. Remove dead `__pycache__` from git
```bash
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
find . -type d -name __pycache__ -exec git rm -r --cached {} + 2>/dev/null
```
