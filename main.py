import os
import re
import discord
import aiosqlite
from discord.ext import commands
from discord import app_commands

# ============================================================
# DRACO SCAMMER FILES
# Red / Black investigation and case-management bot
# Prefix: ;
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = ";"
DATABASE = "draco_scammer_files.db"

RED = 0xE32636
DARK_RED = 0x8B0000
BLACK = 0x0B0B0B
WHITE = 0xFFFFFF

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ----------------------------- EMBEDS -----------------------------

def embed(title: str, description: str = "", *, color: int = RED) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Draco Scammer Files")
    return e


async def send_log(guild: discord.Guild, title: str, description: str):
    channel_id = await get_setting(guild.id, "log_channel")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await guild.fetch_channel(int(channel_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            return
    try:
        await channel.send(embed=embed(title, description))
    except discord.HTTPException:
        pass


# ----------------------------- DATABASE -----------------------------

async def db():
    return await aiosqlite.connect(DATABASE)


async def setup_database():
    async with await db() as con:
        await con.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (guild_id, key)
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            reporter_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            details TEXT NOT NULL,
            evidence TEXT DEFAULT '',
            status TEXT DEFAULT 'Pending',
            decision TEXT DEFAULT '',
            assigned_to INTEGER DEFAULT 0,
            claimed_by INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            added_by INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS scammer_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            report_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            finding TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS twc_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            report_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            finding TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            report_id INTEGER NOT NULL,
            appellant_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            decision TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS staff_ranks (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rank TEXT NOT NULL,
            updated_by INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS staff_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            opener_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Open'
        );
        """)
        await con.commit()


async def get_setting(guild_id: int, key: str):
    async with await db() as con:
        cur = await con.execute(
            "SELECT value FROM settings WHERE guild_id=? AND key=?",
            (guild_id, key)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(guild_id: int, key: str, value: str):
    async with await db() as con:
        await con.execute(
            "INSERT INTO settings(guild_id,key,value) VALUES(?,?,?) "
            "ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value",
            (guild_id, key, str(value))
        )
        await con.commit()


async def fetch_one(query: str, params=()):
    async with await db() as con:
        cur = await con.execute(query, params)
        return await cur.fetchone()


async def fetch_all(query: str, params=()):
    async with await db() as con:
        cur = await con.execute(query, params)
        return await cur.fetchall()


async def execute(query: str, params=()):
    async with await db() as con:
        cur = await con.execute(query, params)
        await con.commit()
        return cur.lastrowid


# ----------------------------- PERMISSIONS -----------------------------

async def configured_staff(member: discord.Member) -> bool:
    staff_id = await get_setting(member.guild.id, "staff_role")
    supervisor_id = await get_setting(member.guild.id, "supervisor_role")
    role_ids = {r.id for r in member.roles}
    return bool(
        member.guild_permissions.administrator
        or (staff_id and int(staff_id) in role_ids)
        or (supervisor_id and int(supervisor_id) in role_ids)
    )


async def supervisor(member: discord.Member) -> bool:
    role_id = await get_setting(member.guild.id, "supervisor_role")
    return bool(
        member.guild_permissions.administrator
        or (role_id and int(role_id) in {r.id for r in member.roles})
    )


def staff_only():
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member) or not await configured_staff(ctx.author):
            raise commands.CheckFailure("This command is for configured staff.")
        return True
    return commands.check(predicate)


def supervisor_only():
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member) or not await supervisor(ctx.author):
            raise commands.CheckFailure("This command is for supervisors.")
        return True
    return commands.check(predicate)


def admin_only():
    return commands.has_guild_permissions(administrator=True)


async def get_report(report_id: int, guild_id: int):
    return await fetch_one(
        "SELECT id,guild_id,reporter_id,subject,details,evidence,status,decision,"
        "assigned_to,claimed_by,created_at FROM reports WHERE id=? AND guild_id=?",
        (report_id, guild_id)
    )


# ----------------------------- EVENTS -----------------------------

@bot.event
async def on_ready():
    await setup_database()
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    print(f"Logged in as {bot.user} | Draco Scammer Files")
    print(f"Prefix: {PREFIX}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(embed=embed("Missing information", f"Usage: `{PREFIX}{ctx.command.qualified_name} {ctx.command.signature}`"))
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(embed=embed("Invalid input", "Check the command arguments and try again."))
    elif isinstance(error, commands.CheckFailure):
        await ctx.reply(embed=embed("Access denied", str(error) or "You do not have permission to use this command."))
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.reply(embed=embed("Server only", "This command must be used in a server."))
    else:
        print(f"Command error: {repr(error)}")
        await ctx.reply(embed=embed("Command error", "Something went wrong. Check the bot console for details."))


# ----------------------------- CONFIGURATION -----------------------------

@bot.command()
@admin_only()
@commands.guild_only()
async def setstaff(ctx, role: discord.Role):
    await set_setting(ctx.guild.id, "staff_role", role.id)
    await ctx.reply(embed=embed("Staff role updated", f"Configured staff role: {role.mention}"))
    await send_log(ctx.guild, "Configuration changed", f"{ctx.author.mention} set staff role to {role.mention}.")


@bot.command()
@admin_only()
@commands.guild_only()
async def setstaffsupervisor(ctx, role: discord.Role):
    await set_setting(ctx.guild.id, "supervisor_role", role.id)
    await ctx.reply(embed=embed("Supervisor role updated", f"Configured supervisor role: {role.mention}"))
    await send_log(ctx.guild, "Configuration changed", f"{ctx.author.mention} set supervisor role to {role.mention}.")


@bot.command()
@admin_only()
@commands.guild_only()
async def setlog(ctx, channel: discord.TextChannel):
    await set_setting(ctx.guild.id, "log_channel", channel.id)
    await ctx.reply(embed=embed("Log channel updated", f"Logs will be sent to {channel.mention}."))
    await send_log(ctx.guild, "Configuration changed", f"{ctx.author.mention} configured {channel.mention} as the log channel.")


@bot.command()
@admin_only()
@commands.guild_only()
async def setticketcategory(ctx, category: discord.CategoryChannel):
    await set_setting(ctx.guild.id, "ticket_category", category.id)
    await ctx.reply(embed=embed("Ticket category updated", f"New tickets will be created under **{category.name}**."))


@bot.command()
@admin_only()
@commands.guild_only()
async def sentinelconfig(ctx):
    staff = await get_setting(ctx.guild.id, "staff_role")
    sup = await get_setting(ctx.guild.id, "supervisor_role")
    log = await get_setting(ctx.guild.id, "log_channel")
    cat = await get_setting(ctx.guild.id, "ticket_category")
    e = embed("Draco Scammer Files | Configuration")
    e.add_field(name="Staff role", value=f"<@&{staff}>" if staff else "Not set", inline=False)
    e.add_field(name="Supervisor role", value=f"<@&{sup}>" if sup else "Not set", inline=False)
    e.add_field(name="Log channel", value=f"<#{log}>" if log else "Not set", inline=False)
    e.add_field(name="Ticket category", value=f"<#{cat}>" if cat else "Not set", inline=False)
    await ctx.reply(embed=e)


# ----------------------------- REPORTS -----------------------------

@bot.command()
@commands.guild_only()
async def report(ctx, *, details: str):
    if len(details) < 10:
        return await ctx.reply(embed=embed("Report too short", "Please provide enough information for staff to review."))
    if len(details) > 1800:
        return await ctx.reply(embed=embed("Report too long", "Keep the report under 1,800 characters."))
    report_id = await execute(
        "INSERT INTO reports(guild_id,reporter_id,subject,details) VALUES(?,?,?,?)",
        (ctx.guild.id, ctx.author.id, "Unspecified", details)
    )
    await ctx.reply(embed=embed("Report submitted", f"Your report has been saved. Reference: **#{report_id}**\nStaff will review it."))
    await send_log(ctx.guild, f"New report #{report_id}", f"Submitted by {ctx.author.mention}\n\n{details[:1500]}")


@bot.command()
@staff_only()
@commands.guild_only()
async def reports(ctx, status: str = "Pending"):
    rows = await fetch_all(
        "SELECT id,reporter_id,status,subject FROM reports WHERE guild_id=? AND status LIKE ? ORDER BY id DESC LIMIT 15",
        (ctx.guild.id, f"%{status}%")
    )
    e = embed(f"Reports | {status}")
    if not rows:
        e.description = "No matching reports found."
    else:
        e.description = "\n".join(
            f"**#{r[0]}** — {r[2]} — reporter <@{r[1]}>" for r in rows
        )
    await ctx.reply(embed=e)


@bot.command()
@commands.guild_only()
async def reportinfo(ctx, report_id: int):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "That report does not exist."))
    is_staff = isinstance(ctx.author, discord.Member) and await configured_staff(ctx.author)
    if not is_staff and ctx.author.id != row[2]:
        return await ctx.reply(embed=embed("Access denied", "You can only view your own report."))
    e = embed(f"Report #{row[0]}", row[4][:4000])
    e.add_field(name="Status", value=row[6], inline=True)
    e.add_field(name="Reporter", value=f"<@{row[2]}>", inline=True)
    if is_staff:
        e.add_field(name="Decision", value=row[7] or "Not set", inline=False)
        e.add_field(name="Assigned to", value=f"<@{row[8]}>" if row[8] else "Unassigned", inline=True)
        e.add_field(name="Claimed by", value=f"<@{row[9]}>" if row[9] else "Unclaimed", inline=True)
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def accept(ctx, report_id: int):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    await execute("UPDATE reports SET status='Accepted' WHERE id=? AND guild_id=?", (report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Report accepted", f"Report **#{report_id}** has been accepted."))
    await send_log(ctx.guild, f"Report #{report_id} accepted", f"By {ctx.author.mention}")


@bot.command()
@staff_only()
@commands.guild_only()
async def reject(ctx, report_id: int, *, reason: str):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    await execute("UPDATE reports SET status='Rejected',decision=? WHERE id=? AND guild_id=?", (reason[:1000], report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Report rejected", f"Report **#{report_id}** was rejected.\nReason: {reason[:1000]}"))
    await send_log(ctx.guild, f"Report #{report_id} rejected", f"By {ctx.author.mention}\nReason: {reason[:1000]}")


@bot.command()
@staff_only()
@commands.guild_only()
async def claim(ctx, report_id: int):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    if row[9] and row[9] != ctx.author.id:
        return await ctx.reply(embed=embed("Already claimed", f"This report is claimed by <@{row[9]}>."))
    await execute("UPDATE reports SET claimed_by=? WHERE id=? AND guild_id=?", (ctx.author.id, report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case claimed", f"You claimed report **#{report_id}**."))


@bot.command()
@staff_only()
@commands.guild_only()
async def unclaim(ctx, report_id: int):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    if row[9] not in (0, ctx.author.id) and not await supervisor(ctx.author):
        return await ctx.reply(embed=embed("Access denied", "Only the claimant or a supervisor can unclaim this report."))
    await execute("UPDATE reports SET claimed_by=0 WHERE id=? AND guild_id=?", (report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case unclaimed", f"Report **#{report_id}** is now unclaimed."))


@bot.command()
@staff_only()
@commands.guild_only()
async def assigncase(ctx, report_id: int, member: discord.Member):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    await execute("UPDATE reports SET assigned_to=? WHERE id=? AND guild_id=?", (member.id, report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case assigned", f"Report **#{report_id}** assigned to {member.mention}."))


@bot.command()
@staff_only()
@commands.guild_only()
async def updatecase(ctx, report_id: int, status: str, *, decision: str = ""):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    allowed = {"pending", "accepted", "rejected", "investigating", "resolved", "appealed", "on-hold"}
    if status.lower() not in allowed:
        return await ctx.reply(embed=embed("Invalid status", "Use: Pending, Accepted, Rejected, Investigating, Resolved, Appealed, On-hold."))
    await execute("UPDATE reports SET status=?,decision=? WHERE id=? AND guild_id=?", (status.title(), decision[:1000], report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case updated", f"Report **#{report_id}** status: **{status.title()}**."))


@bot.command()
@staff_only()
@commands.guild_only()
async def resolve(ctx, report_id: int, *, finding: str):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    await execute("UPDATE reports SET status='Resolved',decision=? WHERE id=? AND guild_id=?", (finding[:1000], report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case resolved", f"Report **#{report_id}** marked resolved.\nFinding: {finding[:1000]}"))
    await send_log(ctx.guild, f"Report #{report_id} resolved", f"By {ctx.author.mention}\nFinding: {finding[:1000]}")


@bot.command()
@staff_only()
@commands.guild_only()
async def reopen(ctx, report_id: int):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    await execute("UPDATE reports SET status='Investigating' WHERE id=? AND guild_id=?", (report_id, ctx.guild.id))
    await ctx.reply(embed=embed("Case reopened", f"Report **#{report_id}** is now under investigation."))


# ----------------------------- EVIDENCE AND NOTES -----------------------------

@bot.command()
@staff_only()
@commands.guild_only()
async def addevidence(ctx, report_id: int, *, content: str):
    if not await get_report(report_id, ctx.guild.id):
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    evidence_id = await execute(
        "INSERT INTO evidence(report_id,added_by,content) VALUES(?,?,?)",
        (report_id, ctx.author.id, content[:1800])
    )
    await ctx.reply(embed=embed("Evidence added", f"Evidence **#{evidence_id}** added to report **#{report_id}**."))
    await send_log(ctx.guild, f"Evidence added to report #{report_id}", f"Evidence ID: {evidence_id}\nAdded by: {ctx.author.mention}")


@bot.command()
@staff_only()
@commands.guild_only()
async def evidence(ctx, report_id: int):
    if not await get_report(report_id, ctx.guild.id):
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    rows = await fetch_all("SELECT id,added_by,content,created_at FROM evidence WHERE report_id=? ORDER BY id", (report_id,))
    e = embed(f"Evidence | Report #{report_id}")
    e.description = "\n\n".join(f"**Evidence #{r[0]}** by <@{r[1]}>\n{r[2][:700]}" for r in rows)[:4000] or "No evidence stored."
    await ctx.reply(embed=e)


@bot.command()
@supervisor_only()
@commands.guild_only()
async def removeevidence(ctx, evidence_id: int):
    row = await fetch_one(
        "SELECT evidence.id,evidence.report_id FROM evidence JOIN reports ON reports.id=evidence.report_id "
        "WHERE evidence.id=? AND reports.guild_id=?",
        (evidence_id, ctx.guild.id)
    )
    if not row:
        return await ctx.reply(embed=embed("Not found", "Evidence not found."))
    await execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
    await ctx.reply(embed=embed("Evidence removed", f"Evidence **#{evidence_id}** removed from report **#{row[1]}**."))


@bot.command()
@staff_only()
@commands.guild_only()
async def addnote(ctx, report_id: int, *, note: str):
    if not await get_report(report_id, ctx.guild.id):
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    note_id = await execute(
        "INSERT INTO notes(report_id,staff_id,note) VALUES(?,?,?)",
        (report_id, ctx.author.id, note[:1500])
    )
    await ctx.reply(embed=embed("Internal note added", f"Note **#{note_id}** added to report **#{report_id}**."))


@bot.command()
@staff_only()
@commands.guild_only()
async def history(ctx, report_id: int):
    if not await get_report(report_id, ctx.guild.id):
        return await ctx.reply(embed=embed("Not found", "Report not found."))
    notes = await fetch_all("SELECT staff_id,note,created_at FROM notes WHERE report_id=? ORDER BY id DESC LIMIT 8", (report_id,))
    evs = await fetch_all("SELECT id,added_by,created_at FROM evidence WHERE report_id=? ORDER BY id DESC LIMIT 8", (report_id,))
    e = embed(f"Investigation history | #{report_id}")
    e.add_field(name="Internal notes", value="\n".join(f"<@{n[0]}>: {n[1][:180]}" for n in notes)[:1000] or "None", inline=False)
    e.add_field(name="Evidence entries", value="\n".join(f"#{v[0]} by <@{v[1]}> — {v[2]}" for v in evs)[:1000] or "None", inline=False)
    await ctx.reply(embed=e)


# ----------------------------- SCAMMER FILES / TWC -----------------------------

async def add_record(ctx, table: str, report_id: int, identifier: str, finding: str):
    if not await get_report(report_id, ctx.guild.id):
        return await ctx.reply(embed=embed("Report not found", "A valid report from this server is required."))
    if len(identifier) > 200 or len(finding) > 1200:
        return await ctx.reply(embed=embed("Input too long", "Keep the identifier under 200 characters and finding under 1,200."))
    record_id = await execute(
        f"INSERT INTO {table}(guild_id,report_id,identifier,finding,created_by) VALUES(?,?,?,?,?)",
        (ctx.guild.id, report_id, identifier, finding, ctx.author.id)
    )
    await ctx.reply(embed=embed("Record created", f"Record **#{record_id}** added. It is stored in the server's private database."))
    await send_log(ctx.guild, f"New {('scammer file' if table == 'scammer_files' else 'TWC record')} #{record_id}",
                   f"Created by {ctx.author.mention}\nCase: #{report_id}\nIdentifier: {identifier}\nFinding: {finding[:800]}")


@bot.command()
@supervisor_only()
@commands.guild_only()
async def addscammer(ctx, report_id: int, identifier: str, *, finding: str):
    await add_record(ctx, "scammer_files", report_id, identifier, finding)


@bot.command()
@staff_only()
@commands.guild_only()
async def scammer(ctx, *, identifier: str):
    row = await fetch_one(
        "SELECT id,report_id,identifier,finding,created_at FROM scammer_files WHERE guild_id=? AND lower(identifier)=lower(?) ORDER BY id DESC LIMIT 1",
        (ctx.guild.id, identifier)
    )
    if not row:
        return await ctx.reply(embed=embed("No confirmed file found", "No matching record was found."))
    e = embed(f"Scammer file #{row[0]}", f"Identifier: **{row[2]}**\nFinding: {row[3][:2500]}")
    e.add_field(name="Linked case", value=f"#{row[1]}")
    e.add_field(name="Created", value=row[4])
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def scammerlist(ctx):
    rows = await fetch_all("SELECT id,identifier,report_id FROM scammer_files WHERE guild_id=? ORDER BY id DESC LIMIT 20", (ctx.guild.id,))
    e = embed("Scammer files")
    e.description = "\n".join(f"**#{r[0]}** — {r[1]} — case #{r[2]}" for r in rows) or "No files stored."
    await ctx.reply(embed=e)


@bot.command()
@supervisor_only()
@commands.guild_only()
async def editscammer(ctx, file_id: int, *, finding: str):
    row = await fetch_one("SELECT id FROM scammer_files WHERE id=? AND guild_id=?", (file_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "Scammer file not found."))
    await execute("UPDATE scammer_files SET finding=? WHERE id=? AND guild_id=?", (finding[:1200], file_id, ctx.guild.id))
    await ctx.reply(embed=embed("File updated", f"Scammer file **#{file_id}** updated."))


@bot.command()
@supervisor_only()
@commands.guild_only()
async def removescammer(ctx, file_id: int, *, reason: str):
    row = await fetch_one("SELECT identifier FROM scammer_files WHERE id=? AND guild_id=?", (file_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "Scammer file not found."))
    await execute("DELETE FROM scammer_files WHERE id=? AND guild_id=?", (file_id, ctx.guild.id))
    await ctx.reply(embed=embed("File removed", f"File **#{file_id}** removed.\nReason: {reason[:800]}"))
    await send_log(ctx.guild, f"Scammer file #{file_id} removed", f"By {ctx.author.mention}\nReason: {reason[:800]}")


@bot.command()
@supervisor_only()
@commands.guild_only()
async def addtwc(ctx, report_id: int, identifier: str, *, finding: str):
    await add_record(ctx, "twc_records", report_id, identifier, finding)


@bot.command()
@staff_only()
@commands.guild_only()
async def twc(ctx, *, identifier: str):
    row = await fetch_one(
        "SELECT id,report_id,identifier,finding,created_at FROM twc_records WHERE guild_id=? AND lower(identifier)=lower(?) ORDER BY id DESC LIMIT 1",
        (ctx.guild.id, identifier)
    )
    if not row:
        return await ctx.reply(embed=embed("No TWC record found", "No matching record was found."))
    e = embed(f"TWC record #{row[0]}", f"Identifier: **{row[2]}**\nFinding: {row[3][:2500]}")
    e.add_field(name="Linked case", value=f"#{row[1]}")
    e.add_field(name="Created", value=row[4])
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def twclist(ctx):
    rows = await fetch_all("SELECT id,identifier,report_id FROM twc_records WHERE guild_id=? ORDER BY id DESC LIMIT 20", (ctx.guild.id,))
    e = embed("TWC records")
    e.description = "\n".join(f"**#{r[0]}** — {r[1]} — case #{r[2]}" for r in rows) or "No records stored."
    await ctx.reply(embed=e)


@bot.command()
@supervisor_only()
@commands.guild_only()
async def edittwc(ctx, record_id: int, *, finding: str):
    row = await fetch_one("SELECT id FROM twc_records WHERE id=? AND guild_id=?", (record_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "TWC record not found."))
    await execute("UPDATE twc_records SET finding=? WHERE id=? AND guild_id=?", (finding[:1200], record_id, ctx.guild.id))
    await ctx.reply(embed=embed("TWC updated", f"TWC record **#{record_id}** updated."))


@bot.command()
@supervisor_only()
@commands.guild_only()
async def removetwc(ctx, record_id: int, *, reason: str):
    row = await fetch_one("SELECT id FROM twc_records WHERE id=? AND guild_id=?", (record_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "TWC record not found."))
    await execute("DELETE FROM twc_records WHERE id=? AND guild_id=?", (record_id, ctx.guild.id))
    await ctx.reply(embed=embed("TWC removed", f"Record **#{record_id}** removed.\nReason: {reason[:800]}"))
    await send_log(ctx.guild, f"TWC record #{record_id} removed", f"By {ctx.author.mention}\nReason: {reason[:800]}")


@bot.command()
@supervisor_only()
@commands.guild_only()
async def reviewtwc(ctx, record_id: int, *, finding: str):
    row = await fetch_one("SELECT id FROM twc_records WHERE id=? AND guild_id=?", (record_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "TWC record not found."))
    await execute("UPDATE twc_records SET finding=? WHERE id=? AND guild_id=?", (finding[:1200], record_id, ctx.guild.id))
    await ctx.reply(embed=embed("TWC reviewed", f"Record **#{record_id}** has been updated after review."))


# ----------------------------- APPEALS -----------------------------

@bot.command()
@commands.guild_only()
async def appeal(ctx, report_id: int, *, reason: str):
    row = await get_report(report_id, ctx.guild.id)
    if not row:
        return await ctx.reply(embed=embed("Not found", "That report does not exist."))
    appeal_id = await execute(
        "INSERT INTO appeals(guild_id,report_id,appellant_id,reason) VALUES(?,?,?,?)",
        (ctx.guild.id, report_id, ctx.author.id, reason[:1200])
    )
    await ctx.reply(embed=embed("Appeal submitted", f"Appeal **#{appeal_id}** for report **#{report_id}** submitted."))
    await send_log(ctx.guild, f"New appeal #{appeal_id}", f"Report: #{report_id}\nFrom: {ctx.author.mention}\n{reason[:800]}")


@bot.command()
@staff_only()
@commands.guild_only()
async def appeals(ctx):
    rows = await fetch_all("SELECT id,report_id,appellant_id,status FROM appeals WHERE guild_id=? ORDER BY id DESC LIMIT 20", (ctx.guild.id,))
    e = embed("Appeals")
    e.description = "\n".join(f"**#{r[0]}** — report #{r[1]} — <@{r[2]}> — {r[3]}" for r in rows) or "No appeals found."
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def reviewappeal(ctx, appeal_id: int, *, decision: str):
    row = await fetch_one("SELECT id FROM appeals WHERE id=? AND guild_id=?", (appeal_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "Appeal not found."))
    await execute("UPDATE appeals SET status='Reviewed',decision=? WHERE id=? AND guild_id=?", (decision[:1000], appeal_id, ctx.guild.id))
    await ctx.reply(embed=embed("Appeal reviewed", f"Appeal **#{appeal_id}** marked reviewed."))


@bot.command()
@supervisor_only()
@commands.guild_only()
async def acceptappeal(ctx, appeal_id: int, *, reason: str):
    row = await fetch_one("SELECT report_id FROM appeals WHERE id=? AND guild_id=?", (appeal_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "Appeal not found."))
    await execute("UPDATE appeals SET status='Accepted',decision=? WHERE id=? AND guild_id=?", (reason[:1000], appeal_id, ctx.guild.id))
    await execute("UPDATE reports SET status='Reopened' WHERE id=? AND guild_id=?", (row[0], ctx.guild.id))
    await ctx.reply(embed=embed("Appeal accepted", f"Appeal **#{appeal_id}** accepted. Report **#{row[0]}** reopened."))


@bot.command()
@supervisor_only()
@commands.guild_only()
async def rejectappeal(ctx, appeal_id: int, *, reason: str):
    row = await fetch_one("SELECT id FROM appeals WHERE id=? AND guild_id=?", (appeal_id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not found", "Appeal not found."))
    await execute("UPDATE appeals SET status='Rejected',decision=? WHERE id=? AND guild_id=?", (reason[:1000], appeal_id, ctx.guild.id))
    await ctx.reply(embed=embed("Appeal rejected", f"Appeal **#{appeal_id}** rejected.\nReason: {reason[:800]}"))


# ----------------------------- TICKETS -----------------------------

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a report ticket", style=discord.ButtonStyle.danger, custom_id="draco:open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
        existing = await fetch_one("SELECT channel_id FROM tickets WHERE guild_id=? AND opener_id=? AND status='Open'", (guild.id, interaction.user.id))
        if existing:
            channel = guild.get_channel(existing[0])
            if channel:
                return await interaction.response.send_message(f"You already have an open ticket: {channel.mention}", ephemeral=True)
        category_id = await get_setting(guild.id, "ticket_category")
        category = guild.get_channel(int(category_id)) if category_id else None
        staff_id = await get_setting(guild.id, "staff_role")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        if staff_id:
            role = guild.get_role(int(staff_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        safe_name = re.sub(r"[^a-z0-9-]", "-", interaction.user.name.lower())[:30].strip("-") or "user"
        try:
            channel = await guild.create_text_channel(
                name=f"report-{safe_name}",
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                topic=f"Draco report ticket opened by {interaction.user.id}"
            )
        except discord.Forbidden:
            return await interaction.response.send_message("The bot needs Manage Channels and permission to set channel overwrites.", ephemeral=True)
        await execute("INSERT INTO tickets(channel_id,guild_id,opener_id) VALUES(?,?,?)", (channel.id, guild.id, interaction.user.id))
        await channel.send(
            content=interaction.user.mention,
            embed=embed("Draco Scammer Files | Report ticket", "Please provide the details of your report. Do not post passwords, private addresses, or other sensitive personal information."),
            view=TicketControls()
        )
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)
        await send_log(guild, "Ticket opened", f"{interaction.user.mention} opened {channel.mention}.")


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close ticket", style=discord.ButtonStyle.secondary, custom_id="draco:close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await fetch_one("SELECT opener_id FROM tickets WHERE channel_id=? AND guild_id=? AND status='Open'", (interaction.channel_id, interaction.guild_id))
        if not row:
            return await interaction.response.send_message("This ticket is already closed or is not registered.", ephemeral=True)
        member = interaction.user
        allowed = member.id == row[0] or (isinstance(member, discord.Member) and await configured_staff(member))
        if not allowed:
            return await interaction.response.send_message("Only the ticket opener or configured staff can close this ticket.", ephemeral=True)
        await interaction.response.send_message("Ticket closing in a moment.", ephemeral=True)
        await execute("UPDATE tickets SET status='Closed' WHERE channel_id=?", (interaction.channel_id,))
        await send_log(interaction.guild, "Ticket closed", f"Ticket channel: <#{interaction.channel_id}>\nClosed by: {member.mention}")
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {member}")
        except discord.HTTPException:
            pass


@bot.command()
@admin_only()
@commands.guild_only()
async def ticketsetup(ctx):
    await ctx.send(embed=embed("Draco Scammer Files | Support", "Open a private ticket to submit information to the staff team."), view=TicketPanel())


@bot.command()
@commands.guild_only()
async def closeticket(ctx):
    row = await fetch_one("SELECT opener_id FROM tickets WHERE channel_id=? AND guild_id=? AND status='Open'", (ctx.channel.id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not a ticket", "This channel is not an open ticket."))
    if ctx.author.id != row[0] and not await configured_staff(ctx.author):
        return await ctx.reply(embed=embed("Access denied", "Only the opener or configured staff can close this ticket."))
    await execute("UPDATE tickets SET status='Closed' WHERE channel_id=?", (ctx.channel.id,))
    await ctx.reply(embed=embed("Ticket closed", "This channel will be deleted shortly."))
    await send_log(ctx.guild, "Ticket closed", f"Channel #{ctx.channel.name} closed by {ctx.author.mention}.")
    await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")


@bot.command()
@staff_only()
@commands.guild_only()
async def adduser(ctx, member: discord.Member):
    row = await fetch_one("SELECT opener_id FROM tickets WHERE channel_id=? AND guild_id=? AND status='Open'", (ctx.channel.id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not a ticket", "Use this command inside an open ticket."))
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    await ctx.reply(embed=embed("Member added", f"{member.mention} can now access this ticket."))


@bot.command()
@staff_only()
@commands.guild_only()
async def removeuser(ctx, member: discord.Member):
    row = await fetch_one("SELECT opener_id FROM tickets WHERE channel_id=? AND guild_id=? AND status='Open'", (ctx.channel.id, ctx.guild.id))
    if not row:
        return await ctx.reply(embed=embed("Not a ticket", "Use this command inside an open ticket."))
    if member.id == row[0]:
        return await ctx.reply(embed=embed("Not allowed", "You cannot remove the ticket opener."))
    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.reply(embed=embed("Member removed", f"{member.mention} no longer has ticket access."))


# ----------------------------- STAFF MANAGEMENT -----------------------------

@bot.command()
@supervisor_only()
@commands.guild_only()
async def promote(ctx, member: discord.Member, *, rank: str):
    await execute(
        "INSERT INTO staff_ranks(guild_id,user_id,rank,updated_by) VALUES(?,?,?,?) "
        "ON CONFLICT(guild_id,user_id) DO UPDATE SET rank=excluded.rank,updated_by=excluded.updated_by",
        (ctx.guild.id, member.id, rank[:80], ctx.author.id)
    )
    await ctx.reply(embed=embed("Staff rank updated", f"{member.mention} is now recorded as **{rank[:80]}**. This updates the bot's rank database only; it does not assign a Discord role."))
    await send_log(ctx.guild, "Staff rank updated", f"{member.mention} promoted/recorded as {rank[:80]} by {ctx.author.mention}.")


@bot.command()
@supervisor_only()
@commands.guild_only()
async def demote(ctx, member: discord.Member, *, rank: str):
    await execute(
        "INSERT INTO staff_ranks(guild_id,user_id,rank,updated_by) VALUES(?,?,?,?) "
        "ON CONFLICT(guild_id,user_id) DO UPDATE SET rank=excluded.rank,updated_by=excluded.updated_by",
        (ctx.guild.id, member.id, rank[:80], ctx.author.id)
    )
    await ctx.reply(embed=embed("Staff rank updated", f"{member.mention} is now recorded as **{rank[:80]}**. This updates the bot's rank database only; it does not change Discord roles."))


@bot.command()
@staff_only()
@commands.guild_only()
async def staffinfo(ctx, member: discord.Member):
    row = await fetch_one("SELECT rank,updated_by FROM staff_ranks WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
    e = embed(f"Staff information | {member}")
    e.add_field(name="Recorded rank", value=row[0] if row else "Not set", inline=False)
    e.add_field(name="Discord account", value=str(member.id), inline=False)
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def stafflist(ctx):
    rows = await fetch_all("SELECT user_id,rank FROM staff_ranks WHERE guild_id=? ORDER BY rank", (ctx.guild.id,))
    e = embed("Staff directory")
    e.description = "\n".join(f"<@{r[0]}> — **{r[1]}**" for r in rows) or "No staff ranks recorded."
    await ctx.reply(embed=e)


@bot.command()
@supervisor_only()
@commands.guild_only()
async def staffwarn(ctx, member: discord.Member, *, reason: str):
    warning_id = await execute(
        "INSERT INTO staff_warnings(guild_id,user_id,staff_id,reason) VALUES(?,?,?,?)",
        (ctx.guild.id, member.id, ctx.author.id, reason[:1000])
    )
    await ctx.reply(embed=embed("Staff warning recorded", f"Warning **#{warning_id}** recorded for {member.mention}.\nReason: {reason[:800]}"))
    await send_log(ctx.guild, "Staff warning issued", f"Member: {member.mention}\nIssued by: {ctx.author.mention}\nReason: {reason[:800]}")


@bot.command()
@staff_only()
@commands.guild_only()
async def staffwarnings(ctx, member: discord.Member):
    rows = await fetch_all("SELECT id,reason,staff_id,created_at FROM staff_warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10", (ctx.guild.id, member.id))
    e = embed(f"Staff warnings | {member}")
    e.description = "\n".join(f"**#{r[0]}** — {r[1][:250]} (by <@{r[2]}>)" for r in rows) or "No warnings recorded."
    await ctx.reply(embed=e)


@bot.command()
@supervisor_only()
@commands.guild_only()
async def removestaff(ctx, member: discord.Member):
    await execute("DELETE FROM staff_ranks WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
    await ctx.reply(embed=embed("Staff record removed", f"Removed the bot's staff-rank record for {member.mention}. Discord roles are unchanged."))


# ----------------------------- BLACKLIST -----------------------------

@bot.command()
@supervisor_only()
@commands.guild_only()
async def blacklist(ctx, member: discord.Member, *, reason: str):
    await execute(
        "INSERT INTO blacklist(guild_id,user_id,reason,added_by) VALUES(?,?,?,?) "
        "ON CONFLICT(guild_id,user_id) DO UPDATE SET reason=excluded.reason,added_by=excluded.added_by",
        (ctx.guild.id, member.id, reason[:1000], ctx.author.id)
    )
    await ctx.reply(embed=embed("Internal blacklist updated", f"{member.mention} was added to the internal blacklist.\nReason: {reason[:800]}\n\nThis does not ban the member from Discord."))


@bot.command()
@supervisor_only()
@commands.guild_only()
async def unblacklist(ctx, member: discord.Member):
    await execute("DELETE FROM blacklist WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
    await ctx.reply(embed=embed("Blacklist updated", f"{member.mention} was removed from the internal blacklist."))


# ----------------------------- INFORMATION / STATS -----------------------------

@bot.command()
@staff_only()
@commands.guild_only()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    e = embed(f"User information | {member}")
    e.add_field(name="User ID", value=str(member.id), inline=False)
    e.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "F") if member.joined_at else "Unknown", inline=False)
    e.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "F"), inline=False)
    e.add_field(name="Top role", value=member.top_role.mention, inline=False)
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def serverinfo(ctx):
    g = ctx.guild
    e = embed(f"Server information | {g.name}")
    e.add_field(name="Server ID", value=str(g.id), inline=False)
    e.add_field(name="Members", value=str(g.member_count), inline=True)
    e.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    e.add_field(name="Channels", value=str(len(g.channels)), inline=True)
    e.add_field(name="Created", value=discord.utils.format_dt(g.created_at, "F"), inline=False)
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def stats(ctx):
    reports_count = await fetch_one("SELECT COUNT(*) FROM reports WHERE guild_id=?", (ctx.guild.id,))
    pending = await fetch_one("SELECT COUNT(*) FROM reports WHERE guild_id=? AND status='Pending'", (ctx.guild.id,))
    scammers = await fetch_one("SELECT COUNT(*) FROM scammer_files WHERE guild_id=?", (ctx.guild.id,))
    twcs = await fetch_one("SELECT COUNT(*) FROM twc_records WHERE guild_id=?", (ctx.guild.id,))
    appeals_count = await fetch_one("SELECT COUNT(*) FROM appeals WHERE guild_id=?", (ctx.guild.id,))
    e = embed("Draco Scammer Files | Statistics")
    e.add_field(name="Total reports", value=str(reports_count[0]), inline=True)
    e.add_field(name="Pending reports", value=str(pending[0]), inline=True)
    e.add_field(name="Scammer files", value=str(scammers[0]), inline=True)
    e.add_field(name="TWC records", value=str(twcs[0]), inline=True)
    e.add_field(name="Appeals", value=str(appeals_count[0]), inline=True)
    await ctx.reply(embed=e)


@bot.command()
@staff_only()
@commands.guild_only()
async def staffstats(ctx):
    rows = await fetch_all(
        "SELECT assigned_to,COUNT(*) FROM reports WHERE guild_id=? AND assigned_to != 0 GROUP BY assigned_to ORDER BY COUNT(*) DESC LIMIT 10",
        (ctx.guild.id,)
    )
    e = embed("Staff case statistics")
    e.description = "\n".join(f"<@{r[0]}> — **{r[1]}** assigned reports" for r in rows) or "No assigned reports yet."
    await ctx.reply(embed=e)


@bot.command()
async def help(ctx):
    e = embed("Draco Scammer Files | Command list", "Prefix: `;`\nUse `;help` to view this command list.")
    e.add_field(name="Configuration", value="`;setstaff @Role`\n`;setstaffsupervisor @Role`\n`;setlog #channel`\n`;setticketcategory CATEGORY`\n`;sentinelconfig`", inline=False)
    e.add_field(name="Reports", value="`;report DETAILS`\n`;reports [STATUS]`\n`;reportinfo ID`\n`;accept ID`\n`;reject ID REASON`\n`;claim ID`\n`;unclaim ID`\n`;assigncase ID @Member`\n`;updatecase ID STATUS DECISION`\n`;resolve ID FINDING`\n`;reopen ID`", inline=False)
    e.add_field(name="Evidence and notes", value="`;addevidence ID TEXT`\n`;evidence ID`\n`;removeevidence ID`\n`;addnote ID TEXT`\n`;history ID`", inline=False)
    e.add_field(name="Scammer files and TWC", value="`;addscammer ID IDENTIFIER FINDING`\n`;scammer IDENTIFIER`\n`;scammerlist`\n`;editscammer ID FINDING`\n`;removescammer ID REASON`\n`;addtwc ID IDENTIFIER FINDING`\n`;twc IDENTIFIER`\n`;twclist`\n`;edittwc ID FINDING`\n`;removetwc ID REASON`\n`;reviewtwc ID FINDING`", inline=False)
    e.add_field(name="Appeals and tickets", value="`;appeal ID REASON`\n`;appeals`\n`;reviewappeal ID DECISION`\n`;acceptappeal ID REASON`\n`;rejectappeal ID REASON`\n`;ticketsetup`\n`;closeticket`\n`;adduser @Member`\n`;removeuser @Member`", inline=False)
    e.add_field(name="Staff and records", value="`;promote @Member RANK`\n`;demote @Member RANK`\n`;staffinfo @Member`\n`;stafflist`\n`;staffwarn @Member REASON`\n`;staffwarnings @Member`\n`;removestaff @Member`\n`;blacklist @Member REASON`\n`;unblacklist @Member`", inline=False)
    e.add_field(name="Information", value="`;userinfo [@Member]`\n`;serverinfo`\n`;stats`\n`;staffstats`", inline=False)
    await ctx.reply(embed=e)


# ----------------------------- STARTUP -----------------------------

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Add your bot token as an environment variable named DISCORD_TOKEN."
    )

bot.run(TOKEN)
