"""
Discord Ticket + Payment Bot

Features:
- Private support tickets
- Ticket questions
- /close-ticket
- /setup-tickets
- /pay amount wallet (administrator only)
- Solana wallet validation
- Payment FAQ embed
"""

import os
import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

def _int_or_none(value):
    value = (value or "").strip()
    return int(value) if value else None


BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = _int_or_none(os.getenv("GUILD_ID"))
SUPPORT_ROLE_ID = _int_or_none(os.getenv("SUPPORT_ROLE_ID"))
TICKET_CATEGORY_ID = _int_or_none(os.getenv("TICKET_CATEGORY_ID"))

BANDITS_ROLE_ID = 1546880925525217300
ADMINS_ROLE_ID = 1546883844219871232


# ============================================================
# TICKET SETTINGS
# ============================================================

TICKET_QUESTIONS = [
    "How long have you been into memecoins?",
    "Do you know about rugging?",
    "What is the capital size you usually go with while trading?",
]

QUESTION_TIMEOUT_SECONDS = 300


# ============================================================
# PAYMENT SETTINGS
# ============================================================

# Basic Solana address check:
# Base58 characters, approximately 32-44 characters.
SOLANA_ADDRESS_REGEX = re.compile(
    r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
)

PAYMENT_FAQS = [
    (
        "🏛️ How It Works:",
        "🚀 Token Is Launched!\n"
        "Your exclusive access to our premium launch",
    ),
    (
        "🔍 Payment Detection",
        "Our advanced system instantly identifies your transaction",
    ),
    (
        "✅ Wallet Registration",
        "Your address is automatically whitelisted for the launch",
    ),
    (
        "📈 Strategic Exit",
        "We execute a perfectly timed market exit strategy.",
    ),
    (
        "💎 Profit Distribution",
        "Your share of profits is immediately sent back to your wallet",
    ),
]


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# TICKET CREATION
# ============================================================

async def create_ticket_channel(
    guild: discord.Guild,
    user: discord.Member
) -> discord.TextChannel:

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),

        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True
        ),
    }

    support_role = (
        guild.get_role(SUPPORT_ROLE_ID)
        if SUPPORT_ROLE_ID
        else None
    )

    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

    category = (
        guild.get_channel(TICKET_CATEGORY_ID)
        if TICKET_CATEGORY_ID
        else None
    )

    safe_name = "".join(
        c for c in user.name.lower()
        if c.isalnum() or c == "-"
    )[:20]

    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name or user.id}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket opened by {user}",
    )

    return channel


# ============================================================
# TICKET QUESTIONS
# ============================================================

async def run_ticket_questions(
    channel: discord.TextChannel,
    user: discord.Member
):

    def check(message: discord.Message) -> bool:
        return (
            message.author.id == user.id
            and message.channel.id == channel.id
        )

    answers = []

    await channel.send(
        f"Hey <@&{BANDITS_ROLE_ID}>, thanks for opening a ticket!\n"
        f"<@&{ADMINS_ROLE_ID}> will soon respond to your ticket.\n"
        f"Till then we suggest that you answer a few questions"
    )

    for i, question in enumerate(
        TICKET_QUESTIONS,
        start=1
    ):

        await channel.send(
            f"**Question {i}/{len(TICKET_QUESTIONS)}:** "
            f"{question}"
        )

        try:
            reply = await bot.wait_for(
                "message",
                check=check,
                timeout=QUESTION_TIMEOUT_SECONDS
            )

        except asyncio.TimeoutError:

            await channel.send(
                f"{user.mention} didn't reply in time, "
                f"so I stopped asking questions. "
                f"A staff member can pick it up from here, "
                f"or you can type your remaining answers below."
            )

            break

        answers.append(
            (question, reply.content)
        )

    guild = channel.guild

    support_role = (
        guild.get_role(SUPPORT_ROLE_ID)
        if SUPPORT_ROLE_ID
        else None
    )

    embed = discord.Embed(
        title="Ticket Summary",
        description=f"Opened by {user.mention}",
        color=discord.Color.blurple(),
    )

    for question, answer in answers:
        embed.add_field(
            name=question,
            value=answer or "—",
            inline=False
        )

    if not answers:
        embed.add_field(
            name="Note",
            value="No questions were answered.",
            inline=False
        )

    await channel.send(
        content=support_role.mention if support_role else None,
        embed=embed,
    )


# ============================================================
# OPEN TICKET BUTTON
# ============================================================

