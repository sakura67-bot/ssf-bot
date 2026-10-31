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
# SENTINAL NETWORK ROLES
# ==========================================

ROLE_CONFIG = {
    "Founder": "E5C76B",
    "Sentinel Leadership": "D4AF37",
    "Director": "B58BFF",
    "Head Scam Investigator": "9370DB",
    "Senior Scam Investigator": "8064C8",
    "Scam Investigator": "6B70C8",
    "Junior Scam Investigator": "5686B8",
    "Trial Scam Investigator": "55A6B0",
    "Staff": "9B9BBA",
    "Staff of the Month": "F0C75E",
    "Staff of the Week": "C49B50",
    "Verified Member": "6595D8",
    "Community Member": "A0A0A0",
}


# ==========================================
# EXACT SERVER LAYOUT
# ==========================================

SERVER_LAYOUT = {
    "╭── INFORMATION": [
        "│・welcome",
        "│・announcements",
        "│・rules",
        "│・server-info",
        "╰・roles",
    ],

    "╭── PUBLIC": [
        "│・general-chat",
        "╰・suggestions",
    ],

    "╭── REPORT": [
        "│・submit-a-report",
        "│・submit-evidence",
        "│・scammer-reports",
        "│・known-scammers",
        "╰・scam-server-reports",
    ],

    "╭── INVESTIGATION": [
        "│・open-cases",
        "│・under-review",
        "│・resolved-cases",
        "╰・rejected-reports",
    ],

    "╭── STAFF AREA": [
        "│・staff-chat",
        "│・staff-announcements",
        "│・staff-logs",
        "╰・staff-applications",
    ],

    "╭── MANAGEMENT": [
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

def make_permissions(view=True, send=False, attach=False):
    return discord.PermissionOverwrite(
        view_channel=view,
        send_messages=send,
        read_message_history=True,
        attach_files=attach,
        embed_links=send,
        add_reactions=send
    )


# ==========================================
# DELETE OLD CHANNELS AND CATEGORIES
# ==========================================

async def reset_channels(guild):

    print("Deleting old channels...")

    for channel in list(guild.channels):

        if isinstance(channel, discord.CategoryChannel):
            continue

        try:
            await channel.delete(
                reason="SENTINAL NETWORK server reset"
            )
            print(f"Deleted channel: {channel.name}")

        except discord.NotFound:
            pass

        except discord.Forbidden:
            print(f"Could not delete channel: {channel.name}")

        except discord.HTTPException as error:
            print(f"Channel deletion error: {error}")

    print("Deleting old categories...")

    for category in list(guild.categories):

        try:
            await category.delete(
                reason="SENTINAL NETWORK server reset"
            )
            print(f"Deleted category: {category.name}")

        except discord.NotFound:
            pass

        except discord.Forbidden:
            print(f"Could not delete category: {category.name}")

        except discord.HTTPException as error:
            print(f"Category deletion error: {error}")

    print("Channel reset completed.")


# ==========================================
# DELETE OLD ROLES
# ==========================================

async def delete_old_roles(guild):

    bot_member = guild.me

    if bot_member is None:
        raise RuntimeError("Could not find the bot's server member.")

    print("Deleting old roles...")

    deleted = 0
    skipped = 0

    # Delete from lower roles upwards.
    for role in sorted(
        list(guild.roles),
        key=lambda r: r.position
    ):

        # These roles cannot be deleted.
        if role.is_default() or role.managed:
            skipped += 1
            continue

        # The bot cannot delete roles at or above its highest role.
        if role >= bot_member.top_role:
            print(f"Skipped role above bot: {role.name}")
            skipped += 1
            continue

        try:
            await role.delete(
                reason="SENTINAL NETWORK role reset"
            )

            print(f"Deleted role: {role.name}")
            deleted += 1

        except discord.Forbidden:
            print(f"Permission denied deleting role: {role.name}")
            skipped += 1

        except discord.HTTPException as error:
            print(f"Could not delete {role.name}: {error}")
            skipped += 1

    print(f"Roles deleted: {deleted}")
    print(f"Roles skipped: {skipped}")


# ==========================================
# CREATE NEW ROLES
# ==========================================

async def create_roles(guild):

    roles = {}

    print("Creating SENTINAL NETWORK roles...")

    for role_name, hex_colour in ROLE_CONFIG.items():

        colour = discord.Colour(int(hex_colour, 16))

        role = await guild.create_role(
            name=role_name,
            colour=colour,
            hoist=True,
            permissions=discord.Permissions.none(),
            mentionable=False,
            reason="SENTINAL NETWORK role setup"
        )

        roles[role_name] = role

        print(f"Created role: {role_name}")

    print("All roles created!")

    return roles


# ==========================================
# CATEGORY PERMISSIONS
# ==========================================

def get_category_permissions(guild, roles, category_name):

    everyone = guild.default_role

    staff = roles["Staff"]
    investigator = roles["Scam Investigator"]
    junior = roles["Junior Scam Investigator"]
    trial = roles["Trial Scam Investigator"]
    senior = roles["Senior Scam Investigator"]
    head = roles["Head Scam Investigator"]

    leadership = roles["Sentinel Leadership"]
    director = roles["Director"]
    founder = roles["Founder"]

    management_roles = [
        leadership,
        director,
        founder
    ]

    investigation_roles = [
        investigator,
        junior,
        trial,
        senior,
        head
    ]

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

        overwrites = {
            everyone: make_permissions(
                view=True,
                send=False
            ),

            staff: make_permissions(
                view=True,
                send=True,
                attach=True
            )
        }

        for role in investigation_roles + management_roles:

            overwrites[role] = make_permissions(
                view=True,
                send=True,
                attach=True
            )

        return overwrites

    # INVESTIGATION DIVISION
    if category_name == "╭── INVESTIGATION DIVISION":

        overwrites = {
            everyone: make_permissions(view=False),
            staff: make_permissions(view=False)
        }

        for role in investigation_roles + management_roles:

            overwrites[role] = make_permissions(
                view=True,
                send=True,
                attach=True
            )

        return overwrites

    # INTERNAL AFFAIRS
    if category_name == "╭── INTERNAL AFFAIRS":

        overwrites = {
            everyone: make_permissions(view=False)
        }

        for role in [staff] + management_roles:

            overwrites[role] = make_permissions(
                view=True,
                send=True,
                attach=True
            )

        return overwrites

    # EXECUTIVE OFFICE
    if category_name == "╭── EXECUTIVE OFFICE":

        overwrites = {
            everyone: make_permissions(view=False)
        }

        for role in management_roles:

            overwrites[role] = make_permissions(
                view=True,
                send=True,
                attach=True
            )

        return overwrites

    return {}


# ==========================================
# CREATE SERVER STRUCTURE
# ==========================================

async def create_server(guild, roles):

    everyone = guild.default_role

    staff = roles["Staff"]
    investigator = roles["Scam Investigator"]
    junior = roles["Junior Scam Investigator"]
    trial = roles["Trial Scam Investigator"]
    senior = roles["Senior Scam Investigator"]
    head = roles["Head Scam Investigator"]

    leadership = roles["Sentinel Leadership"]
    director = roles["Director"]
    founder = roles["Founder"]

    print("Creating categories and channels...")

    for category_name, channel_names in SERVER_LAYOUT.items():

        print(f"Creating category: {category_name}")

        category_overwrites = get_category_permissions(
            guild,
            roles,
            category_name
        )

        category = await guild.create_category(
            name=category_name,
            overwrites=category_overwrites,
            reason="SENTINAL NETWORK server setup"
        )

        for channel_name in channel_names:

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
                    )
                }

                staff_and_investigators = [
                    staff,
                    investigator,
                    junior,
                    trial,
                    senior,
                    head,
                    leadership,
                    director,
                    founder
                ]

                for role in staff_and_investigators:

                    channel_overwrites[role] = make_permissions(
                        view=True,
                        send=True,
                        attach=True
                    )

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

        await interaction.response.defer(
            ephemeral=True,
            thinking=True
        )

        owner = interaction.user

        try:

            print("Starting SENTINAL NETWORK setup...")

            # 1. Delete old channels and categories.
            await reset_channels(self.guild)

            # 2. Delete old deletable roles.
            await delete_old_roles(self.guild)

            # 3. Create the new roles.
            roles = await create_roles(self.guild)

            # 4. Create the new server structure.
            await create_server(self.guild, roles)

            success_message = (
                "✅ **SENTINAL NETWORK SETUP COMPLETED!**\n\n"
                "Your server now has:\n"
                "• 6 categories\n"
                "• 24 text channels\n"
                "• 13 new roles with individual colours\n\n"
                "**The server icon was not changed.**\n\n"
                "Please assign the new roles to your members manually."
            )

            print("SETUP COMPLETED SUCCESSFULLY.")

            await notify_owner(owner, success_message)

            await interaction.followup.send(
                success_message,
                ephemeral=True
            )

        except Exception as error:

            print("SETUP ERROR:", repr(error))

            error_message = (
                "❌ **SETUP FAILED**\n\n"
                "An error occurred while rebuilding the server.\n"
                "Check the Bot-Hosting console for details.\n\n"
                "Some channels or roles may already have been deleted."
            )

            await notify_owner(owner, error_message)

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
# SERVER SETUP COMMAND
# ==========================================

