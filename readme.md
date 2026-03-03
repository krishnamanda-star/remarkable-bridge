# Remarkable Bridge

HTTP bridge server that exposes remarkable-mcp tools for the Vercel notes app.

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Create new Railway project → Deploy from GitHub
3. Set environment variables:
   - `REMARKABLE_TOKEN` — your reMarkable token (see below)
   - `BRIDGE_SECRET` — any random secret string (e.g. `openssl rand -hex 32`)
4. Railway auto-deploys and gives you a URL like `https://remarkable-bridge.up.railway.app`

## Getting your REMARKABLE_TOKEN

1. Go to https://my.remarkable.com/device/browser/connect
2. Generate a one-time code (8 letters, e.g. `apwngead`)
3. Run this once on your Mac to convert it to a long-lived token:
   ```
   pip install remarkable-mcp
   python3 -c "
   from remarkable_mcp.cloud import register
   import asyncio
   code = input('Enter one-time code: ')
   token = asyncio.run(register(code))
   print('Your token:', token)
   "
   ```
4. Copy the token — paste it as the `REMARKABLE_TOKEN` env var in Railway

## API

POST /
```json
{
  "tool": "remarkable_search",
  "params": { "query": "meeting notes" }
}
```

Headers: `Authorization: Bearer YOUR_BRIDGE_SECRET`

Tools available:
- `remarkable_browse` — params: `{ "path": "/" }`
- `remarkable_read` — params: `{ "document": "Meeting Notes" }`
- `remarkable_search` — params: `{ "query": "T2 platform" }`
- `remarkable_recent` — params: `{ "limit": 10 }`
- `remarkable_status` — params: `{}`