class TicketOpenView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.green,
        emoji="🎫",
        custom_id="ticket:open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        channel = await create_ticket_channel(
            interaction.guild,
            interaction.user
        )

        await interaction.followup.send(
            f"Your ticket has been created: "
            f"{channel.mention}",
            ephemeral=True
        )

        bot.loop.create_task(
            run_ticket_questions(
                channel,
                interaction.user
            )
        )


# ============================================================
# STAFF CHECK
# ============================================================

def _is_staff(member: discord.Member) -> bool:

    support_role = (
        member.guild.get_role(SUPPORT_ROLE_ID)
        if SUPPORT_ROLE_ID
        else None
    )

    is_support_role = (
        support_role and support_role in member.roles
    )

    return bool(
        is_support_role
        or member.guild_permissions.manage_channels
    )


# ============================================================
# /close-ticket
# ============================================================

@bot.tree.command(
    name="close-ticket",
    description="Close this ticket (staff only)"
)
async def close_ticket(
    interaction: discord.Interaction
):

    if not _is_staff(interaction.user):

        await interaction.response.send_message(
            "Only support staff can close this ticket.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        "Closing ticket in 5 seconds..."
    )

    await asyncio.sleep(5)

    await interaction.channel.delete(
        reason=f"Ticket closed by {interaction.user}"
    )


# ============================================================
# /setup-tickets
# ============================================================

@bot.tree.command(
    name="setup-tickets",
    description="Post the ticket-opening button in this channel"
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def setup_tickets(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="Support Tickets",
        description=(
            "Need help? Click the button below to "
            "open a private ticket with our team."
        ),
        color=discord.Color.blurple(),
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketOpenView()
    )

    await interaction.response.send_message(
        "Ticket panel posted.",
        ephemeral=True
    )


# ============================================================
# /pay
# ============================================================

@bot.tree.command(
    name="pay",
    description="Generate a Solana payment request (admin only)"
)
@app_commands.describe(
    amount="Amount of SOL to request",
    wallet="Solana wallet address to receive payment"
)
async def pay(
    interaction: discord.Interaction,
    amount: float,
    wallet: str
):

    # Administrator check
    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(
            "Only administrators can use this command.",
            ephemeral=True
        )

        return

    # Amount check
    if amount <= 0:

        await interaction.response.send_message(
            "The payment amount must be greater than 0.",
            ephemeral=True
        )

        return

    # Wallet check
    wallet = wallet.strip()

    if not SOLANA_ADDRESS_REGEX.fullmatch(wallet):

        await interaction.response.send_message(
            "That doesn't look like a valid Solana wallet "
            "address. Please double-check it and try again.",
            ephemeral=True
        )

        return

    # Build payment embed
    embed = discord.Embed(
        title="Solana Payment Request",
        description=(
            f"Please send **{amount:g} SOL** "
            f"to the wallet address below:"
        ),
        color=0x9945FF
    )

    embed.add_field(
        name="Wallet Address",
        value=f"`{wallet}`",
        inline=False
    )

    embed.add_field(
        name="Amount",
        value=f"{amount:g} SOL",
        inline=True
    )

    embed.add_field(
        name="Network",
        value="Solana",
        inline=True
    )

    # Add FAQ entries
    for question, answer in PAYMENT_FAQS:

        embed.add_field(
            name=question,
            value=answer,
            inline=False
        )

    embed.set_footer(
        text=f"Requested by {interaction.user}"
    )

    embed.timestamp = discord.utils.utcnow()

    # Public response
    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ERROR HANDLER FOR /setup-tickets
# ============================================================

@setup_tickets.error
async def setup_tickets_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if interaction.response.is_done():
            await interaction.followup.send(
                "You need Manage Channels permission to use this command.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You need Manage Channels permission to use this command.",
                ephemeral=True
            )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    # Re-register persistent ticket button
    bot.add_view(
        TicketOpenView()
    )

    if GUILD_ID:

        guild = discord.Object(
            id=GUILD_ID
        )

        bot.tree.copy_global_to(
            guild=guild
        )

        await bot.tree.sync(
            guild=guild
        )

    else:

        await bot.tree.sync()

    print(
        f"Logged in as {bot.user} "
        f"(id: {bot.user.id})"
    )


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    if not BOT_TOKEN:

        raise SystemExit(
            "BOT_TOKEN is not set. "
            "Set it in Railway Variables."
        )

    bot.run(BOT_TOKEN)
