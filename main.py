import os
import discord
import aiosqlite

from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ==============================
# CONFIGURATION
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

DATABASE = "sentinel.db"

PURPLE = 0x8B5CF6
DARK_PURPLE = 0x24143D
WHITE = 0xFFFFFF
GREY = 0xA1A1AA

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ==============================
# DATABASE
# ==============================

async def setup_database():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                reported_user TEXT NOT NULL,
                report_type TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence TEXT,
                status TEXT DEFAULT 'Pending',
                assigned_to INTEGER,
                created_at TEXT NOT NULL,
                decision TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS scammer_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_identifier TEXT NOT NULL,
                case_id INTEGER NOT NULL,
                finding TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.commit()


# ==============================
# EMBEDS AND PERMISSIONS
# ==============================

def sentinel_embed(title, description=None):
    embed = discord.Embed(
        title=f"✦ SENTINEL NETWORK | {title}",
        description=description,
        color=PURPLE,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(
        text="SENTINEL NETWORK • Investigation Division"
    )

    return embed


def is_staff(interaction: discord.Interaction):
    if interaction.guild is None:
        return False

    if interaction.user.guild_permissions.administrator:
        return True

    return any(
        role.id == STAFF_ROLE_ID
        for role in interaction.user.roles
    )


async def staff_check(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return False

    return True


async def send_log(guild, embed):
    if not LOG_CHANNEL_ID:
        return

    channel = guild.get_channel(LOG_CHANNEL_ID)

    if channel and isinstance(channel, discord.TextChannel):
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print("Missing permission to send logs.")


# ==============================
# REPORT MODAL
# ==============================

class ReportModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Submit a Sentinel Report")

        self.reported_user = discord.ui.TextInput(
            label="Reported user / Discord ID",
            placeholder="Enter their username or ID",
            max_length=100
        )

        self.report_type = discord.ui.TextInput(
            label="Report type",
            placeholder="Scammer / TWC / Scam server / Other",
            max_length=50
        )

        self.description = discord.ui.TextInput(
            label="What happened?",
            style=discord.TextStyle.paragraph,
            placeholder="Explain the situation clearly.",
            max_length=2000
        )

        self.evidence = discord.ui.TextInput(
            label="Evidence links",
            style=discord.TextStyle.paragraph,
            placeholder="Paste relevant links. Do not share passwords.",
            required=False,
            max_length=1000
        )

        self.add_item(self.reported_user)
        self.add_item(self.report_type)
        self.add_item(self.description)
        self.add_item(self.evidence)

    async def on_submit(self, interaction: discord.Interaction):
        created = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute("""
                INSERT INTO reports (
                    guild_id,
                    reporter_id,
                    reported_user,
                    report_type,
                    description,
                    evidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.guild_id,
                interaction.user.id,
                str(self.reported_user),
                str(self.report_type),
                str(self.description),
                str(self.evidence),
                created
            ))

            report_id = cursor.lastrowid
            await db.commit()

        embed = sentinel_embed(
            f"New Report #{report_id}",
            "A new report has been submitted and is awaiting staff review."
        )

        embed.add_field(
            name="Reported account",
            value=str(self.reported_user),
            inline=True
        )

        embed.add_field(
            name="Report type",
            value=str(self.report_type),
            inline=True
        )

        embed.add_field(
            name="Submitted by",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="Description",
            value=str(self.description)[:1024],
            inline=False
        )

        embed.add_field(
            name="Evidence",
            value=str(self.evidence)[:1024] or "Not provided",
            inline=False
        )

        embed.add_field(
            name="Status",
            value="🟡 Pending review",
            inline=False
        )

        await send_log(interaction.guild, embed)

        await interaction.response.send_message(
            f"✅ Your report was submitted. Report ID: **#{report_id}**\n"
            "It will be reviewed by the investigation team.",
            ephemeral=True
        )


# ==============================
# REPORT COMMAND
# ==============================

@bot.tree.command(
    name="report",
    description="Submit a report to Sentinel Network."
)
async def report(interaction: discord.Interaction):
    await interaction.response.send_modal(ReportModal())


# ==============================
# VIEW A CASE
# ==============================

@bot.tree.command(
    name="case",
    description="View a report by its case ID."
)
@app_commands.describe(case_id="The report ID")
async def case(interaction: discord.Interaction, case_id: int):

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("""
            SELECT id, reporter_id, reported_user, report_type,
                   description, evidence, status, assigned_to,
                   created_at, decision
            FROM reports
            WHERE id = ? AND guild_id = ?
        """, (case_id, interaction.guild_id))

        record = await cursor.fetchone()

    if not record:
        return await interaction.response.send_message(
            "❌ Case not found.",
            ephemeral=True
        )

    (
        report_id, reporter_id, reported_user, report_type,
        description, evidence, status, assigned_to,
        created_at, decision
    ) = record

    # Only staff and the original reporter can view case details.
    if not is_staff(interaction) and interaction.user.id != reporter_id:
        return await interaction.response.send_message(
            "❌ You cannot view this case.",
            ephemeral=True
        )

    embed = sentinel_embed(f"Case #{report_id}")

    embed.add_field(name="Reported account", value=reported_user)
    embed.add_field(name="Type", value=report_type)
    embed.add_field(name="Status", value=status)
    embed.add_field(name="Reporter", value=f"<@{reporter_id}>")

    embed.add_field(
        name="Description",
        value=description[:1024],
        inline=False
    )

    if is_staff(interaction):
        embed.add_field(
            name="Evidence",
            value=evidence or "None provided",
            inline=False
        )

        embed.add_field(
            name="Assigned investigator",
            value=f"<@{assigned_to}>" if assigned_to else "Unassigned"
        )

        embed.add_field(
            name="Staff decision",
            value=decision or "No decision recorded",
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==============================
# LIST PENDING REPORTS
# ==============================

@bot.tree.command(
    name="reports",
    description="View the latest reports awaiting review."
)
async def reports(interaction: discord.Interaction):

    if not await staff_check(interaction):
        return

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("""
            SELECT id, reported_user, report_type, status
            FROM reports
            WHERE guild_id = ? AND status = 'Pending'
            ORDER BY id DESC LIMIT 10
        """, (interaction.guild_id,))

        records = await cursor.fetchall()

    embed = sentinel_embed("Pending Reports")

    if not records:
        embed.description = "There are no pending reports."
    else:
        for report_id, user, report_type, status in records:
            embed.add_field(
                name=f"Case #{report_id}",
                value=(
                    f"Account: {user}\n"
                    f"Type: {report_type}\n"
                    f"Status: {status}"
                ),
                inline=False
            )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==============================
# ASSIGN INVESTIGATOR
# ==============================

@bot.tree.command(
    name="assigncase",
    description="Assign a report to an investigator."
)
@app_commands.describe(
    case_id="Report ID",
    investigator="Investigator to assign"
)
async def assigncase(
    interaction: discord.Interaction,
    case_id: int,
    investigator: discord.Member
):

    if not await staff_check(interaction):
        return

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("""
            UPDATE reports
            SET assigned_to = ?
            WHERE id = ? AND guild_id = ?
        """, (
            investigator.id,
            case_id,
            interaction.guild_id
        ))

        await db.commit()

        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ Case not found.",
                ephemeral=True
            )

    embed = sentinel_embed(
        f"Case #{case_id} Assigned",
        f"Assigned investigator: {investigator.mention}"
    )

    await send_log(interaction.guild, embed)

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==============================
# UPDATE CASE STATUS
# ==============================

@bot.tree.command(
    name="updatecase",
    description="Update a case status and record a staff decision."
)
@app_commands.describe(
    case_id="Report ID",
    status="New case status",
    decision="Explain the review outcome"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Under Review", value="Under Review"),
    app_commands.Choice(name="Resolved - Finding Recorded", value="Resolved - Finding Recorded"),
    app_commands.Choice(name="Rejected", value="Rejected"),
    app_commands.Choice(name="Needs More Context", value="Needs More Context")
])
async def updatecase(
    interaction: discord.Interaction,
    case_id: int,
    status: app_commands.Choice[str],
    decision: str
):

    if not await staff_check(interaction):
        return

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("""
            UPDATE reports
            SET status = ?, decision = ?
            WHERE id = ? AND guild_id = ?
        """, (
            status.value,
            decision,
            case_id,
            interaction.guild_id
        ))

        await db.commit()

        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ Case not found.",
                ephemeral=True
            )

    embed = sentinel_embed(
        f"Case #{case_id} Updated",
        f"**New status:** {status.value}\n"
        f"**Decision:** {decision}\n"
        f"**Reviewed by:** {interaction.user.mention}"
    )

    await send_log(interaction.guild, embed)

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==============================
# SEARCH SCAMMER FILES
# ==============================

@bot.tree.command(
    name="scammer",
    description="Search reviewed Sentinel findings."
)
@app_commands.describe(identifier="Username or Discord ID to search")
async def scammer(
    interaction: discord.Interaction,
    identifier: str
):

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("""
            SELECT user_identifier, case_id, finding, created_at
            FROM scammer_files
            WHERE guild_id = ? AND user_identifier LIKE ?
            ORDER BY id DESC LIMIT 10
        """, (
            interaction.guild_id,
            f"%{identifier}%"
        ))

        records = await cursor.fetchall()

    embed = sentinel_embed("Scammer Files")

    if not records:
        embed.description = (
            "No reviewed findings were found for that search.\n"
            "This does not mean the account has been cleared."
        )
    else:
        for user, case_id, finding, created_at in records:
            embed.add_field(
                name=f"{user} • Case #{case_id}",
                value=f"{finding}\nRecorded: {created_at[:10]}",
                inline=False
            )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ==============================
# BOT STARTUP
# ==============================

@bot.event
async def on_ready():
    await setup_database()

    if not getattr(bot, "synced", False):
        synced = await bot.tree.sync()
        bot.synced = True
        print(f"Synced {len(synced)} slash commands.")

    print(f"Sentinel Network online as {bot.user}")


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Add it to your hosting environment variables."
    )

bot.run(TOKEN)
