Perfect — this is a **clean, automation-focused backend system** and very aligned with your existing FastAPI + async + VPS setup.

Below is a full technical project blueprint.

---

# 🏃‍♂️ Project Overview

## Goal

Build a VPS-hosted automation service that integrates with:

* Strava (activity events + updates)
* Telegram (user interaction)

### The system should:

1. When a **Run** is finished:

   * Send a Telegram message asking which shoes were used.
   * Present available gear options as inline buttons.
   * Update the activity with selected gear.

2. When a **Gym/Strength** workout is finished:

   * Automatically set `hide_from_home = true`
   * So it does not appear in followers’ feeds
   * But remains visible on your profile.

---

# 🏗 System Architecture

```
Strava → Webhook → FastAPI App (VPS)
                             ↓
                        Business Logic
                             ↓
                  ┌───────────────┐
                  │ Telegram Bot  │
                  └───────────────┘
                             ↓
                        Strava API
```

---

# 🧱 Core Components

## 1️⃣ FastAPI Backend

Single service running on your VPS.

Responsibilities:

* Handle Strava webhook
* Handle Telegram webhook
* Store tokens & gear
* Refresh Strava tokens
* Business logic routing

---

## 2️⃣ Strava Integration

### Required Permissions

Scopes:

* `activity:read`
* `activity:write`

### You Must Implement:

* OAuth flow
* Token storage
* Token refresh handling
* Webhook subscription verification
* Activity fetch
* Activity update

---

## 3️⃣ Telegram Bot

Responsibilities:

* Send messages with inline keyboards
* Handle callback queries
* Map selected button → gear_id
* Trigger Strava update

---

## 4️⃣ Database

Use PostgreSQL (fits your ecosystem).

### Tables

#### users

```
id
strava_athlete_id
telegram_user_id
access_token
refresh_token
expires_at
```

#### gear

```
id
strava_gear_id
name
is_default
```

#### pending_activities

```
activity_id
telegram_message_id
created_at
```

---

# 🧠 Event Flow Breakdown

---

# 🔔 Flow 1: Run Finished

### Step 1 — Strava Webhook Fires

Strava sends:

```
aspect_type: create
object_type: activity
object_id: 123
```

---

### Step 2 — Backend Fetches Activity

Call:

```
GET /api/v3/activities/{id}
```

Check:

* type == "Run"
* gear_id == null

---

### Step 3 — Fetch Available Gear

Call:

```
GET /api/v3/athlete
```

Extract:

* shoes list

Store locally for quick access.

---

### Step 4 — Send Telegram Message

Message:

> “Nice run 🔥 Which shoes did you use?”

Inline buttons:

```
[ Vaporfly ]
[ Boston 12 ]
[ Trail ]
```

Store:

* activity_id
* message_id

---

### Step 5 — Telegram Callback

User clicks a button.

Telegram sends callback:

```
callback_data = "activity_123_gear_456"
```

---

### Step 6 — Update Strava Activity

Call:

```
PUT /api/v3/activities/{id}
{
  "gear_id": "g123456"
}
```

Delete pending activity row.

---

# 🏋️ Flow 2: Gym Workout Finished

Webhook fires.

Fetch activity.

If:

```
type in ["WeightTraining", "Workout"]
```

Call:

```
PUT /api/v3/activities/{id}
{
  "hide_from_home": true
}
```

No Telegram interaction needed.

---

# 🧰 Recommended Tech Stack

Given your experience:

### Backend

* FastAPI
* Uvicorn
* httpx (async Strava client)
* Pydantic
* asyncpg
* Redis (optional)

### Infrastructure

* Docker
* Docker Compose
* Nginx
* Let’s Encrypt
* VPS (Ubuntu)

### Dev Tools

* Poetry
* Alembic (migrations)
* Loguru or structlog

---

# 📁 Suggested Project Structure

```
app/
  main.py
  config.py
  db.py
  models.py
  strava/
      client.py
      oauth.py
      webhooks.py
  telegram/
      bot.py
      handlers.py
  services/
      activity_service.py
      gear_service.py
  utils/
      security.py
```

---

# 🔐 Security Considerations

## 1️⃣ Webhook Verification

Strava requires:

* Verification token
* Challenge response on registration

## 2️⃣ Telegram Secret Token

Use secret webhook URL:

```
/telegram/webhook/<random-secret>
```

## 3️⃣ Token Encryption

Store:

* access_token
* refresh_token

Encrypted at rest (optional but good practice).

---

# 🔄 Token Refresh Logic

Before every Strava call:

```
if now > expires_at:
    refresh_token()
```

Strava refresh endpoint:

```
POST /oauth/token
```

Update DB with new:

* access_token
* refresh_token
* expires_at

---

# ⏱ Handling Strava Timing Issue

Strava sometimes fires webhook before activity is fully processed.

Solution:

* Delay 5–10 seconds before fetching
  OR
* Retry if activity returns incomplete data

---

# 🧪 Testing Strategy

## Local Testing

Use:

* ngrok to expose local server
* Register webhook to ngrok URL

## Unit Tests

Mock:

* Strava API
* Telegram API

Test:

* Run logic
* Gym logic
* Token refresh
* Callback mapping

---

# 📦 Deployment Plan

1. VPS setup
2. Dockerize app
3. Nginx reverse proxy
4. HTTPS
5. Register Strava webhook
6. Set Telegram webhook

---

# 🧩 Optional Enhancements

You could expand into:

### 1️⃣ Auto-Shoe Detection

* Based on:

  * Activity title
  * Terrain
  * Elevation

### 2️⃣ Auto Default After Timeout

If no response in 1 hour:

* Assign default shoe

### 3️⃣ Shoe Mileage Tracker

Maintain your own cumulative mileage per shoe.

### 4️⃣ Activity Summary Message

Send:

> 10km · 42:31 · 120m elevation 🔥

### 5️⃣ Admin Dashboard

Minimal React frontend:

* See pending activities
* Change defaults
* View shoe mileage

---

# 🏁 Complexity Assessment

| Component      | Difficulty     |
| -------------- | -------------- |
| Strava OAuth   | Medium         |
| Webhooks       | Medium         |
| Telegram bot   | Easy           |
| Business logic | Easy           |
| Deployment     | Easy (for you) |

Given your background with:

* Async APIs
* Webhooks
* Postgres
* Docker
* VPS hosting

This is very manageable.

---

# 🧠 Estimated Build Time

MVP:

* 4–6 hours

Production-grade:

* 1–2 days

---
