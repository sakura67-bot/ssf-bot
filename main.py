
import os
import discord
from discord.ext import commands

# ==========================================
# SECURE BOT TOKEN
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is missing!")


# ==========================================
# SERVER ROLES
# ==========================================

ROLE_NAMES = [
    "Sentinal Staff",
    "Sentinal Investigator",
    "Sentinal Senior Investigator",
    "Sentinal Management",
]


# ==========================================
# EXACT SERVER LAYOUT
# ==========================================

SERVER_LAYOUT = {
    "╭── INFORMATION DIVISION": [
        "│・welcome",
        "│・announcements",
        "│・rules",
        "│・server-info",
        "╰・roles",
    ],

    "╭── PUBLIC ACCESS": [
        "│・general-chat",
        "╰・suggestions",
    ],

    "╭── REPORT CENTER": [
        "│・submit-a-report",
        "│・submit-evidence",
        "│・scammer-reports",
        "│・known-scammers",
        "╰・scam-server-reports",
    ],

    "╭── INVESTIGATION DIVISION": [
        "│・open-cases",
        "│・under-review",
        "│・resolved-cases",
        "╰・rejected-reports",
    ],

    "╭── INTERNAL AFFAIRS": [
        "│・staff-chat",
        "│・staff-announcements",
        "│・staff-logs",
        "╰・staff-applications",
    ],

    "╭── EXECUTIVE OFFICE": [
        "│・management",
        "│・owner-room",
        "│・security-logs",
        "╰・bot-logs",
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
# PERMISSION HELPER
# ==========================================

def make_permissions(
    view=True,
    send=False,
    attach=False
):
    return discord.PermissionOverwrite(
        view_channel=view,
        send_messages=send,
        read_message_history=True,
        attach_files=attach,
        embed_links=send,
        add_reactions=send
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
# DELETE OLD CHANNELS AND CATEGORIES
# ==========================================

async def reset_channels(guild):

    print("Deleting old channels...")

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

    print("Deleting old categories...")

    # Delete categories
    for category in list(guild.categories):

        try:

            await category.delete(
                reason="SENTINAL NETWORK server reset"
            )

        except discord.NotFound:
            pass

    print("Old server structure deleted.")


# ==========================================
# CREATE PERMISSIONS FOR CATEGORIES
# ==========================================

def get_category_permissions(guild, roles, category_name):

    everyone = guild.default_role

    staff = roles["Sentinal Staff"]
    investigator = roles["Sentinal Investigator"]
    senior = roles["Sentinal Senior Investigator"]
    management = roles["Sentinal Management"]

    # INFORMATION DIVISION
    if category_name == "╭── INFORMATION DIVISION":

        return {
            everyone: make_permissions(
                view=True,
                send=False
            )
        }

    # PUBLIC ACCESS
    if category_name == "╭── PUBLIC ACCESS":

        return {
            everyone: make_permissions(
                view=True,
                send=True,
                attach=True
            )
        }

    # REPORT CENTER
    if category_name == "╭── REPORT CENTER":

        return {
            everyone: make_permissions(
                view=True,
                send=False
            ),

            staff: make_permissions(
                view=True,
                send=True,
                attach=True
            ),

            investigator: make_permissions(
                view=True,
                send=True,
                attach=True
            ),

            senior: make_permissions(
                view=True,
                send=True,
                attach=True
            ),

            management: make_permissions(
                view=True,
                send=True,
                attach=True
            )
        }

    # INVESTIGATION DIVISION
    if category_name == "╭── INVESTIGATION DIVISION":

        return {
            everyone: make_permissions(view=False),

            investigator: make_permissions(
                view=True,
                send=True
            ),

            senior: make_permissions(
                view=True,
                send=True
            ),

            management: make_permissions(
                view=True,
                send=True
            )
        }

    # INTERNAL AFFAIRS
    if category_name == "╭── INTERNAL AFFAIRS":

        return {
            everyone: make_permissions(view=False),

            staff: make_permissions(
                view=True,
                send=True
            ),

            management: make_permissions(
                view=True,
                send=True
            )
        }

    # EXECUTIVE OFFICE
    if category_name == "╭── EXECUTIVE OFFICE":

        return {
            everyone: make_permissions(view=False),

            management: make_permissions(
                view=True,
                send=True
            )
        }

    return {}


# ==========================================
# CREATE SERVER STRUCTURE
# ==========================================

async def create_server(guild, roles):

    everyone = guild.default_role

    staff = roles["Sentinal Staff"]
    investigator = roles["Sentinal Investigator"]
    senior = roles["Sentinal Senior Investigator"]
    management = roles["Sentinal Management"]

    print("Creating categories and channels...")

    for category_name, channel_names in SERVER_LAYOUT.items():

        print(f"Creating category: {category_name}")

        category_overwrites = get_category_permissions(
            guild,
            roles,
            category_name
        )

        # Create category
        category = await guild.create_category(
            name=category_name,
            overwrites=category_overwrites,
            reason="SENTINAL NETWORK server setup"
        )

        for channel_name in channel_names:

            # IMPORTANT:
            # Always pass a dictionary to overwrites.
            # Copy category permissions for the channel.
            channel_overwrites = dict(category_overwrites)

            # PUBLIC REPORT SUBMISSION CHANNELS
            if (
                category_name == "╭── REPORT CENTER"
                and channel_name in [
                    "│・submit-a-report",
                    "│・submit-evidence"
                ]
            ):

                channel_overwrites = {
                    everyone: make_permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    staff: make_permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    investigator: make_permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    senior: make_permissions(
                        view=True,
                        send=True,
                        attach=True
                    ),

                    management: make_permissions(
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

            print(f"Created channel: {channel_name}")

    print("All categories and channels created!")


# ==========================================
# NOTIFY OWNER
# ==========================================

async def notify_owner(user, message):

    try:

        await user.send(message)

    except discord.Forbidden:

        print("Could not DM owner. DMs may be disabled.")

    except discord.HTTPException as error:

        print("Owner notification error:", repr(error))


# ==========================================
# CONFIRMATION BUTTONS
# ==========================================

class SetupConfirmation(discord.ui.View):

    def __init__(self, guild):

        super().__init__(timeout=60)

        self.guild = guild
        self.processing = False

    # CONFIRM RESET
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

        # Acknowledge interaction before deleting channels
        await interaction.response.defer(
            ephemeral=True,
            thinking=True
        )

        owner = interaction.user

        try:

            print("Starting SENTINAL NETWORK setup...")

            # Create or find roles
            roles = await create_roles(self.guild)

            print("Roles ready.")

            # Delete old channels and categories
            await reset_channels(self.guild)

            # Create the new server structure
            await create_server(self.guild, roles)

            success_message = (
                "✅ **SENTINAL NETWORK SETUP COMPLETED!**\n\n"
                "Your server now has:\n"
                "• 6 categories\n"
                "• 24 text channels\n"
                "• 4 Sentinal roles\n\n"
                "Your existing members and roles were kept."
            )

            print("SETUP COMPLETED SUCCESSFULLY.")

            await notify_owner(
                owner,
                success_message
            )

            try:

                await interaction.followup.send(
                    success_message,
                    ephemeral=True
                )

            except discord.HTTPException:

                print("Could not send interaction followup.")

        except Exception as error:

            print("SETUP ERROR:", repr(error))

            error_message = (
                "❌ **SETUP FAILED**\n\n"
                "An error occurred while creating the server.\n"
                "Check the Bot-Hosting console for details.\n"
                "Some channels may already have been deleted."
            )

            await notify_owner(
                owner,
                error_message
            )

            try:

                await interaction.followup.send(
                    error_message,
                    ephemeral=True
                )

            except discord.HTTPException:

                print("Could not send error notification.")

        finally:

            self.stop()

    # CANCEL RESET
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
    description="Create the SENTINAL NETWORK server layout."
)
async def setupserver(interaction: discord.Interaction):

    if interaction.guild is None:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return

    # Only actual server owner
    if interaction.user.id != interaction.guild.owner_id:

        await interaction.response.send_message(
            "❌ Only the server owner can use this command.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.me

    if bot_member is None:

        await interaction.response.send_message(
            "Could not find the bot in this server.",
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

    # Confirmation embed
    embed = discord.Embed(
        title="SENTINAL NETWORK | SERVER RESET",

        description=(
            "You are about to rebuild the server layout.\n\n"

            "**THIS WILL DELETE:**\n"
            "• All existing channels\n"
            "• All existing categories\n"
            "• Messages inside those channels\n\n"

            "**THIS WILL KEEP:**\n"
            "• Existing members\n"
            "• Existing roles\n"
            "• Server ownership\n\n"

            "**NEW ROLES IF MISSING:**\n"
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

            print("COMMAND SYNC ERROR:", repr(error))


# ==========================================
# START BOT
# ==========================================

bot.run(TOKEN)


