
import os
import discord
from discord import app_commands
from discord.ext import commands

# ==========================================
# SECURE TOKEN CONFIGURATION
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "DISCORD_TOKEN environment variable is missing!"
    )


# ==========================================
# SERVER CONFIGURATION
# ==========================================

ROLE_NAMES = [
    "Sentinal Staff",
    "Sentinal Investigator",
    "Sentinal Senior Investigator",
    "Sentinal Management",
]

SERVER_LAYOUT = {
    "INFORMATION DIVISION": [
        "welcome",
        "announcements",
        "rules",
        "server-info",
        "roles",
    ],

    "PUBLIC ACCESS": [
        "general-chat",
        "suggestions",
    ],

    "REPORT CENTER": [
        "submit-a-report",
        "submit-evidence",
        "scammer-reports",
        "known-scammers",
        "scam-server-reports",
    ],

    "INVESTIGATION DIVISION": [
        "open-cases",
        "under-review",
        "resolved-cases",
        "rejected-reports",
    ],

    "INTERNAL AFFAIRS": [
        "staff-chat",
        "staff-announcements",
        "staff-logs",
        "staff-applications",
    ],

    "EXECUTIVE OFFICE": [
        "management",
        "owner-room",
        "security-logs",
        "bot-logs",
    ],
}


# ==========================================
# BOT SETUP
# ==========================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================================
# CREATE ROLES
# ==========================================

async def create_roles(guild):

    roles = {}

    for role_name in ROLE_NAMES:

        role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        if role is None:

            role = await guild.create_role(
                name=role_name,
                colour=discord.Colour.from_rgb(112, 65, 190),
                hoist=True,
                permissions=discord.Permissions.none(),
                reason="SENTINAL NETWORK setup"
            )

        roles[role_name] = role

    return roles


# ==========================================
# PERMISSION HELPER
# ==========================================

def permissions(
    view=True,
    send=False,
    history=True,
    attach=False
):

    return discord.PermissionOverwrite(
        view_channel=view,
        send_messages=send,
        read_message_history=history,
        attach_files=attach,
        embed_links=send,
        add_reactions=send
    )


# ==========================================
# DELETE OLD CHANNELS
# ==========================================

async def reset_channels(guild):

    # Delete text, voice and other channels first
    for channel in list(guild.channels):

        if isinstance(channel, discord.CategoryChannel):
            continue

        try:
            await channel.delete(
                reason="SENTINAL NETWORK server reset"
            )

        except discord.NotFound:
            pass

    # Delete old categories
    for category in list(guild.categories):

        try:
            await category.delete(
                reason="SENTINAL NETWORK server reset"
            )

        except discord.NotFound:
            pass


# ==========================================
# CREATE SERVER STRUCTURE
# ==========================================

async def create_server(guild, roles):

    everyone = guild.default_role

    staff = roles["Sentinal Staff"]
    investigator = roles["Sentinal Investigator"]
    senior = roles["Sentinal Senior Investigator"]
    management = roles["Sentinal Management"]

    # INFORMATION DIVISION
    info_overwrites = {
        everyone: permissions(
            view=True,
            send=False
        )
    }

    # PUBLIC ACCESS
    public_overwrites = {
        everyone: permissions(
            view=True,
            send=True,
            attach=True
        )
    }

    # REPORT CENTER
    report_overwrites = {
        everyone: permissions(
            view=True,
            send=False
        ),

        staff: permissions(
            view=True,
            send=True,
            attach=True
        ),

        investigator: permissions(
            view=True,
            send=True,
            attach=True
        ),

        senior: permissions(
            view=True,
            send=True,
            attach=True
        ),

        management: permissions(
            view=True,
            send=True,
            attach=True
        )
    }

    # INVESTIGATION DIVISION
    investigation_overwrites = {
        everyone: permissions(view=False),

        investigator: permissions(
            view=True,
            send=True
        ),

        senior: permissions(
            view=True,
            send=True
        ),

        management: permissions(
            view=True,
            send=True
        )
    }

    # INTERNAL AFFAIRS
    internal_overwrites = {
        everyone: permissions(view=False),

        staff: permissions(
            view=True,
            send=True
        ),

        management: permissions(
            view=True,
            send=True
        )
    }

    # EXECUTIVE OFFICE
    executive_overwrites = {
        everyone: permissions(view=False),

        management: permissions(
            view=True,
            send=True
        )
    }

    category_permissions = {
        "INFORMATION DIVISION": info_overwrites,
        "PUBLIC ACCESS": public_overwrites,
        "REPORT CENTER": report_overwrites,
        "INVESTIGATION DIVISION": investigation_overwrites,
        "INTERNAL AFFAIRS": internal_overwrites,
        "EXECUTIVE OFFICE": executive_overwrites
    }

    # CREATE CATEGORIES
    for category_name, channel_names in SERVER_LAYOUT.items():

        category = await guild.create_category(
            name=category_name,
            overwrites=category_permissions[category_name],
            reason="SENTINAL NETWORK server setup"
        )

        # CREATE CHANNELS
        for channel_name in channel_names:

            channel_overwrites = None

            # Submission channels allow public reports
            if (
                category_name == "REPORT CENTER"
                and channel_name in [
                    "submit-a-report",
                    "submit-evidence"
                ]
            ):

                channel_overwrites = {
                    everyone: permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    staff: permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    investigator: permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    senior: permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    management: permissions(
                        view=True,
                        send=True,
                        attach=True
                    )
                }

            await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=channel_overwrites,
                reason="SENTINAL NETWORK server setup"
            )


