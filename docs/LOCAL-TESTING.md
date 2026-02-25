# Local Testing Runbook

Use this when you've stopped Docker and need to bring everything back up for local testing.

---

## Prerequisites

- `.env` file filled with real values (Strava, Telegram, ngrok, etc.)
- Strava API app created with correct Authorization Callback Domain
- Telegram bot created and your user ID known

---

## 1. Start the stack

```bash
./ops/scripts/local-start.sh
```

This starts: postgres, api, frontend, nginx. Webhook processing runs in the API process (no separate worker). Wait ~30–60 seconds for all services to become healthy.

---

## 2. Start ngrok

**Option A – Host ngrok (recommended)**

In a separate terminal:

```bash
ngrok http 80
```

Copy the `https://...ngrok-free.app` URL from the ngrok output.

**Option B – Docker ngrok**

```bash
docker compose --profile ngrok up ngrok
```

Then open `http://localhost:4040` in a browser to see the ngrok UI and copy the public URL.

---

## 3. Update Strava Authorization Callback Domain

If your ngrok URL changed (it does every time you restart ngrok unless you use a paid domain):

1. Go to [Strava API Settings](https://www.strava.com/settings/api) → **Edit Application**
2. Set **Authorization Callback Domain** to your ngrok hostname only (no `https://`, no path)
   - Example: `a1b2c3d4.ngrok-free.app`
3. Save

---

## 4. Update `.env` and register webhooks

Set your current ngrok URL in `.env`:

```env
PUBLIC_BASE_URL=https://YOUR-NGROK-URL.ngrok-free.app
```

Then run:

```bash
./ops/scripts/register-webhooks.sh
```

This registers Strava and Telegram webhooks to your current ngrok URL.

---

## 5. Connect Strava (if needed)

You only need this once, or if you reset tokens / change callback domain.

1. Open `http://localhost/` (or your ngrok URL) in a browser.
2. Click **Connect with Strava** — you’ll be redirected to Strava to authorize.
3. After authorizing, you’ll be redirected back to the UI with a success message.
4. Use the toggles to enable or disable:
   - **Run shoe selection** — ask via Telegram which shoes after each run
   - **Gym hide from home** — auto-hide strength workouts from feed

---

## 6. Start chat with Telegram bot (if needed)

In Telegram, find your bot and send any message (e.g. `hi`). The bot won’t reply, but this opens the chat so it can message you when a run needs gear selection.

---

## 7. Test

1. Record or upload a **Run** in Strava (with Run shoe selection enabled)
2. You should get a Telegram message asking which shoes you used
3. Tap a shoe option → Strava activity is updated → you’ll get a confirmation message (“Nice one — [shoe] logged. Well done.”)
4. Record a **Gym/Strength** workout (with Gym hide enabled) → it’s auto-hidden from feed → you’ll get “Gym workout hidden from feed. Strong work.”
5. Scroll down on the settings page to see the events dashboard (always visible when connected)

---

## Quick reference

| Step | Command / action |
|------|------------------|
| Start stack | `./ops/scripts/local-start.sh` |
| Start ngrok | `ngrok http 80` (or `docker compose --profile ngrok up ngrok`) |
| Update Strava callback domain | Strava → Edit Application → Authorization Callback Domain = ngrok hostname |
| Update .env | `PUBLIC_BASE_URL=https://your-ngrok.ngrok-free.app` |
| Register webhooks | `./ops/scripts/register-webhooks.sh` |
| Connect Strava | Open UI at http://localhost/ → Click “Connect with Strava” |
| Start Telegram chat | Send any message to your bot |
| Dashboard | `http://localhost/` |
| Stop everything | `docker compose down` |

---

## Restart ngrok (URL changed)

When you restart ngrok, the public URL changes. Follow these steps in order:

1. **Stop ngrok** (Ctrl+C if running in a terminal, or `docker compose --profile ngrok down` if using Docker ngrok).

2. **Start ngrok again:**
   - Host: `ngrok http 80`
   - Docker: `docker compose --profile ngrok up ngrok`
   - Copy the new `https://xxxx.ngrok-free.app` URL.

3. **Update `.env`** with the new URL:
   ```env
   PUBLIC_BASE_URL=https://YOUR-NEW-NGROK-URL.ngrok-free.app
   STRAVA_WEBHOOK_CALLBACK_URL=https://YOUR-NEW-NGROK-URL.ngrok-free.app/api/strava/webhook
   TELEGRAM_WEBHOOK_URL=https://YOUR-NEW-NGROK-URL.ngrok-free.app/api/telegram/webhook/YOUR_TELEGRAM_WEBHOOK_SECRET
   ```
   (Replace `YOUR-NEW-NGROK-URL` and `YOUR_TELEGRAM_WEBHOOK_SECRET` with your values.)

4. **Update Strava API settings:**
   - Go to [Strava API Settings](https://www.strava.com/settings/api) → **Edit Application**
   - Set **Authorization Callback Domain** to the ngrok hostname only (e.g. `xxxx.ngrok-free.app`)
   - Save

5. **Register webhooks** (points Strava and Telegram at the new URL):
   ```bash
   ./ops/scripts/register-webhooks.sh
   ```

6. **Restart the API** so it picks up the new env:
   ```bash
   docker compose restart api
   ```

7. **Reconnect Strava** (OAuth redirect URL changed):
   - Open `http://localhost/` or your ngrok URL
   - Click **Connect with Strava** and authorize again

---

## If something breaks

- **No Telegram message after a run**: Check the dashboard at `http://localhost/` for events (run_action, webhook_retry, webhook_failed). Ensure `TELEGRAM_ALLOWED_USER_ID` is set and you've started a chat with your bot.
- **Webhook not reaching app**: Ensure ngrok is running and `PUBLIC_BASE_URL` matches the current ngrok URL
- **Strava OAuth fails**: Ensure Strava Authorization Callback Domain matches your ngrok hostname exactly
