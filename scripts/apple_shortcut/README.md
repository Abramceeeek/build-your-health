# Apple Watch Auto-Sync Setup

Automatically syncs your Apple Watch health data to Build Your Health every morning.

## How It Works

An iOS Shortcut reads HealthKit data (HRV, resting HR, sleep, steps, VO2max)
and POSTs it to the app backend. Runs silently each morning at 8 AM.

## Setup (one-time, ~2 minutes)

### Step 1 — Get your sync token

1. Open the app → **You** tab → **Connect Apple Watch**
2. Tap **Show sync token** — copy the long code

### Step 2 — Install the Shortcut

1. On your iPhone, open the Shortcuts app
2. Tap **+** → **Add Action**
3. Add these actions in order:

```
Action 1: Get Health Quantity Samples
  Type: Heart Rate
  Include: Average
  In the last: 1 Day
  → Save as "RestingHR"

Action 2: Get Health Quantity Samples
  Type: Heart Rate Variability (HRV)
  Include: Average
  In the last: 1 Day
  → Save as "HRV"

Action 3: Get Health Quantity Samples
  Type: Step Count
  Include: Sum
  In the last: 1 Day
  → Save as "Steps"

Action 4: Get Health Quantity Samples
  Type: Active Energy Burned
  Include: Sum
  In the last: 1 Day
  → Save as "ActiveCal"

Action 5: Get Health Quantity Samples
  Type: VO2 Max
  Include: Latest
  → Save as "VO2max"

Action 6: Get Health Quantity Samples
  Type: Sleep Analysis (Asleep)
  Include: Sum (hours)
  In the last: 1 Day
  → Save as "SleepHours"

Action 7: Dictionary
  Keys:
    resting_hr    → RestingHR (Number)
    hrv_rmssd     → HRV (Number)
    steps         → Steps (Number)
    active_calories → ActiveCal (Number)
    vo2max        → VO2max (Number)
    sleep_hours   → SleepHours (Number)
    wearable_source → "apple_watch" (Text)
  → Save as "Payload"

Action 8: Get Contents of URL
  URL: https://YOUR_DOMAIN/api/health/wearable-sync
  Method: POST
  Request Body: JSON
    Body: Payload
  Headers:
    Authorization: sync YOUR_SYNC_TOKEN_HERE
  → Save as "Response"

Action 9: Show Notification
  Title: "✅ Health Synced"
  Body: "Readiness: " + Response["readiness_score"]
```

### Step 3 — Automate it

1. In Shortcuts app → **Automation** tab → **+**
2. Choose **Time of Day** → set to 8:00 AM
3. Select the shortcut you just created
4. Turn off "Ask Before Running"

That's it — health data syncs automatically every morning.

## Troubleshooting

**"Invalid sync token"** — regenerate in app Settings → Connect Apple Watch → Reset token

**HRV shows 0** — Apple Watch needs to have recorded HRV during sleep. Takes a few nights.

**VO2max not syncing** — requires Apple Watch Series 3+ with at least one outdoor run.