# ==========================================
# CONFIRMATION VIEW
# ==========================================

class SetupConfirmation(discord.ui.View):

    def __init__(self, guild):

        super().__init__(timeout=60)

        self.guild = guild
        self.processing = False

    # CONFIRM BUTTON
    @discord.ui.button(
        label="CONFIRM SERVER RESET",
        style=discord.ButtonStyle.danger,
        emoji="⚠️"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.guild.owner_id:

            await interaction.response.send_message(
                "Only the server owner can confirm this reset.",
                ephemeral=True
            )

            return

        if self.processing:

            await interaction.response.send_message(
                "Setup is already running.",
                ephemeral=True
            )

            return

        self.processing = True

        # Defer before deleting the channel containing
        # the original confirmation message.
        await interaction.response.defer(
            ephemeral=True,
            thinking=True
        )

        try:

            # Create or find roles
            roles = await create_roles(self.guild)

            # Delete existing channels and categories
            await reset_channels(self.guild)

            # Recreate server layout
            await create_server(self.guild, roles)

            await interaction.followup.send(
                "✅ **SENTINAL NETWORK SETUP COMPLETED!**\n\n"
                "All 6 categories and 24 channels have been created.\n\n"
                "Your existing members and roles were kept.",
                ephemeral=True
            )

        except Exception as error:

            print(
                "SETUP ERROR:",
                repr(error)
            )

            try:
                await interaction.followup.send(
                    "❌ **SETUP FAILED**\n\n"
                    "An error occurred during setup. "
                    "Check the console for details.\n"
                    "Some channels may already have been deleted.",
                    ephemeral=True
                )

            except discord.HTTPException:
                print("Could not send setup error notification.")

        finally:

            self.stop()

    # CANCEL BUTTON
    @discord.ui.button(
        label="CANCEL",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.guild.owner_id:

            await interaction.response.send_message(
                "Only the server owner can cancel setup.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "Setup cancelled. Nothing was changed.",
            ephemeral=True
        )

        self.stop()


# ==========================================
# SETUP SERVER COMMAND
# ==========================================

@bot.tree.command(
    name="setupserver",
    description="Reset and create the SENTINAL NETWORK server."
)
async def setupserver(interaction: discord.Interaction):

    if interaction.guild is None:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )

        return

    # OWNER CHECK
    if interaction.user.id != interaction.guild.owner_id:

        await interaction.response.send_message(
            "❌ Only the server owner can use this command.",
            ephemeral=True
        )

        return

    # BOT PERMISSION CHECK
    bot_member = interaction.guild.me

    if bot_member is None:

        await interaction.response.send_message(
            "Could not find the bot's server member.",
            ephemeral=True
        )

        return

    if not bot_member.guild_permissions.manage_channels:

        await interaction.response.send_message(
            "❌ I need the Manage Channels permission.",
            ephemeral=True
        )

        return

    if not bot_member.guild_permissions.manage_roles:

        await interaction.response.send_message(
            "❌ I need the Manage Roles permission.",
            ephemeral=True
        )

        return

    # CONFIRMATION EMBED
    embed = discord.Embed(
        title="SENTINAL NETWORK | SERVER RESET",

        description=(
            "You are about to reset the server structure.\n\n"

            "**THIS WILL DELETE:**\n"
            "• All existing channels\n"
            "• All existing categories\n"
            "• Messages inside those channels\n\n"

            "**THIS WILL KEEP:**\n"
            "• Existing members\n"
            "• Existing roles\n"
            "• Server ownership\n\n"

            "**NEW ROLES:**\n"
            "• Sentinal Staff\n"
            "• Sentinal Investigator\n"
            "• Sentinal Senior Investigator\n"
            "• Sentinal Management\n\n"

            "Press **CONFIRM SERVER RESET** to continue."
        ),

        colour=discord.Colour.from_rgb(112, 65, 190)
    )

    embed.set_footer(
        text="SENTINAL NETWORK • Administration"
    )

    await interaction.response.send_message(
        embed=embed,
        view=SetupConfirmation(interaction.guild),
        ephemeral=True
    )


# ==========================================
# BOT STARTUP
# ==========================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("SENTINAL NETWORK is online.")

    if not getattr(bot, "commands_synced", False):

        try:

            synced = await bot.tree.sync()

            bot.commands_synced = True

            print(
                f"Synced {len(synced)} slash commands."
            )

        except Exception as error:

            print(
                "COMMAND SYNC ERROR:",
                repr(error)
            )


# ==========================================
# RUN BOT
# ==========================================

bot.run(TOKEN)
