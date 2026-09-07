# Discord Ticket Bot

A bot where users click **Open Ticket**, answer a few questions in a popup form,
and the bot creates a private channel for them with their answers posted for staff.

## 1. Create the bot

1. Go to https://discord.com/developers/applications → **New Application**.
2. Go to the **Bot** tab → **Reset Token** → copy it (this is your `BOT_TOKEN`).
3. On the same page, turn ON the **Server Members Intent**.
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Manage Channels`, `Send Messages`, `Read Message History`,
     `Embed Links`, `Manage Roles`
5. Open the generated URL and invite the bot to your server.

## 2. Get your IDs (optional but recommended)

Turn on Developer Mode in Discord (Settings → Advanced), then right-click to copy IDs:
- **Server ID** → `GUILD_ID`
- **Support role** → `SUPPORT_ROLE_ID`
- **Ticket category** (create one called "Tickets" first) → `TICKET_CATEGORY_ID`

## 3. Install & run

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and fill in BOT_TOKEN (and the optional IDs)
python bot.py
```

## 4. Post the ticket button

In any channel in your server, run:

```
/setup-tickets
```

This posts an embed with an **Open Ticket** button. Anyone who clicks it gets
asked the questions defined in `TICKET_QUESTIONS` at the top of `bot.py`, then
gets their own private channel with the support role pinged.

## Customizing the questions

Edit the `TICKET_QUESTIONS` list near the top of `bot.py`. You can have up to
5 questions per ticket (a Discord limit on modals), each either a short
one-line answer or a longer paragraph field.

## How closing works

Inside each ticket channel there's a **Close Ticket** button. Only members
with the support role (or `Manage Channels` permission) can use it — it
deletes the channel after a short delay.

## Notes

- The bot uses **persistent views**, so the buttons keep working even after
  you restart the bot.
- If `GUILD_ID` isn't set, slash commands still work but can take up to an
  hour to show up everywhere; setting it makes them sync instantly.
