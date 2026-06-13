# Server setup / migration guide (Amsterdam VPS)

Fresh Ubuntu/Debian VPS, run everything as `root`. Replace `OLD_SERVER_IP`
with the old server's IP where noted.

## 0. Confirm Telegram is reachable (do this first!)

```bash
curl -o /dev/null -s -w "telegram: %{time_total}s (code %{http_code})\n" \
  https://api.telegram.org --connect-timeout 5
```
Fast reply (any code, even 404) = clean route, continue. Hangs = wrong region.

## 1. System packages

```bash
apt update && apt -y upgrade
apt -y install python3 python3-venv python3-pip ffmpeg redis-server git curl
# Docker (for the bot-api server)
curl -fsSL https://get.docker.com | sh
systemctl enable --now redis-server docker
```

## 2. Get the code

```bash
cd /root
git clone https://github.com/komronium/video-to-audio-bot.git
cd video-to-audio-bot
python3 -m venv venv
venv/bin/pip install -U pip
venv/bin/pip install -r requirements.txt
```

## 3. Bring over data from the old server

Run these **from the old server** (or via your laptop):
```bash
scp /root/video-to-audio-bot/.env          root@NEW_SERVER_IP:/root/video-to-audio-bot/
scp /root/video-to-audio-bot/database.db   root@NEW_SERVER_IP:/root/video-to-audio-bot/
scp /root/video-to-audio-bot/cookies.txt   root@NEW_SERVER_IP:/root/video-to-audio-bot/
```
Then edit `.env` on the new server and make sure `TELEGRAM_API_ID` and
`TELEGRAM_API_HASH` are set (copy from the old bot-api config, or get fresh at
https://my.telegram.org). See `.env.example` for all fields.

## 4. Start the local Telegram Bot API server

```bash
cd /root/video-to-audio-bot/deploy
docker compose up -d
docker compose logs --tail 20      # should show it listening on 8081
```

## 5. Install and start the bot service

```bash
cp /root/video-to-audio-bot/deploy/video-to-audio-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now video-to-audio-bot
journalctl -u video-to-audio-bot -n 30 -f
```
Look for `Started 5 conversion workers` and the "BOT IS UP" group message.

## 6. Stop the old server

Only after the new bot answers in Telegram (two instances polling the same
token conflict):
```bash
# on the OLD server:
systemctl stop video-to-audio-bot && systemctl disable video-to-audio-bot
```

## 7. (Optional) Admin dashboard

```bash
venv/bin/pip install -r webapp/requirements.txt
cp deploy/video-to-audio-bot.service /tmp/   # use webapp/bot-admin.service as a template
```
