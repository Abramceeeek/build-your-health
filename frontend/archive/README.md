# Frontend archive

Reference only. **Not loaded by the live app.**

## Currently archived

- `app-claude.css` — Claude editorial stylesheet (warm off-white, terracotta accent, Source Serif 4, no shadows). Replaced the original dark theme briefly; archived for later iteration.
- `tokens-claude.css` — design tokens consumed by `app-claude.css`.
- `index-claude.html` — sidebar shell + Coach page + redesigned Today/Settings/Nutrition/Progress/Compete/Assistant.
- `app-original.css` — original dark navy/blue stylesheet (currently restored as live `frontend/css/app.css`).
- `index-original.html` — original mark-up (currently restored as live `frontend/index.html`).

## Restoring the Claude theme

```sh
cp frontend/archive/app-claude.css frontend/css/app.css
cp frontend/archive/tokens-claude.css frontend/css/tokens.css
cp frontend/archive/index-claude.html frontend/index.html
```

## Restoring the original (current state)

```sh
cp frontend/archive/app-original.css frontend/css/app.css
cp frontend/archive/index-original.html frontend/index.html
rm -f frontend/css/tokens.css
```

## What stays the same regardless of theme

All backend changes are theme-independent:
- Coach API (`/api/coach/today`, `/api/coach/messages`, `/api/coach/message`)
- Pyramid set ladder + RPE-aware progression
- Settings save → today's tasks regenerate
- Muscle-tier exercise selector
- Admin endpoints for fixing image URLs
- FEEDBACK_BOT_TOKEN routing
- OpenRouter / Gemini fallback chain in coach chat
