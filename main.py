
import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# SENTINAL NETWORK SERVER STRUCTURE
# ==========================================

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

# ==========================================
# ROLE CONFIGURATION
# ==========================================

ROLE_NAMES = [
    "Sentinal Staff",
    "Sentinal Investigator",
    "Sentinal Senior Investigator",
    "Sentinal Management"
]

# ==========================================
# HELPERS
# ==========================================

async def create_roles(guild):

    roles = {}

    for name in ROLE_NAMES:
        role = discord.utils.get(guild.roles, name=name)

        if role is None:
            role = await guild.create_role(
                name=name,
                permissions=discord.Permissions.none(),
                colour=discord.Colour.from_rgb(145, 75, 220),
                hoist=True,
                mentionable=False,
                reason="Sentinal Network setup"
            )

        roles[name] = role

    return roles


async def reset_channels(guild):

    # Delete normal channels first
    normal_channels = [
        channel for channel in guild.channels
        if not isinstance(channel, discord.CategoryChannel)
    ]

    for channel in normal_channels:
        await channel.delete(
            reason="Sentinal Network complete server reset"
        )
        await asyncio.sleep(0.3)

    # Delete old categories
    for category in list(guild.categories):
        await category.delete(
            reason="Sentinal Network complete server reset"
        )
        await asyncio.sleep(0.3)


async def create_server(guild):

    roles = await create_roles(guild)

    everyone = guild.default_role

    staff = roles["Sentinal Staff"]
    investigator = roles["Sentinal Investigator"]
    senior = roles["Sentinal Senior Investigator"]
    management = roles["Sentinal Management"]

    # Permissions
    public_view = {
        everyone: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True
        )
    }

    public_read_only = {
        everyone: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True
        )
    }

    staff_access = {
        everyone: discord.PermissionOverwrite(
            view_channel=False
        ),
        staff: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        management: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )
    }

    investigator_access = {
        everyone: discord.PermissionOverwrite(
            view_channel=False
        ),
        investigator: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        senior: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        management: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )
    }

    executive_access = {
        everyone: discord.PermissionOverwrite(
            view_channel=False
        ),
        management: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )
    }

    created_categories = 0
    created_channels = 0

    for category_name, channel_names in SERVER_LAYOUT.items():

        # Choose category permissions
        if category_name == "╭── INVESTIGATION DIVISION":
            overwrites = investigator_access

        elif category_name == "╭── INTERNAL AFFAIRS":
            overwrites = staff_access

        elif category_name == "╭── EXECUTIVE OFFICE":
            overwrites = executive_access

        else:
            overwrites = public_view

        category = await guild.create_category(
            name=category_name,
            overwrites=overwrites,
            reason="Sentinal Network setup"
        )

        created_categories += 1

        for channel_name in channel_names:

            channel_overwrites = None

            # Information channels are read-only
            if category_name == "╭── INFORMATION DIVISION":
                channel_overwrites = public_read_only

            # Public access
            elif category_name == "╭── PUBLIC ACCESS":
                channel_overwrites = public_view

            # Report center
            elif category_name == "╭── REPORT CENTER":

                if channel_name in [
                    "│・submit-a-report",
                    "│・submit-evidence"
                ]:
                    channel_overwrites = {
                        everyone: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            attach_files=True,
                            embed_links=True,
                            read_message_history=True
                        ),
                        staff: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True
                        ),
                        management: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True
                        )
                    }

                else:
                    channel_overwrites = {
                        everyone: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=False,
                            read_message_history=True
                        ),
                        staff: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True
                        ),
                        management: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True
                        )
                    }

            await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=channel_overwrites,
                reason="Sentinal Network setup"
            )

            created_channels += 1
            await asyncio.sleep(0.3)

    return created_categories, created_channels, roles


# ==========================================
# CONFIRMATION BUTTON
# ==========================================

class SetupConfirmation(discord.ui.View):

    def __init__(self, guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(
        label="CONFIRM SERVER RESET",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.guild.owner_id:
            await interaction.response.send_message(
                "Only the actual server owner can confirm this.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        self.stop()

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

        try:
            await interaction.followup.send(
                "Sentinal Network reset started. Please wait...",
                ephemeral=True
            )

            await reset_channels(self.guild)

            categories, channels, roles = await create_server(
                self.guild
            )

            embed = discord.Embed(
                title="SENTINAL NETWORK",
                description="Your server has been rebuilt successfully.",
                color=discord.Colour.from_rgb(145, 75, 220)
            )

            embed.add_field(
                name="Categories created",
                value=str(categories),
                inline=True
            )

            embed.add_field(
                name="Channels created",
                value=str(channels),
                inline=True
            )

            embed.add_field(
                name="Roles created / found",
                value=str(len(roles)),
                inline=True
            )

            embed.add_field(
                name="Status",
                value="Server setup completed.",
                inline=False
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
                "Permission error. Check Manage Channels and "
                "Manage Roles permissions and role hierarchy. "
                "The reset may be incomplete.",
                ephemeral=True
            )

        except discord.HTTPException as error:
            await interaction.followup.send(
                f"Discord API error. Setup may be incomplete: {error}",
                ephemeral=True
            )

    @discord.ui.button(
        label="CANCEL",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can cancel this setup.",
                ephemeral=True
            )
            return

        self.stop()

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Server reset cancelled.",
            view=self
        )


# ==========================================
# BOT EVENTS
# ==========================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as error:
        print(f"Sync error: {error}")


# ==========================================
# SETUP COMMAND
# ==========================================

@bot.tree.command(
    name="setupserver",
    description="Rebuild the complete Sentinal Network server"
)
@app_commands.guild_only()
async def setupserver(interaction: discord.Interaction):

    guild = interaction.guild

    if interaction.user.id != guild.owner_id:
        await interaction.response.send_message(
            "Only the actual server owner can use this command.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="SENTINAL NETWORK RESET",
        description=(
            "You are about to completely rebuild this server.\n\n"
            "**The following actions will happen:**\n"
            "• Delete all existing channels.\n"
            "• Delete all existing categories.\n"
            "• Create 6 new categories.\n"
            "• Create 24 new channels.\n"
            "• Create 4 staff roles if missing.\n"
            "• Configure channel permissions.\n\n"
            "**Existing roles and members will remain.**\n\n"
            "This action cannot be undone. Deleted messages "
            "and channel settings cannot be recovered."
        ),
        color=discord.Colour.from_rgb(145, 75, 220)
    )

    embed.set_footer(
        text="Sentinal Network | Confirmation required"
    )

    await interaction.response.send_message(
        embed=embed,
        view=SetupConfirmation(guild),
        ephemeral=True
    )


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing!")

bot.run(TOKEN)

