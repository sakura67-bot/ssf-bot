
import os
import discord
import aiosqlite

from datetime import datetime, timezone
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE = "sentinel.db"
PREFIX = ";"

PURPLE = 0x7651A8
DARK_PURPLE = 0x24143D
WHITE = 0xFFFFFF
BLACK = 0x111111

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ==================================================
# DATABASE
# ==================================================

async def setup_database():
    async with aiosqlite.connect(DATABASE) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            staff_role_id INTEGER,
            supervisor_role_id INTEGER,
            log_channel_id INTEGER,
            ticket_category_id INTEGER
        )
        """)

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
            decision TEXT,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS scammer_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            case_id INTEGER NOT NULL,
            finding TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS twc_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            case_id INTEGER NOT NULL,
            finding TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            evidence_text TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS case_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            decision TEXT,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            moderator_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            moderator_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_ranks (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rank TEXT NOT NULL,
            updated_by INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Open',
            created_at TEXT NOT NULL
        )
        """)

        await db.commit()


async def execute(query, params=()):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.lastrowid, cursor.rowcount


async def fetch_one(query, params=()):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()


async def fetch_all(query, params=()):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def settings(guild_id):
    result = await fetch_one(
        "SELECT staff_role_id, supervisor_role_id, log_channel_id, "
        "ticket_category_id FROM settings WHERE guild_id = ?",
        (guild_id,)
    )

    return result or (None, None, None, None)


async def save_setting(guild_id, column, value):
    allowed = {
        "staff_role_id",
        "supervisor_role_id",
        "log_channel_id",
        "ticket_category_id"
    }

    if column not in allowed:
        raise ValueError("Invalid setting")

    await execute(
        "INSERT OR IGNORE INTO settings (guild_id) VALUES (?)",
        (guild_id,)
    )

    await execute(
        f"UPDATE settings SET {column} = ? WHERE guild_id = ?",
        (value, guild_id)
    )


# ==================================================
# EMBEDS AND PERMISSIONS
# ==================================================