@bot.tree.command(
    name="serversetup",
    description="Completely rebuild the SENTINAL NETWORK server."
)
async def serversetup(interaction: discord.Interaction):

    if interaction.guild is None:

        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return

    # Only the actual server owner.
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

    embed = discord.Embed(
        title="SENTINAL NETWORK | COMPLETE SERVER RESET",
        description=(
            "⚠️ **WARNING: THIS ACTION IS DESTRUCTIVE.**\n\n"

            "**THIS WILL DELETE:**\n"
            "• All existing channels\n"
            "• All existing categories\n"
            "• Messages inside deleted channels\n"
            "• All deletable existing roles\n\n"

            "**THIS WILL KEEP:**\n"
            "• Server ownership\n"
            "• Existing members\n"
            "• The @everyone role\n"
            "• Discord-managed roles and integrations\n"
            "• Roles the bot cannot delete due to role hierarchy\n"
            "• Your server icon\n\n"

            "**NEW ROLES:**\n"
            "• Founder\n"
            "• Sentinel Leadership\n"
            "• Director\n"
            "• Head Scam Investigator\n"
            "• Senior Scam Investigator\n"
            "• Scam Investigator\n"
            "• Junior Scam Investigator\n"
            "• Trial Scam Investigator\n"
            "• Staff\n"
            "• Staff of the Month\n"
            "• Staff of the Week\n"
            "• Verified Member\n"
            "• Community Member\n\n"

            "Old role assignments will be lost. You will need to "
            "assign the new roles to members manually.\n\n"

            "**Only press confirm if you are certain.**"
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

            print(f"Synced {len(synced)} slash commands.")

        except Exception as error:

            print("COMMAND SYNC ERROR:", repr(error))


# ==========================================
# START BOT
# ==========================================

bot.run(TOKEN)
