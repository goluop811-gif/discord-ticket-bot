"""
Discord Ticket Bot
-------------------
When someone clicks "Open Ticket", the bot creates a private channel for them
and asks the questions ONE AT A TIME as normal chat messages, waiting for
their reply before asking the next. Once all questions are answered, it
posts a summary embed and pings your support team. Staff can close a ticket
by running /close-ticket inside that channel.

SETUP:
1. pip install -r requirements.txt
2. Copy .env.example to .env and fill in your bot token + IDs
3. Run: python bot.py
4. In your server, run /setup-tickets in the channel where you want the
   "Open Ticket" button to appear (do this once per channel).

See README.md for full setup instructions (creating the bot, getting IDs, etc).
"""

import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

def _int_or_none(value):
    value = (value or "").strip()
    return int(value) if value else None

BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = _int_or_none(os.getenv("GUILD_ID"))
SUPPORT_ROLE_ID = _int_or_none(os.getenv("SUPPORT_ROLE_ID"))
TICKET_CATEGORY_ID = _int_or_none(os.getenv("TICKET_CATEGORY_ID"))
BANDITS_ROLE_ID = 1546880925525217300
ADMINS_ROLE_ID = 1546883844219871232

# ---------------------------------------------------------------------------
# EDIT THIS to change the questions asked when someone opens a ticket.
# The bot asks these one at a time as chat messages (no length limit like
# the old popup form had). Add or remove as many as you want.
# ---------------------------------------------------------------------------
TICKET_QUESTIONS = [
    "What do you need help with?",
    "Describe your issue in detail.",
    "Have you tried anything already? (say 'no' if not)",
]

# How long (in seconds) the bot waits for a reply before giving up on a ticket.
QUESTION_TIMEOUT_SECONDS = 300  # 5 minutes

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # needed to set channel permissions per-user
intents.message_content = True  # needed to read the user's answers in the ticket channel

bot = commands.Bot(command_prefix="!", intents=intents)


async def create_ticket_channel(guild: discord.Guild, user: discord.Member) -> discord.TextChannel:
    """Creates the private channel for a new ticket and returns it."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }

    support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None

    safe_name = "".join(c for c in user.name.lower() if c.isalnum() or c == "-")[:20]
    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name or user.id}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket opened by {user}",
    )
    return channel


async def run_ticket_questions(channel: discord.TextChannel, user: discord.Member):
    """Asks TICKET_QUESTIONS one at a time in `channel`, waiting for `user` to
    reply to each before asking the next. Posts a summary embed at the end."""

    def check(message: discord.Message) -> bool:
        return message.author.id == user.id and message.channel.id == channel.id

       answers = []
    await channel.send(
        f"Hey <@&{BANDITS_ROLE_ID}>, thanks for opening a ticket!\n"
        f"<@&{ADMINS_ROLE_ID}> will soon respond to your ticket.\n"
        f"Till then we suggest that you answer a few questions"
    )

    for i, question in enumerate(TICKET_QUESTIONS, start=1):
        await channel.send(f"**Question {i}/{len(TICKET_QUESTIONS)}:** {question}")
        try:
            reply = await bot.wait_for(
                "message", check=check, timeout=QUESTION_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            await channel.send(
                f"{user.mention} didn't reply in time, so I stopped asking questions. "
                f"A staff member can pick it up from here, or you can type your remaining "
                f"answers below."
            )
            break
        answers.append((question, reply.content))

    guild = channel.guild
    support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None

    embed = discord.Embed(
        title="Ticket Summary",
        description=f"Opened by {user.mention}",
        color=discord.Color.blurple(),
    )
    for question, answer in answers:
        embed.add_field(name=question, value=answer or "—", inline=False)
    if not answers:
        embed.add_field(name="Note", value="No questions were answered.", inline=False)

    await channel.send(
        content=support_role.mention if support_role else None,
        embed=embed,
    )


# ---------------------------------------------------------------------------
# The persistent "Open Ticket" button, posted via /setup-tickets
# ---------------------------------------------------------------------------
class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent, survives bot restarts

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.green,
        emoji="🎫",
        custom_id="ticket:open",  # fixed custom_id required for persistence
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel = await create_ticket_channel(interaction.guild, interaction.user)
        await interaction.followup.send(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
        )
        # Fire off the Q&A in the background so this button handler returns quickly
        bot.loop.create_task(run_ticket_questions(channel, interaction.user))


def _is_staff(member: discord.Member) -> bool:
    support_role = member.guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
    is_support_role = support_role and support_role in member.roles
    return bool(is_support_role or member.guild_permissions.manage_channels)


# ---------------------------------------------------------------------------
# Slash command staff use to close a ticket (run inside the ticket channel)
# ---------------------------------------------------------------------------
@bot.tree.command(name="close-ticket", description="Close this ticket (staff only)")
async def close_ticket(interaction: discord.Interaction):
    if not _is_staff(interaction.user):
        await interaction.response.send_message(
            "Only support staff can close this ticket.", ephemeral=True
        )
        return

    await interaction.response.send_message("Closing ticket in 5 seconds...")
    await asyncio.sleep(5)
    await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


# ---------------------------------------------------------------------------
# Slash command to post the ticket-opening embed + button in a channel
# ---------------------------------------------------------------------------
@bot.tree.command(name="setup-tickets", description="Post the ticket-opening button in this channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Support Tickets",
        description="Need help? Click the button below to open a private ticket with our team.",
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=TicketOpenView())
    await interaction.response.send_message("Ticket panel posted.", ephemeral=True)


@bot.event
async def on_ready():
    # Re-register persistent views so buttons keep working after a restart
    bot.add_view(TicketOpenView())

    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

    print(f"Logged in as {bot.user} (id: {bot.user.id})")


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
    bot.run(BOT_TOKEN)
