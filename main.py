
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
# ROLE CONFIGURATION
# Permissions are server-level permissions.
# ==========================================

ROLE_CONFIG = {
    # Leadership
    "Founder": {
        "color": "E5C76B",
        "permissions": discord.Permissions(administrator=True),
    },

    "Sentinel Leadership": {
        "color": "D4AF37",
        "permissions": discord.Permissions(
            manage_guild=True,
            manage_channels=True,
            manage_roles=True,
            manage_messages=True,
            moderate_members=True,
            kick_members=True,
            ban_members=True,
            view_audit_log=True,
            manage_nicknames=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    "Director": {
        "color": "B58BFF",
        "permissions": discord.Permissions(
            manage_channels=True,
            manage_messages=True,
            moderate_members=True,
            kick_members=True,
            view_audit_log=True,
            manage_nicknames=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    # Investigators
    "Head Scam Investigator": {
        "color": "9370DB",
        "permissions": discord.Permissions(
            manage_messages=True,
            moderate_members=True,
            view_audit_log=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    "Senior Scam Investigator": {
        "color": "8064C8",
        "permissions": discord.Permissions(
            manage_messages=True,
            moderate_members=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    "Scam Investigator": {
        "color": "6B70C8",
        "permissions": discord.Permissions(
            manage_messages=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    "Junior Scam Investigator": {
        "color": "5686B8",
        "permissions": discord.Permissions(
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    "Trial Scam Investigator": {
        "color": "55A6B0",
        "permissions": discord.Permissions(
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    # Staff
    "Staff": {
        "color": "9B9BBA",
        "permissions": discord.Permissions(
            manage_messages=True,
            moderate_members=True,
            read_message_history=True,
            send_messages=True,
            view_channel=True,
        ),
    },

    # Recognition roles
    "Staff of the Month": {
        "color": "F0C75E",
        "permissions": discord.Permissions.none(),
    },

    "Staff of the Week": {
        "color": "C49B50",
        "permissions": discord.Permissions.none(),
    },

    # Member roles
    "Verified Member": {
        "color": "6595D8",
        "permissions": discord.Permissions(
            read_message_history=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            view_channel=True,
        ),
    },

    "Community Member": {
        "color": "A0A0A0",
        "permissions": discord.Permissions(
            read_message_history=True,
            send_messages=True,
            view_channel=True,
            add_reactions=True,
        ),
    },
}


# ==========================================
# SERVER LAYOUT
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
# BOT
# ==========================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================================
# PERMISSION HELPERS
# ==========================================

def make_permissions(
    view=True,
    send=False,
    attach=False,
    manage_messages=False,
    embed=False
):
    return discord.PermissionOverwrite(
        view_channel=view,
        send_messages=send,
        read_message_history=True,
        attach_files=attach,
        embed_links=embed,
        add_reactions=send,
        manage_messages=manage_messages
    )


def get_roles(roles, names):
    return [roles[name] for name in names]


INVESTIGATOR_ROLES = [
    "Trial Scam Investigator",
    "Junior Scam Investigator",
    "Scam Investigator",
    "Senior Scam Investigator",
    "Head Scam Investigator",
]

MANAGEMENT_ROLES = [
    "Sentinel Leadership",
    "Director",
    "Founder",
]

STAFF_ROLES = [
    "Staff",
    "Sentinel Leadership",
    "Director",
    "Founder",
]


# ==========================================
# DELETE OLD CHANNELS
# ==========================================

async def reset_channels(guild):

    print("Deleting old channels...")

    for channel in list(guild.channels):

        if isinstance(channel, discord.CategoryChannel):
            continue

        try:
            await channel.delete(
                reason="SENTINAL NETWORK reset"
            )
            print("Deleted channel:", channel.name)

        except discord.NotFound:
            pass

        except discord.Forbidden:
            print("Cannot delete channel:", channel.name)

        except discord.HTTPException as error:
            print("Channel error:", repr(error))

    for category in list(guild.categories):

        try:
            await category.delete(
                reason="SENTINAL NETWORK reset"
            )
            print("Deleted category:", category.name)

        except discord.NotFound:
            pass

        except discord.Forbidden:
            print("Cannot delete category:", category.name)

        except discord.HTTPException as error:
            print("Category error:", repr(error))


# ==========================================
# DELETE OLD ROLES
# ==========================================

async def delete_old_roles(guild):

    bot_member = guild.me

    if bot_member is None:
        raise RuntimeError("Bot member not found.")

    deleted = 0
    skipped = 0

    print("Deleting old roles...")

    for role in sorted(
        list(guild.roles),
        key=lambda r: r.position
    ):

        if role.is_default() or role.managed:
            skipped += 1
            continue

        if role >= bot_member.top_role:
            print("Skipped role above bot:", role.name)
            skipped += 1
            continue

        try:
            await role.delete(
                reason="SENTINAL NETWORK role reset"
            )
            deleted += 1
            print("Deleted role:", role.name)

        except discord.Forbidden:
            skipped += 1
            print("Cannot delete role:", role.name)

        except discord.HTTPException as error:
            skipped += 1
            print("Role error:", repr(error))

    return deleted, skipped


# ==========================================
# CREATE NEW ROLES
# ==========================================

async def create_roles(guild):

    roles = {}

    print("Creating roles...")

    for name, config in ROLE_CONFIG.items():

        role = await guild.create_role(
            name=name,
            colour=discord.Colour(
                int(config["color"], 16)
            ),
            permissions=config["permissions"],
            hoist=True,
            mentionable=False,
            reason="SENTINAL NETWORK role creation"
        )

        roles[name] = role

        print("Created role:", name)

    return roles


# ==========================================
# CATEGORY PERMISSIONS
# ==========================================

def get_category_permissions(guild, roles, category_name):

    everyone = guild.default_role

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
                attach=True,
                embed=True
            )
        }

    # REPORT CENTER
    if category_name == "╭── REPORT CENTER":

        overwrites = {
            everyone: make_permissions(
                view=True,
                send=False
            )
        }

        for name in (
            ["Staff"] + INVESTIGATOR_ROLES + MANAGEMENT_ROLES
        ):
            overwrites[roles[name]] = make_permissions(
                view=True,
                send=True,
                attach=True,
                manage_messages=True,
                embed=True
            )

        return overwrites

    # INVESTIGATION DIVISION
    if category_name == "╭── INVESTIGATION DIVISION":

        overwrites = {
            everyone: make_permissions(view=False)
        }

        for name in INVESTIGATOR_ROLES + MANAGEMENT_ROLES:

            overwrites[roles[name]] = make_permissions(
                view=True,
                send=True,
                attach=True,
                manage_messages=True,
                embed=True
            )

        return overwrites

    # INTERNAL AFFAIRS
    if category_name == "╭── INTERNAL AFFAIRS":

        overwrites = {
            everyone: make_permissions(view=False)
        }

        for name in STAFF_ROLES:

            overwrites[roles[name]] = make_permissions(
                view=True,
                send=True,
                attach=True,
                manage_messages=True,
                embed=True
            )

        return overwrites

    # EXECUTIVE OFFICE
    if category_name == "╭── EXECUTIVE OFFICE":

        overwrites = {
            everyone: make_permissions(view=False)
        }

        for name in MANAGEMENT_ROLES:

            overwrites[roles[name]] = make_permissions(
                view=True,
                send=True,
                attach=True,
                manage_messages=True,
                embed=True
            )

        return overwrites

    return {}


# ==========================================
# CREATE SERVER CHANNELS
# ==========================================

async def create_server(guild, roles):

    everyone = guild.default_role

    print("Creating server layout...")

    for category_name, channel_names in SERVER_LAYOUT.items():

        overwrites = get_category_permissions(
            guild,
            roles,
            category_name
        )

        category = await guild.create_category(
            name=category_name,
            overwrites=overwrites,
            reason="SENTINAL NETWORK setup"
        )

        for channel_name in channel_names:

            channel_overwrites = dict(overwrites)

            # Submission channels allow everyone to submit.
            if (
                category_name == "╭── REPORT CENTER"
                and channel_name in [
                    "│・submit-a-report",
                    "│・submit-evidence"
                ]
            ):

                channel_overwrites[everyone] = make_permissions(
                    view=True,
                    send=True,
                    attach=True,
                    embed=True
                )

            await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=channel_overwrites,
                reason="SENTINAL NETWORK setup"
            )

            print("Created channel:", channel_name)

    print("All categories and channels created!")


# ==========================================
# OWNER NOTIFICATION
# ==========================================

async def notify_owner(user, message):

    try:
        await user.send(message)

    except discord.Forbidden:
        print("Owner DMs are disabled.")

    except discord.HTTPException as error:
        print("DM error:", repr(error))


# ==========================================
# CONFIRMATION VIEW
# ==========================================

class SetupConfirmation(discord.ui.View):

    def __init__(self, guild):

        super().__init__(timeout=60)

        self.guild = guild
        self.processing = False

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
                "Only the server owner can confirm.",
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

        await interaction.response.defer(
            ephemeral=True,
            thinking=True
        )

        owner = interaction.user

        try:

            print("Starting SENTINAL NETWORK setup...")

            # 1. Delete channels.
            await reset_channels(self.guild)

            # 2. Delete old roles.
            deleted, skipped = await delete_old_roles(self.guild)

            # 3. Create new roles.
            roles = await create_roles(self.guild)

            # 4. Create categories and channels.
            await create_server(self.guild, roles)

            message = (
                "✅ **SENTINAL NETWORK SETUP COMPLETED!**\n\n"
                "• 6 categories created\n"
                "• 24 channels created\n"
                "• 13 roles created\n"
                f"• {deleted} old roles deleted\n"
                f"• {skipped} old roles skipped\n\n"
                "**Remember:** Assign the new roles to your members."
            )

            print("SETUP COMPLETED SUCCESSFULLY.")

            await notify_owner(owner, message)

            try:
                await interaction.followup.send(
                    message,
                    ephemeral=True
                )

            except discord.NotFound:
                print("Interaction expired; setup was successful.")

            except discord.HTTPException as error:
                print("Success message error:", repr(error))

        except Exception as error:

            print("SETUP FAILED:", repr(error))

            message = (
                "❌ **SETUP FAILED**\n\n"
                "Check the Bot-Hosting console.\n"
                "Some channels or roles may already have been deleted."
            )

            await notify_owner(owner, message)

            try:
                await interaction.followup.send(
                    message,
                    ephemeral=True
                )
            except discord.HTTPException:
                print("Could not send error followup.")

        finally:
            self.stop()

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
                "Only the server owner can cancel.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Setup cancelled.",
            ephemeral=True
        )

        self.stop()


# ==========================================
# /serversetup COMMAND
# ==========================================

@bot.tree.command(
    name="serversetup",
    description="Completely rebuild SENTINAL NETWORK."
)
async def serversetup(interaction: discord.Interaction):

    if interaction.guild is None:

        await interaction.response.send_message(
            "Use this command inside a server.",
            ephemeral=True
        )
        return

    if interaction.user.id != interaction.guild.owner_id:

        await interaction.response.send_message(
            "Only the server owner can use this command.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.me

    if bot_member is None:

        await interaction.response.send_message(
            "Could not find the bot.",
            ephemeral=True
        )
        return

    permissions = bot_member.guild_permissions

    if not permissions.manage_channels or not permissions.manage_roles:

        await interaction.response.send_message(
            "The bot needs Manage Channels and Manage Roles.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="SENTINAL NETWORK | SERVER RESET",
        description=(
            "⚠️ **THIS ACTION CANNOT BE UNDONE.**\n\n"
            "**WILL DELETE:**\n"
            "• All channels and categories\n"
            "• Messages in deleted channels\n"
            "• Deletable existing roles\n"
            "• Existing role assignments\n\n"
            "**WILL KEEP:**\n"
            "• Existing members\n"
            "• Server ownership\n"
            "• @everyone\n"
            "• Discord-managed roles\n"
            "• Roles above the bot's highest role\n"
            "• Server icon\n\n"
            "**WILL CREATE:**\n"
            "• 6 categories\n"
            "• 24 channels\n"
            "• 13 coloured roles\n"
            "• New role and channel permissions\n\n"
            "Founder receives Administrator permission.\n"
            "Assign new roles to members manually.\n\n"
            "**Only confirm if you understand the consequences.**"
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
# STARTUP
# ==========================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("SENTINAL NETWORK is online.")

    if not getattr(bot, "commands_synced", False):

        try:

            synced = await bot.tree.sync()

            bot.commands_synced = True

            print(f"Synced {len(synced)} slash commands.")

        except Exception as error:

            print("Sync error:", repr(error))


# ==========================================
# RUN BOT
# ==========================================

bot.run(TOKEN)

