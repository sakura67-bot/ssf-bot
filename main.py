
import discord
from discord.ext import commands
from discord import app_commands
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


SERVER_LAYOUT = {
    "╭── INFORMATION DIVISION": [
        "│・welcome",
        "│・announcements",
        "│・rules",
        "│・server-info",
        "╰・roles"
    ],

    "╭── PUBLIC ACCESS": [
        "│・general-chat",
        "╰・suggestions"
    ],

    "╭── REPORT CENTER": [
        "│・submit-a-report",
        "│・submit-evidence",
        "│・scammer-reports",
        "│・known-scammers",
        "╰・scam-server-reports"
    ],

    "╭── INVESTIGATION DIVISION": [
        "│・open-cases",
        "│・under-review",
        "│・resolved-cases",
        "╰・rejected-reports"
    ],

    "╭── INTERNAL AFFAIRS": [
        "│・staff-chat",
        "│・staff-announcements",
        "│・staff-logs",
        "╰・staff-applications"
    ],

    "╭── EXECUTIVE OFFICE": [
        "│・management",
        "│・owner-room",
        "│・security-logs",
        "╰・bot-logs"
    ]
}


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.command(
    name="setupserver",
    description="Create the Sentinal Network server layout"
)
@app_commands.checks.has_permissions(administrator=True)
async def setupserver(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild

    if guild is None:
        await interaction.followup.send(
            "This command must be used inside a server.",
            ephemeral=True
        )
        return

    categories_created = 0
    channels_created = 0
    channels_skipped = 0

    try:
        for category_name, channel_names in SERVER_LAYOUT.items():

            category = discord.utils.get(
                guild.categories,
                name=category_name
            )

            if category is None:
                category = await guild.create_category(
                    name=category_name,
                    reason="Sentinal Network setup"
                )
                categories_created += 1

            for channel_name in channel_names:

                existing = discord.utils.get(
                    category.text_channels,
                    name=channel_name
                )

                if existing:
                    channels_skipped += 1
                    continue

                await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason="Sentinal Network setup"
                )

                channels_created += 1

        embed = discord.Embed(
            title="SENTINAL NETWORK",
            description="Server layout setup completed successfully.",
            color=discord.Color.from_rgb(128, 55, 200)
        )

        embed.add_field(
            name="Categories created",
            value=str(categories_created),
            inline=True
        )

        embed.add_field(
            name="Channels created",
            value=str(channels_created),
            inline=True
        )

        embed.add_field(
            name="Channels skipped",
            value=str(channels_skipped),
            inline=True
        )

        embed.set_footer(
            text="Sentinal Network | Management System"
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "Missing permissions! Give the bot Manage Channels permission.",
            ephemeral=True
        )

    except discord.HTTPException as e:
        await interaction.followup.send(
            f"Discord error: {e}",
            ephemeral=True
        )


@setupserver.error
async def setupserver_error(interaction, error):

    if isinstance(error, app_commands.MissingPermissions):
        message = "You need Administrator permissions to use this command."
    else:
        message = f"Error: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing!")

bot.run(TOKEN)