def embed(title, description=None, color=PURPLE):
    result = discord.Embed(
        title=f"SENTINEL NETWORK | {title}",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    result.set_footer(text="SENTINEL NETWORK | Investigation Division")
    return result


async def is_staff(member):
    if member.guild_permissions.administrator:
        return True

    staff_role, supervisor_role, _, _ = await settings(member.guild.id)

    role_ids = {role.id for role in member.roles}

    return (
        staff_role in role_ids if staff_role else False
    ) or (
        supervisor_role in role_ids if supervisor_role else False
    )


async def staff_only(ctx):
    if not await is_staff(ctx.author):
        await ctx.send("You do not have permission to use this command.")
        return False
    return True


async def supervisor_only(ctx):
    if ctx.author.guild_permissions.administrator:
        return True

    _, supervisor_role, _, _ = await settings(ctx.guild.id)

    if supervisor_role and any(
        role.id == supervisor_role for role in ctx.author.roles
    ):
        return True

    await ctx.send("Only supervisors or administrators can use this command.")
    return False


async def log_action(guild, title, description):
    _, _, log_channel_id, _ = await settings(guild.id)

    if not log_channel_id:
        return

    channel = guild.get_channel(log_channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(log_channel_id)
        except discord.HTTPException:
            return

    try:
        await channel.send(embed=embed(title, description))
    except discord.HTTPException:
        print("Could not send log message.")


async def get_case(guild_id, case_id):
    return await fetch_one(
        "SELECT id, reporter_id, reported_user, report_type, description, "
        "evidence, status, assigned_to, decision, created_at "
        "FROM reports WHERE guild_id = ? AND id = ?",
        (guild_id, case_id)
    )


# ==================================================
# CONFIGURATION COMMANDS
# ==================================================

@bot.command(name="setstaff")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def setstaff(ctx, role: discord.Role = None):
    if role is None:
        return await ctx.send("Usage: `;setstaff @Role`")

    if role.is_default or role.managed:
        return await ctx.send("That role cannot be used.")

    await save_setting(ctx.guild.id, "staff_role_id", role.id)

    await ctx.send(embed=embed(
        "Staff Role Updated",
        f"Staff role: {role.mention}"
    ))

    await log_action(
        ctx.guild,
        "Configuration Updated",
        f"{ctx.author.mention} changed the staff role to {role.mention}."
    )


@bot.command(name="setstaffsupervisor")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def setstaffsupervisor(ctx, role: discord.Role = None):
    if role is None:
        return await ctx.send("Usage: `;setstaffsupervisor @Role`")

    await save_setting(ctx.guild.id, "supervisor_role_id", role.id)

    await ctx.send(embed=embed(
        "Supervisor Role Updated",
        f"Supervisor role: {role.mention}"
    ))


@bot.command(name="setlog")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel = None):
    if channel is None:
        return await ctx.send("Usage: `;setlog #channel`")

    permissions = channel.permissions_for(ctx.guild.me)

    if not permissions.send_messages or not permissions.embed_links:
        return await ctx.send(
            "I need Send Messages and Embed Links in that channel."
        )

    await save_setting(ctx.guild.id, "log_channel_id", channel.id)

    await ctx.send(embed=embed(
        "Log Channel Updated",
        f"Logging channel: {channel.mention}"
    ))

    await log_action(
        ctx.guild,
        "Logging Test",
        "Sentinel logging is working."
    )


@bot.command(name="setticketcategory")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def setticketcategory(ctx, category: discord.CategoryChannel = None):
    if category is None:
        return await ctx.send(
            "Usage: `;setticketcategory CATEGORY_ID`"
        )

    await save_setting(ctx.guild.id, "ticket_category_id", category.id)

    await ctx.send(embed=embed(
        "Ticket Category Updated",
        f"Ticket category: {category.name}"
    ))


@bot.command(name="sentinelconfig")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def sentinelconfig(ctx):
    staff_role, supervisor_role, log_channel, ticket_category = await settings(
        ctx.guild.id
    )

    def role_value(role_id):
        role = ctx.guild.get_role(role_id) if role_id else None
        return role.mention if role else "Not configured"

    def channel_value(channel_id):
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        return channel.mention if channel else "Not configured"

    result = embed("Server Configuration")
    result.add_field(name="Staff Role", value=role_value(staff_role))
    result.add_field(name="Supervisor Role", value=role_value(supervisor_role))
    result.add_field(name="Log Channel", value=channel_value(log_channel))
    result.add_field(name="Ticket Category", value=channel_value(ticket_category))
    result.add_field(name="Prefix", value="`;`")

    await ctx.send(embed=result)


# ==================================================
# REPORT SUBMISSION
# ==================================================

class ReportModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Sentinel Report Submission")

        self.reported = discord.ui.TextInput(
            label="Reported username or Discord ID",
            max_length=100
        )

        self.report_type = discord.ui.TextInput(
            label="Report type",
            placeholder="Scammer, TWC, scam server, other",
            max_length=50
        )

        self.description = discord.ui.TextInput(
            label="Describe what happened",
            style=discord.TextStyle.paragraph,
            max_length=2000
        )

        self.evidence = discord.ui.TextInput(
            label="Evidence links",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )

        self.add_item(self.reported)
        self.add_item(self.report_type)
        self.add_item(self.description)
        self.add_item(self.evidence)

    async def on_submit(self, interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "Reports must be submitted inside the server.",
                ephemeral=True
            )

        created = datetime.now(timezone.utc).isoformat()

        report_id, _ = await execute("""
            INSERT INTO reports (
                guild_id, reporter_id, reported_user, report_type,
                description, evidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction.guild.id,
            interaction.user.id,
            str(self.reported),
            str(self.report_type),
            str(self.description),
            str(self.evidence),
            created
        ))

        result = embed(
            f"New Report #{report_id}",
            "A report has been submitted and is awaiting review."
        )

        result.add_field(name="Reported account", value=str(self.reported))
        result.add_field(name="Type", value=str(self.report_type))
        result.add_field(name="Reporter", value=interaction.user.mention)
        result.add_field(
            name="Description",
            value=str(self.description)[:1024],
            inline=False
        )
        result.add_field(
            name="Evidence",
            value=str(self.evidence)[:1024] or "Not provided",
            inline=False
        )
        result.add_field(name="Status", value="Pending")

        await log_action(
            interaction.guild,
            f"New Report #{report_id}",
            f"Reporter: {interaction.user.mention}\n"
            f"Reported account: {self.reported}\n"
            f"Type: {self.report_type}\n"
            f"Description: {self.description}\n"
            f"Evidence: {self.evidence or 'Not provided'}"
        )

        await interaction.response.send_message(
            f"Your report has been submitted. Case ID: #{report_id}.",
            ephemeral=True
        )


class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Submit Report",
        style=discord.ButtonStyle.primary,
        custom_id="sentinel:report"
    )
    async def submit(self, interaction, button):
        await interaction.response.send_modal(ReportModal())


@bot.command(name="report")
@commands.guild_only()
async def report(ctx):
    await ctx.send(
        embed=embed(
            "Report Centre",
            "Select the button below to submit a report for review."
        ),
        view=ReportView()
    )


# ==================================================
# REPORT LIST AND CASE MANAGEMENT
# ==================================================

@bot.command(name="reports")
@commands.guild_only()
async def reports(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, reported_user, report_type, status
        FROM reports
        WHERE guild_id = ?
        ORDER BY id DESC LIMIT 15
    """, (ctx.guild.id,))

    result = embed("Recent Reports")

    if not records:
        result.description = "No reports have been submitted."
    else:
        for case_id, user, report_type, status in records:
            result.add_field(
                name=f"Case #{case_id}",
                value=f"Account: {user}\nType: {report_type}\nStatus: {status}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="reportinfo")
@commands.guild_only()
async def reportinfo(ctx, case_id: int):
    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    if not await is_staff(ctx.author) and ctx.author.id != record[1]:
        return await ctx.send("You cannot view this case.")

    result = embed(f"Case #{record[0]}")
    result.add_field(name="Reporter", value=f"<@{record[1]}>")
    result.add_field(name="Reported account", value=record[2])
    result.add_field(name="Type", value=record[3])
    result.add_field(name="Status", value=record[6])
    result.add_field(name="Description", value=record[4][:1024], inline=False)

    if await is_staff(ctx.author):
        result.add_field(
            name="Evidence",
            value=record[5] or "None",
            inline=False
        )
        result.add_field(
            name="Assigned investigator",
            value=f"<@{record[7]}>" if record[7] else "Unassigned"
        )
        result.add_field(
            name="Decision",
            value=record[8] or "No decision recorded",
            inline=False
        )

    await ctx.send(embed=result)


@bot.command(name="accept")
@commands.guild_only()
async def accept(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    await execute("""
        UPDATE reports SET status = 'Under Review'
        WHERE guild_id = ? AND id = ?
    """, (ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} has been accepted for review.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Accepted",
        f"Accepted by {ctx.author.mention}."
    )


@bot.command(name="reject")
@commands.guild_only()
async def reject(ctx, case_id: int, *, reason: str):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    await execute("""
        UPDATE reports
        SET status = 'Rejected', decision = ?
        WHERE guild_id = ? AND id = ?
    """, (reason, ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} has been rejected.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Rejected",
        f"Reason: {reason}\nModerator: {ctx.author.mention}"
    )


@bot.command(name="claim")
@commands.guild_only()
async def claim(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    if record[7]:
        return await ctx.send("This case is already assigned.")

    await execute("""
        UPDATE reports SET assigned_to = ?
        WHERE guild_id = ? AND id = ?
    """, (ctx.author.id, ctx.guild.id, case_id))

    await ctx.send(f"You claimed case #{case_id}.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Claimed",
        f"Claimed by {ctx.author.mention}."
    )


@bot.command(name="unclaim")
@commands.guild_only()
async def unclaim(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    if record[7] != ctx.author.id and not ctx.author.guild_permissions.administrator:
        return await ctx.send("You can only unclaim your own cases.")

    await execute("""
        UPDATE reports SET assigned_to = NULL
        WHERE guild_id = ? AND id = ?
    """, (ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} is now unassigned.")


@bot.command(name="assigncase")
@commands.guild_only()
async def assigncase(ctx, case_id: int, member: discord.Member):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    if not await is_staff(member):
        return await ctx.send("The selected member is not configured as staff.")

    await execute("""
        UPDATE reports SET assigned_to = ?
        WHERE guild_id = ? AND id = ?
    """, (member.id, ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} assigned to {member.mention}.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Assigned",
        f"Assigned to {member.mention} by {ctx.author.mention}."
    )


@bot.command(name="updatecase")
@commands.guild_only()
async def updatecase(ctx, case_id: int, status: str, *, decision: str):
    if not await staff_only(ctx):
        return

    allowed = {
        "pending",
        "under-review",
        "resolved",
        "rejected",
        "needs-context"
    }

    if status.lower() not in allowed:
        return await ctx.send(
            "Statuses: pending, under-review, resolved, rejected, needs-context."
        )

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    formatted = status.replace("-", " ").title()

    await execute("""
        UPDATE reports SET status = ?, decision = ?
        WHERE guild_id = ? AND id = ?
    """, (formatted, decision, ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} updated to {formatted}.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Updated",
        f"Status: {formatted}\nDecision: {decision}\n"
        f"Updated by: {ctx.author.mention}"
    )


@bot.command(name="resolve")
@commands.guild_only()
async def resolve(ctx, case_id: int, *, finding: str):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    await execute("""
        UPDATE reports SET status = 'Resolved', decision = ?
        WHERE guild_id = ? AND id = ?
    """, (finding, ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} has been marked resolved.")

    await log_action(
        ctx.guild,
        f"Case #{case_id} Resolved",
        f"Finding: {finding}\nReviewed by: {ctx.author.mention}"
    )


@bot.command(name="reopen")
@commands.guild_only()
async def reopen(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    await execute("""
        UPDATE reports SET status = 'Under Review'
        WHERE guild_id = ? AND id = ?
    """, (ctx.guild.id, case_id))

    await ctx.send(f"Case #{case_id} has been reopened.")


# ==================================================
# EVIDENCE AND INTERNAL NOTES
# ==================================================

@bot.command(name="addevidence")
@commands.guild_only()
async def addevidence(ctx, case_id: int, *, evidence_text: str):
    if not await staff_only(ctx):
        return

    if not await get_case(ctx.guild.id, case_id):
        return await ctx.send("Case not found.")

    evidence_id, _ = await execute("""
        INSERT INTO evidence (
            guild_id, case_id, evidence_text, added_by, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        case_id,
        evidence_text,
        ctx.author.id,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"Evidence #{evidence_id} added to case #{case_id}.")

    await log_action(
        ctx.guild,
        f"Evidence Added to Case #{case_id}",
        f"Evidence ID: {evidence_id}\nAdded by: {ctx.author.mention}"
    )


@bot.command(name="evidence")
@commands.guild_only()
async def evidence(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, evidence_text, added_by, created_at
        FROM evidence
        WHERE guild_id = ? AND case_id = ?
        ORDER BY id DESC
    """, (ctx.guild.id, case_id))

    result = embed(f"Evidence for Case #{case_id}")

    if not records:
        result.description = "No evidence has been added."
    else:
        for evidence_id, text, added_by, created_at in records[:10]:
            result.add_field(
                name=f"Evidence #{evidence_id}",
                value=f"{text[:700]}\nAdded by: <@{added_by}>",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="removeevidence")
@commands.guild_only()
async def removeevidence(ctx, evidence_id: int):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        DELETE FROM evidence
        WHERE id = ? AND guild_id = ?
    """, (evidence_id, ctx.guild.id))

    await ctx.send(
        "Evidence removed." if count else "Evidence not found."
    )


@bot.command(name="addnote")
@commands.guild_only()
async def addnote(ctx, case_id: int, *, note: str):
    if not await staff_only(ctx):
        return

    if not await get_case(ctx.guild.id, case_id):
        return await ctx.send("Case not found.")

    await execute("""
        INSERT INTO case_notes (
            guild_id, case_id, note, added_by, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        case_id,
        note,
        ctx.author.id,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"Internal note added to case #{case_id}.")


@bot.command(name="history")
@commands.guild_only()
async def history(ctx, case_id: int):
    if not await staff_only(ctx):
        return

    if not await get_case(ctx.guild.id, case_id):
        return await ctx.send("Case not found.")

    notes = await fetch_all("""
        SELECT note, added_by, created_at
        FROM case_notes
        WHERE guild_id = ? AND case_id = ?
        ORDER BY id DESC LIMIT 10
    """, (ctx.guild.id, case_id))

    result = embed(f"Internal History for Case #{case_id}")

    if not notes:
        result.description = "No internal notes."
    else:
        for note, added_by, created_at in notes:
            result.add_field(
                name=f"Note by {added_by}",
                value=f"{note[:700]}\n{created_at[:10]}",
                inline=False
            )

    await ctx.send(embed=result)


# ==================================================
# SCAMMER FILES
# ==================================================

@bot.command(name="addscammer")
@commands.guild_only()
async def addscammer(ctx, case_id: int, identifier: str, *, finding: str):
    if not await supervisor_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    if record[6] != "Resolved":
        return await ctx.send(
            "Only resolved cases can be added to reviewed scammer files."
        )

    file_id, _ = await execute("""
        INSERT INTO scammer_files (
            guild_id, identifier, case_id, finding, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        identifier,
        case_id,
        finding,
        ctx.author.id,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"Scammer file #{file_id} created.")

    await log_action(
        ctx.guild,
        "Scammer File Created",
        f"File: #{file_id}\nAccount: {identifier}\n"
        f"Case: #{case_id}\nCreated by: {ctx.author.mention}"
    )


@bot.command(name="scammer")
@commands.guild_only()
async def scammer(ctx, *, identifier: str):
    records = await fetch_all("""
        SELECT id, identifier, case_id, finding, created_at
        FROM scammer_files
        WHERE guild_id = ? AND identifier LIKE ?
        ORDER BY id DESC LIMIT 10
    """, (ctx.guild.id, f"%{identifier}%"))

    result = embed("Reviewed Scammer Files")

    if not records:
        result.description = "No reviewed records matched that search."
    else:
        for file_id, user, case_id, finding, created_at in records:
            result.add_field(
                name=f"File #{file_id} | {user}",
                value=f"Case: #{case_id}\nFinding: {finding}\n"
                      f"Recorded: {created_at[:10]}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="scammerlist")
@commands.guild_only()
async def scammerlist(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, identifier, case_id
        FROM scammer_files
        WHERE guild_id = ?
        ORDER BY id DESC LIMIT 15
    """, (ctx.guild.id,))

    result = embed("Scammer File Index")

    if not records:
        result.description = "No records found."
    else:
        for file_id, identifier, case_id in records:
            result.add_field(
                name=f"File #{file_id}",
                value=f"Account: {identifier}\nCase: #{case_id}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="editscammer")
@commands.guild_only()
async def editscammer(ctx, file_id: int, *, finding: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        UPDATE scammer_files SET finding = ?
        WHERE id = ? AND guild_id = ?
    """, (finding, file_id, ctx.guild.id))

    await ctx.send("Scammer file updated." if count else "File not found.")


@bot.command(name="removescammer")
@commands.guild_only()
async def removescammer(ctx, file_id: int, *, reason: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        DELETE FROM scammer_files
        WHERE id = ? AND guild_id = ?
    """, (file_id, ctx.guild.id))

    await ctx.send("Scammer file removed." if count else "File not found.")

    if count:
        await log_action(
            ctx.guild,
            "Scammer File Removed",
            f"File: #{file_id}\nReason: {reason}\n"
            f"Removed by: {ctx.author.mention}"
        )


# ==================================================
# TWC RECORDS
# ==================================================

@bot.command(name="addtwc")
@commands.guild_only()
async def addtwc(ctx, case_id: int, identifier: str, *, finding: str):
    if not await supervisor_only(ctx):
        return

    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    file_id, _ = await execute("""
        INSERT INTO twc_records (
            guild_id, identifier, case_id, finding, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        identifier,
        case_id,
        finding,
        ctx.author.id,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"TWC record #{file_id} created.")

    await log_action(
        ctx.guild,
        "TWC Record Created",
        f"Record: #{file_id}\nAccount: {identifier}\n"
        f"Case: #{case_id}\nCreated by: {ctx.author.mention}"
    )


@bot.command(name="twc")
@commands.guild_only()
async def twc(ctx, *, identifier: str):
    records = await fetch_all("""
        SELECT id, identifier, case_id, finding, created_at
        FROM twc_records
        WHERE guild_id = ? AND identifier LIKE ?
        ORDER BY id DESC LIMIT 10
    """, (ctx.guild.id, f"%{identifier}%"))

    result = embed("TWC Records")

    if not records:
        result.description = "No TWC records matched that search."
    else:
        for record_id, user, case_id, finding, created_at in records:
            result.add_field(
                name=f"TWC #{record_id} | {user}",
                value=f"Case: #{case_id}\nFinding: {finding}\n"
                      f"Recorded: {created_at[:10]}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="twclist")
@commands.guild_only()
async def twclist(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, identifier, case_id
        FROM twc_records
        WHERE guild_id = ?
        ORDER BY id DESC LIMIT 15
    """, (ctx.guild.id,))

    result = embed("TWC Record Index")

    if not records:
        result.description = "No records found."
    else:
        for record_id, identifier, case_id in records:
            result.add_field(
                name=f"TWC #{record_id}",
                value=f"Account: {identifier}\nCase: #{case_id}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="edittwc")
@commands.guild_only()
async def edittwc(ctx, record_id: int, *, finding: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        UPDATE twc_records SET finding = ?
        WHERE id = ? AND guild_id = ?
    """, (finding, record_id, ctx.guild.id))

    await ctx.send("TWC record updated." if count else "Record not found.")


@bot.command(name="removetwc")
@commands.guild_only()
async def removetwc(ctx, record_id: int, *, reason: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        DELETE FROM twc_records
        WHERE id = ? AND guild_id = ?
    """, (record_id, ctx.guild.id))

    await ctx.send("TWC record removed." if count else "Record not found.")

    if count:
        await log_action(
            ctx.guild,
            "TWC Record Removed",
            f"Record: #{record_id}\nReason: {reason}\n"
            f"Removed by: {ctx.author.mention}"
        )


@bot.command(name="reviewtwc")
@commands.guild_only()
async def reviewtwc(ctx, record_id: int, *, finding: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        UPDATE twc_records SET finding = ?
        WHERE id = ? AND guild_id = ?
    """, (finding, record_id, ctx.guild.id))

    await ctx.send("TWC review updated." if count else "Record not found.")


# ==================================================
# APPEALS
# ==================================================

@bot.command(name="appeal")
@commands.guild_only()
async def appeal(ctx, case_id: int, *, reason: str):
    record = await get_case(ctx.guild.id, case_id)

    if not record:
        return await ctx.send("Case not found.")

    appeal_id, _ = await execute("""
        INSERT INTO appeals (
            guild_id, case_id, user_id, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        case_id,
        ctx.author.id,
        reason,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"Your appeal has been submitted. Appeal ID: #{appeal_id}.")

    await log_action(
        ctx.guild,
        f"New Appeal #{appeal_id}",
        f"Case: #{case_id}\nUser: {ctx.author.mention}\nReason: {reason}"
    )


@bot.command(name="appeals")
@commands.guild_only()
async def appeals(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, case_id, user_id, reason, status
        FROM appeals
        WHERE guild_id = ?
        ORDER BY id DESC LIMIT 15
    """, (ctx.guild.id,))

    result = embed("Appeals")

    if not records:
        result.description = "No appeals found."
    else:
        for appeal_id, case_id, user_id, reason, status in records:
            result.add_field(
                name=f"Appeal #{appeal_id}",
                value=f"Case: #{case_id}\nUser: <@{user_id}>\n"
                      f"Reason: {reason[:300]}\nStatus: {status}",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="reviewappeal")
@commands.guild_only()
async def reviewappeal(ctx, appeal_id: int, *, decision: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        UPDATE appeals SET decision = ?, status = 'Reviewed'
        WHERE id = ? AND guild_id = ?
    """, (decision, appeal_id, ctx.guild.id))

    await ctx.send("Appeal reviewed." if count else "Appeal not found.")


@bot.command(name="acceptappeal")
@commands.guild_only()
async def acceptappeal(ctx, appeal_id: int, *, reason: str):
    if not await supervisor_only(ctx):
        return

    record = await fetch_one("""
        SELECT case_id FROM appeals
        WHERE id = ? AND guild_id = ?
    """, (appeal_id, ctx.guild.id))

    if not record:
        return await ctx.send("Appeal not found.")

    await execute("""
        UPDATE appeals SET status = 'Accepted', decision = ?
        WHERE id = ? AND guild_id = ?
    """, (reason, appeal_id, ctx.guild.id))

    await execute("""
        UPDATE reports SET status = 'Under Review', decision = ?
        WHERE id = ? AND guild_id = ?
    """, (f"Appeal accepted: {reason}", record[0], ctx.guild.id))

    await ctx.send(f"Appeal #{appeal_id} accepted.")


@bot.command(name="rejectappeal")
@commands.guild_only()
async def rejectappeal(ctx, appeal_id: int, *, reason: str):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        UPDATE appeals SET status = 'Rejected', decision = ?
        WHERE id = ? AND guild_id = ?
    """, (reason, appeal_id, ctx.guild.id))

    await ctx.send(
        f"Appeal #{appeal_id} rejected." if count else "Appeal not found."
    )


# ==================================================
# TICKETS
# ==================================================

@bot.command(name="ticketsetup")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def ticketsetup(ctx):
    await ctx.send(
        embed=embed(
            "Support Centre",
            "Select the button below to open a private support ticket."
        ),
        view=TicketPanel()
    )


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="sentinel:ticket"
    )
    async def open_ticket(self, interaction, button):
        guild = interaction.guild

        if not guild:
            return await interaction.response.send_message(
                "Tickets must be opened in a server.",
                ephemeral=True
            )

        existing = await fetch_one("""
            SELECT channel_id FROM tickets
            WHERE guild_id = ? AND user_id = ? AND status = 'Open'
        """, (guild.id, interaction.user.id))

        if existing:
            channel = guild.get_channel(existing[0])
            if channel:
                return await interaction.response.send_message(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True
                )

        _, _, _, category_id = await settings(guild.id)

        category = guild.get_channel(category_id) if category_id else None

        staff_role_id, _, _, _ = await settings(guild.id)
        staff_role = guild.get_role(staff_role_id) if staff_role_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.id}",
                category=category,
                overwrites=overwrites
            )
        except discord.HTTPException:
            return await interaction.response.send_message(
                "I could not create the ticket. Check my channel permissions.",
                ephemeral=True
            )

        ticket_id, _ = await execute("""
            INSERT INTO tickets (
                guild_id, user_id, channel_id, created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild.id,
            interaction.user.id,
            channel.id,
            datetime.now(timezone.utc).isoformat()
        ))

        await channel.send(
            content=interaction.user.mention,
            embed=embed(
                f"Ticket #{ticket_id}",
                "Please explain how the investigation team can help."
            ),
            view=TicketControls()
        )

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="sentinel:close_ticket"
    )
    async def close_ticket(self, interaction, button):
        channel = interaction.channel

        record = await fetch_one("""
            SELECT id, user_id FROM tickets
            WHERE guild_id = ? AND channel_id = ? AND status = 'Open'
        """, (interaction.guild_id, channel.id))

        if not record:
            return await interaction.response.send_message(
                "This is not an open Sentinel ticket.",
                ephemeral=True
            )

        if (
            interaction.user.id != record[1]
            and not await is_staff(interaction.user)
        ):
            return await interaction.response.send_message(
                "Only the ticket owner or staff can close this ticket.",
                ephemeral=True
            )

        await execute("""
            UPDATE tickets SET status = 'Closed'
            WHERE id = ? AND guild_id = ?
        """, (record[0], interaction.guild_id))

        await interaction.response.send_message(
            "This ticket will be deleted in a few seconds."
        )

        await channel.delete(reason=f"Ticket closed by {interaction.user}")


@bot.command(name="closeticket")
@commands.guild_only()
async def closeticket(ctx):
    record = await fetch_one("""
        SELECT id, user_id FROM tickets
        WHERE guild_id = ? AND channel_id = ? AND status = 'Open'
    """, (ctx.guild.id, ctx.channel.id))

    if not record:
        return await ctx.send("This is not an open ticket.")

    if (
        ctx.author.id != record[1]
        and not await is_staff(ctx.author)
    ):
        return await ctx.send("You cannot close this ticket.")

    await execute("""
        UPDATE tickets SET status = 'Closed'
        WHERE id = ? AND guild_id = ?
    """, (record[0], ctx.guild.id))

    await ctx.send("Ticket closed.")
    await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")


@bot.command(name="adduser")
@commands.guild_only()
async def adduser(ctx, member: discord.Member):
    record = await fetch_one("""
        SELECT user_id FROM tickets
        WHERE guild_id = ? AND channel_id = ? AND status = 'Open'
    """, (ctx.guild.id, ctx.channel.id))

    if not record:
        return await ctx.send("This is not an open ticket.")

    if ctx.author.id != record[0] and not await is_staff(ctx.author):
        return await ctx.send("You cannot manage this ticket.")

    await ctx.channel.set_permissions(
        member,
        view_channel=True,
        send_messages=True,
        read_message_history=True
    )

    await ctx.send(f"{member.mention} has been added to this ticket.")


@bot.command(name="removeuser")
@commands.guild_only()
async def removeuser(ctx, member: discord.Member):
    record = await fetch_one("""
        SELECT user_id FROM tickets
        WHERE guild_id = ? AND channel_id = ? AND status = 'Open'
    """, (ctx.guild.id, ctx.channel.id))

    if not record:
        return await ctx.send("This is not an open ticket.")

    if ctx.author.id != record[0] and not await is_staff(ctx.author):
        return await ctx.send("You cannot manage this ticket.")

    if member.id == record[0]:
        return await ctx.send("You cannot remove the ticket owner.")

    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.send(f"{member.mention} has been removed from this ticket.")


# ==================================================
# STAFF MANAGEMENT
# ==================================================

@bot.command(name="promote")
@commands.guild_only()
async def promote(ctx, member: discord.Member, *, rank: str):
    if not await supervisor_only(ctx):
        return

    await execute("""
        INSERT INTO staff_ranks (guild_id, user_id, rank, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET rank = excluded.rank, updated_by = excluded.updated_by
    """, (ctx.guild.id, member.id, rank, ctx.author.id))

    await ctx.send(f"{member.mention} has been promoted to {rank}.")

    await log_action(
        ctx.guild,
        "Staff Promotion",
        f"Member: {member.mention}\nRank: {rank}\n"
        f"Approved by: {ctx.author.mention}"
    )


@bot.command(name="demote")
@commands.guild_only()
async def demote(ctx, member: discord.Member, *, rank: str):
    if not await supervisor_only(ctx):
        return

    await execute("""
        INSERT INTO staff_ranks (guild_id, user_id, rank, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET rank = excluded.rank, updated_by = excluded.updated_by
    """, (ctx.guild.id, member.id, rank, ctx.author.id))

    await ctx.send(f"{member.mention} has been changed to {rank}.")

    await log_action(
        ctx.guild,
        "Staff Rank Changed",
        f"Member: {member.mention}\nNew rank: {rank}\n"
        f"Changed by: {ctx.author.mention}"
    )


@bot.command(name="staffinfo")
@commands.guild_only()
async def staffinfo(ctx, member: discord.Member):
    if not await staff_only(ctx):
        return

    rank = await fetch_one("""
        SELECT rank FROM staff_ranks
        WHERE guild_id = ? AND user_id = ?
    """, (ctx.guild.id, member.id))

    warnings = await fetch_one("""
        SELECT COUNT(*) FROM staff_warnings
        WHERE guild_id = ? AND user_id = ?
    """, (ctx.guild.id, member.id))

    result = embed("Staff Information")
    result.add_field(name="Member", value=member.mention)
    result.add_field(
        name="Recorded Rank",
        value=rank[0] if rank else "Not assigned"
    )
    result.add_field(
        name="Staff Warnings",
        value=str(warnings[0] if warnings else 0)
    )

    await ctx.send(embed=result)


@bot.command(name="stafflist")
@commands.guild_only()
async def stafflist(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT user_id, rank FROM staff_ranks
        WHERE guild_id = ?
        ORDER BY rank
    """, (ctx.guild.id,))

    result = embed("Staff Directory")

    if not records:
        result.description = "No staff ranks have been recorded."
    else:
        for user_id, rank in records:
            result.add_field(
                name=rank,
                value=f"<@{user_id}>",
                inline=True
            )

    await ctx.send(embed=result)


@bot.command(name="staffwarn")
@commands.guild_only()
async def staffwarn(ctx, member: discord.Member, *, reason: str):
    if not await supervisor_only(ctx):
        return

    warning_id, _ = await execute("""
        INSERT INTO staff_warnings (
            guild_id, user_id, reason, moderator_id, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        member.id,
        reason,
        ctx.author.id,
        datetime.now(timezone.utc).isoformat()
    ))

    await ctx.send(f"Staff warning #{warning_id} issued to {member.mention}.")

    await log_action(
        ctx.guild,
        "Staff Warning",
        f"Member: {member.mention}\nReason: {reason}\n"
        f"Moderator: {ctx.author.mention}"
    )


@bot.command(name="staffwarnings")
@commands.guild_only()
async def staffwarnings(ctx, member: discord.Member):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT id, reason, moderator_id, created_at
        FROM staff_warnings
        WHERE guild_id = ? AND user_id = ?
        ORDER BY id DESC LIMIT 10
    """, (ctx.guild.id, member.id))

    result = embed(f"Staff Warnings: {member}")

    if not records:
        result.description = "No staff warnings found."
    else:
        for warning_id, reason, moderator_id, created_at in records:
            result.add_field(
                name=f"Warning #{warning_id}",
                value=f"{reason}\nIssued by: <@{moderator_id}>",
                inline=False
            )

    await ctx.send(embed=result)


@bot.command(name="removestaff")
@commands.guild_only()
async def removestaff(ctx, member: discord.Member):
    if not await supervisor_only(ctx):
        return

    await execute("""
        DELETE FROM staff_ranks
        WHERE guild_id = ? AND user_id = ?
    """, (ctx.guild.id, member.id))

    await ctx.send(f"Recorded staff rank removed for {member.mention}.")

    await log_action(
        ctx.guild,
        "Staff Rank Removed",
        f"Member: {member.mention}\nRemoved by: {ctx.author.mention}"
    )


# ==================================================
# BLACKLIST
# ==================================================

@bot.command(name="blacklist")
@commands.guild_only()
async def blacklist(ctx, member: discord.Member, *, reason: str):
    if not await supervisor_only(ctx):
        return

    await execute("""
        INSERT INTO blacklist (guild_id, user_id, reason, moderator_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET reason = excluded.reason,
                      moderator_id = excluded.moderator_id
    """, (ctx.guild.id, member.id, reason, ctx.author.id))

    await ctx.send(f"{member.mention} has been added to the Sentinel blacklist.")

    await log_action(
        ctx.guild,
        "Blacklist Updated",
        f"Member: {member.mention}\nReason: {reason}"
    )


@bot.command(name="unblacklist")
@commands.guild_only()
async def unblacklist(ctx, member: discord.Member):
    if not await supervisor_only(ctx):
        return

    _, count = await execute("""
        DELETE FROM blacklist WHERE guild_id = ? AND user_id = ?
    """, (ctx.guild.id, member.id))

    await ctx.send(
        "Member removed from the blacklist." if count
        else "Member was not on the blacklist."
    )


# ==================================================
# INFORMATION AND STATISTICS
# ==================================================

@bot.command(name="userinfo")
@commands.guild_only()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    result = embed("User Information")
    result.add_field(name="Username", value=str(member))
    result.add_field(name="User ID", value=str(member.id))
    result.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
    result.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown")

    await ctx.send(embed=result)


@bot.command(name="serverinfo")
@commands.guild_only()
async def serverinfo(ctx):
    guild = ctx.guild

    result = embed("Server Information")
    result.add_field(name="Server", value=guild.name)
    result.add_field(name="Server ID", value=str(guild.id))
    result.add_field(name="Members", value=str(guild.member_count))
    result.add_field(name="Roles", value=str(len(guild.roles)))
    result.add_field(name="Channels", value=str(len(guild.channels)))

    await ctx.send(embed=result)


@bot.command(name="stats")
@commands.guild_only()
async def stats(ctx):
    report_count = await fetch_one(
        "SELECT COUNT(*) FROM reports WHERE guild_id = ?",
        (ctx.guild.id,)
    )

    scammer_count = await fetch_one(
        "SELECT COUNT(*) FROM scammer_files WHERE guild_id = ?",
        (ctx.guild.id,)
    )

    twc_count = await fetch_one(
        "SELECT COUNT(*) FROM twc_records WHERE guild_id = ?",
        (ctx.guild.id,)
    )

    appeal_count = await fetch_one(
        "SELECT COUNT(*) FROM appeals WHERE guild_id = ?",
        (ctx.guild.id,)
    )

    result = embed("Sentinel Statistics")
    result.add_field(name="Reports", value=str(report_count[0]))
    result.add_field(name="Reviewed Scammer Files", value=str(scammer_count[0]))
    result.add_field(name="TWC Records", value=str(twc_count[0]))
    result.add_field(name="Appeals", value=str(appeal_count[0]))

    await ctx.send(embed=result)


@bot.command(name="staffstats")
@commands.guild_only()
async def staffstats(ctx):
    if not await staff_only(ctx):
        return

    records = await fetch_all("""
        SELECT assigned_to, COUNT(*)
        FROM reports
        WHERE guild_id = ? AND assigned_to IS NOT NULL
        GROUP BY assigned_to
        ORDER BY COUNT(*) DESC LIMIT 15
    """, (ctx.guild.id,))

    result = embed("Investigator Statistics")

    if not records:
        result.description = "No assigned cases have been recorded."
    else:
        for user_id, count in records:
            result.add_field(
                name=f"Investigator {user_id}",
                value=f"<@{user_id}> — {count} assigned cases",
                inline=False
            )

    await ctx.send(embed=result)


# ==================================================
# HELP
# ==================================================

@bot.command(name="help")
async def help_command(ctx):
    result = embed("Command Directory")

    result.add_field(
        name="Configuration",
        value="`;setstaff` `;setstaffsupervisor` `;setlog` "
              "`;setticketcategory` `;sentinelconfig`",
        inline=False
    )

    result.add_field(
        name="Reports",
        value="`;report` `;reports` `;reportinfo` `;accept` "
              "`;reject` `;claim` `;unclaim` `;assigncase` "
              "`;updatecase` `;resolve` `;reopen`",
        inline=False
    )

    result.add_field(
        name="Evidence and Notes",
        value="`;addevidence` `;evidence` `;removeevidence` "
              "`;addnote` `;history`",
        inline=False
    )

    result.add_field(
        name="Scammer Files and TWC",
        value="`;addscammer` `;scammer` `;scammerlist` "
              "`;editscammer` `;removescammer` `;addtwc` "
              "`;twc` `;twclist` `;edittwc` `;removetwc` "
              "`;reviewtwc`",
        inline=False
    )

    result.add_field(
        name="Appeals",
        value="`;appeal` `;appeals` `;reviewappeal` "
              "`;acceptappeal` `;rejectappeal`",
        inline=False
    )

    result.add_field(
        name="Tickets",
        value="`;ticketsetup` `;closeticket` `;adduser` `;removeuser`",
        inline=False
    )

    result.add_field(
        name="Staff",
        value="`;promote` `;demote` `;staffinfo` `;stafflist` "
              "`;staffwarn` `;staffwarnings` `;removestaff`",
        inline=False
    )

    result.add_field(
        name="Administration",
        value="`;blacklist` `;unblacklist` `;userinfo` "
              "`;serverinfo` `;stats` `;staffstats`",
        inline=False
    )

    await ctx.send(embed=result)


# ==================================================
# ERROR HANDLING
# ==================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing command argument. Use `;help`.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument. Check the command format.")
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have the required Discord permissions.")
        return

    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used inside a server.")
        return

    print(f"Command error: {error}")
    await ctx.send("An unexpected error occurred. Check the bot console.")


# ==================================================
# STARTUP
# ==================================================

@bot.event
async def on_ready():
    await setup_database()

    if not getattr(bot, "persistent_views_loaded", False):
        bot.add_view(ReportView())
        bot.add_view(TicketPanel())
        bot.add_view(TicketControls())
        bot.persistent_views_loaded = True

    print("--------------------------------")
    print("SENTINEL NETWORK ONLINE")
    print(f"Bot: {bot.user}")
    print(f"Prefix: {PREFIX}")
    print("--------------------------------")


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from your hosting environment variables."
    )

bot.run(TOKEN)

