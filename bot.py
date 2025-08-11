from pathlib import Path
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import random
import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ========== DATA STORAGE (In-Memory) ==========
# In production, consider using a database
club_data = {
    'events': {},
    'announcements': {},
    'attendance': {},
    'club_roles': {},
    'member_clubs': {}  # Track which clubs each member belongs to
}

# Campus clubs configuration
CAMPUS_CLUBS = {
    'debate': {'name': 'Debate Club', 'emoji': '🎤', 'color': 0xff6b6b},
    'drama': {'name': 'Drama Club', 'emoji': '🎭', 'color': 0x4ecdc4},
    'music': {'name': 'Music Club', 'emoji': '🎵', 'color': 0x45b7d1},
    'art': {'name': 'Art Club', 'emoji': '🎨', 'color': 0x96ceb4},
    'science': {'name': 'Science Club', 'emoji': '🔬', 'color': 0xfeca57},
    'sports': {'name': 'Sports Club', 'emoji': '⚽', 'color': 0xff9ff3},
    'literature': {'name': 'Literature Club', 'emoji': '📚', 'color': 0x54a0ff}
}

# ========== UTILITY FUNCTIONS ==========

def save_data():
    """Save bot data to file (simulate database)"""
    try:
        with open('bot_data.json', 'w') as f:
            json.dump(club_data, f, default=str, indent=2)
    except Exception as e:
        logging.error(f"Error saving data: {e}")

def load_data():
    """Load bot data from file"""
    global club_data
    try:
        if os.path.exists('bot_data.json'):
            with open('bot_data.json', 'r') as f:
                club_data = json.load(f)
    except Exception as e:
        logging.error(f"Error loading data: {e}")

def get_club_role(guild, club_key):
    """Get or create club role"""
    club_info = CAMPUS_CLUBS.get(club_key)
    if not club_info:
        return None
    
    role_name = f"{club_info['name']} Member"
    role = discord.utils.get(guild.roles, name=role_name)
    return role

# ========== EVENTS ==========

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    load_data()
    check_reminders.start()  # Start reminder task

@bot.event
async def on_member_join(member):
    # Create welcome embed for new members
    embed = discord.Embed(
        title="🎉 Welcome to Infant Jesus School COCOSA Discord!",
        description=f"Hello {member.mention}! Welcome to our campus club community.",
        color=0x00ff00
    )
    embed.add_field(
        name="Getting Started",
        value="• Use `!clubs` to see available clubs\n• Use `!join <club>` to join a club\n• Use `!help` for all commands",
        inline=False
    )
    embed.add_field(
        name="Available Clubs",
        value="\n".join([f"{info['emoji']} {info['name']}" for info in CAMPUS_CLUBS.values()]),
        inline=False
    )
    
    channel = discord.utils.get(member.guild.text_channels, name="general")
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="general")
    if channel:
        await channel.send(f"👋 {member.name} has left the server. Farewell!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument. Please check your command usage with `!help`.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Try `!help` to see available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        logging.error(f"Command error: {error}")

# ========== BASIC COMMANDS ==========

@bot.command(name="hello", help="Say hello to the bot")
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}! 👋 I'm your Campus Club Assistant Bot!")

@bot.command(name="ping", help="Check bot latency")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: {latency}ms")

# ========== CLUB MANAGEMENT COMMANDS ==========

@bot.command(name="clubs", help="List all available campus clubs")
async def clubs(ctx):
    embed = discord.Embed(
        title="🏫 Infant Jesus School Campus Clubs",
        description="Here are all the available clubs you can join:",
        color=0x3498db
    )
    
    for key, info in CAMPUS_CLUBS.items():
        member_count = len([m for m in ctx.guild.members if get_club_role(ctx.guild, key) in m.roles]) if get_club_role(ctx.guild, key) else 0
        embed.add_field(
            name=f"{info['emoji']} {info['name']}",
            value=f"Members: {member_count}\nJoin with: `!join {key}`",
            inline=True
        )
    
    embed.set_footer(text="Use !join <club_name> to join a club!")
    await ctx.send(embed=embed)

@bot.command(name="join", help="Join a campus club. Usage: !join <club_name>")
async def join_club(ctx, club_key: str = None):
    if not club_key:
        await ctx.send("❌ Please specify a club to join. Use `!clubs` to see available clubs.")
        return
    
    club_key = club_key.lower()
    if club_key not in CAMPUS_CLUBS:
        await ctx.send(f"❌ Club '{club_key}' not found. Use `!clubs` to see available clubs.")
        return
    
    club_info = CAMPUS_CLUBS[club_key]
    role_name = f"{club_info['name']} Member"
    
    # Get or create role
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        role = await ctx.guild.create_role(
            name=role_name,
            color=club_info['color'],
            mentionable=True
        )
    
    if role in ctx.author.roles:
        await ctx.send(f"📋 You're already a member of {club_info['name']}!")
        return
    
    await ctx.author.add_roles(role)
    
    # Track membership
    user_id = str(ctx.author.id)
    if user_id not in club_data['member_clubs']:
        club_data['member_clubs'][user_id] = []
    if club_key not in club_data['member_clubs'][user_id]:
        club_data['member_clubs'][user_id].append(club_key)
    
    save_data()
    
    embed = discord.Embed(
        title=f"🎉 Welcome to {club_info['name']}!",
        description=f"{ctx.author.mention} has successfully joined {club_info['name']}!",
        color=club_info['color']
    )
    await ctx.send(embed=embed)

@bot.command(name="leave", help="Leave a campus club. Usage: !leave <club_name>")
async def leave_club(ctx, club_key: str = None):
    if not club_key:
        await ctx.send("❌ Please specify a club to leave. Use `!myclubs` to see your clubs.")
        return
    
    club_key = club_key.lower()
    if club_key not in CAMPUS_CLUBS:
        await ctx.send(f"❌ Club '{club_key}' not found.")
        return
    
    club_info = CAMPUS_CLUBS[club_key]
    role = get_club_role(ctx.guild, club_key)
    
    if not role or role not in ctx.author.roles:
        await ctx.send(f"❌ You're not a member of {club_info['name']}.")
        return
    
    await ctx.author.remove_roles(role)
    
    # Update tracking
    user_id = str(ctx.author.id)
    if user_id in club_data['member_clubs'] and club_key in club_data['member_clubs'][user_id]:
        club_data['member_clubs'][user_id].remove(club_key)
    
    save_data()
    
    await ctx.send(f"👋 You have left {club_info['name']}.")

@bot.command(name="myclubs", help="Show your club memberships")
async def my_clubs(ctx):
    user_roles = [role.name for role in ctx.author.roles]
    member_clubs = []
    
    for key, info in CAMPUS_CLUBS.items():
        role_name = f"{info['name']} Member"
        if role_name in user_roles:
            member_clubs.append(f"{info['emoji']} {info['name']}")
    
    if not member_clubs:
        await ctx.send("📝 You're not a member of any clubs yet. Use `!clubs` to see available clubs!")
        return
    
    embed = discord.Embed(
        title=f"📋 {ctx.author.display_name}'s Club Memberships",
        description="\n".join(member_clubs),
        color=0x9b59b6
    )
    await ctx.send(embed=embed)

# ========== EVENT MANAGEMENT ==========

@bot.command(name="event", help="Create a club event. Usage: !event <club> \"<title>\" \"<description>\" <date> <time>")
@commands.has_any_role("Club Moderator", "COCOSA Officer", "Administrator")
async def create_event(ctx, club_key: str = None, title: str = None, description: str = None, date: str = None, time: str = None):
    if not all([club_key, title, description, date, time]):
        await ctx.send("❌ Usage: `!event <club> \"<title>\" \"<description>\" <YYYY-MM-DD> <HH:MM>`")
        return
    
    club_key = club_key.lower()
    if club_key not in CAMPUS_CLUBS:
        await ctx.send(f"❌ Club '{club_key}' not found.")
        return
    
    try:
        event_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        await ctx.send("❌ Invalid date/time format. Use YYYY-MM-DD HH:MM")
        return
    
    # Store event
    event_id = f"{club_key}_{len(club_data['events'])}"
    club_data['events'][event_id] = {
        'club': club_key,
        'title': title,
        'description': description,
        'datetime': event_datetime.isoformat(),
        'creator': str(ctx.author.id),
        'attendees': []
    }
    
    save_data()
    
    club_info = CAMPUS_CLUBS[club_key]
    embed = discord.Embed(
        title=f"📅 New {club_info['name']} Event",
        color=club_info['color']
    )
    embed.add_field(name="Event", value=title, inline=False)
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="Date & Time", value=event_datetime.strftime("%B %d, %Y at %I:%M %p"), inline=False)
    embed.add_field(name="RSVP", value="React with ✅ to attend!", inline=False)
    embed.set_footer(text=f"Event ID: {event_id}")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    
    # Mention club members
    role = get_club_role(ctx.guild, club_key)
    if role:
        await ctx.send(f"📢 {role.mention} - New event announced!")

@bot.command(name="events", help="List upcoming events for a club or all clubs")
async def list_events(ctx, club_key: str = None):
    current_time = datetime.now()
    upcoming_events = []
    
    for event_id, event in club_data['events'].items():
        event_time = datetime.fromisoformat(event['datetime'])
        if event_time > current_time:
            if club_key is None or event['club'] == club_key.lower():
                upcoming_events.append((event_id, event, event_time))
    
    if not upcoming_events:
        club_name = CAMPUS_CLUBS.get(club_key.lower(), {}).get('name', 'any club') if club_key else 'any club'
        await ctx.send(f"📅 No upcoming events for {club_name}.")
        return
    
    # Sort by date
    upcoming_events.sort(key=lambda x: x[2])
    
    embed = discord.Embed(
        title="📅 Upcoming Events",
        color=0xe74c3c
    )
    
    for event_id, event, event_time in upcoming_events[:10]:  # Limit to 10 events
        club_info = CAMPUS_CLUBS[event['club']]
        embed.add_field(
            name=f"{club_info['emoji']} {event['title']}",
            value=f"**Club:** {club_info['name']}\n**When:** {event_time.strftime('%B %d, %Y at %I:%M %p')}\n**Attendees:** {len(event['attendees'])}",
            inline=False
        )
    
    await ctx.send(embed=embed)

# ========== ANNOUNCEMENT SYSTEM ==========

@bot.command(name="announce", help="Make a club announcement via DM. Usage: !announce <club> \"<message>\"")
@commands.has_any_role("Club Moderator", "COCOSA Officer", "Administrator")
async def announce_dm(ctx, club_key: str = None, *, message: str = None):
    if not club_key or not message:
        await ctx.send("❌ Usage: `!announce <club> \"<your announcement>\"`")
        return
    
    club_key = club_key.lower()
    if club_key not in CAMPUS_CLUBS:
        await ctx.send(f"❌ Club '{club_key}' not found.")
        return
    
    club_info = CAMPUS_CLUBS[club_key]
    role = get_club_role(ctx.guild, club_key)
    if not role:
        await ctx.send(f"❌ Role for {club_info['name']} not found.")
        return
    
    embed = discord.Embed(
        title=f"📢 {club_info['name']} Announcement",
        description=message,
        color=club_info['color'],
        timestamp=datetime.now()
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    
    # Send a DM to each member with the role
    success_count = 0
    fail_count = 0
    
    for member in role.members:
        try:
            await member.send(embed=embed)
            success_count += 1
            await asyncio.sleep(1)  # small delay to avoid hitting rate limits
        except Exception:
            fail_count += 1
    
    await ctx.send(f"✅ Announcement sent via DM to {success_count} members. Failed to send to {fail_count} members.")

# ========== ATTENDANCE TRACKING ==========

@bot.command(name="attendance", help="Start attendance tracking for a club meeting")
@commands.has_any_role("Club Moderator", "COCOSA Officer", "Administrator")
async def start_attendance(ctx, club_key: str = None, duration: int = 5):
    if not club_key:
        await ctx.send("❌ Usage: `!attendance <club> [duration_in_minutes]`")
        return
    
    club_key = club_key.lower()
    if club_key not in CAMPUS_CLUBS:
        await ctx.send(f"❌ Club '{club_key}' not found.")
        return
    
    club_info = CAMPUS_CLUBS[club_key]
    session_id = f"{club_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    club_data['attendance'][session_id] = {
        'club': club_key,
        'start_time': datetime.now().isoformat(),
        'duration': duration,
        'present': []
    }
    
    save_data()
    
    embed = discord.Embed(
        title=f"📝 {club_info['name']} Attendance",
        description=f"Attendance tracking has started!\nDuration: {duration} minutes\n\nReact with ✅ to mark yourself present!",
        color=club_info['color']
    )
    embed.set_footer(text=f"Session ID: {session_id}")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    
    role = get_club_role(ctx.guild, club_key)
    if role:
        await ctx.send(f"📢 {role.mention} - Attendance is being taken!")
    
    # Auto-close attendance after duration
    await asyncio.sleep(duration * 60)
    
    try:
        updated_embed = discord.Embed(
            title=f"📝 {club_info['name']} Attendance - CLOSED",
            description=f"Attendance tracking has ended.\nTotal present: {len(club_data['attendance'][session_id]['present'])}",
            color=0x95a5a6
        )
        await message.edit(embed=updated_embed)
    except:
        pass

# ========== REACTION HANDLERS ==========

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
    # Handle event RSVP
    if reaction.emoji == "✅" and reaction.message.embeds:
        embed = reaction.message.embeds[0]
        if "Event ID:" in embed.footer.text:
            event_id = embed.footer.text.split(": ")[1]
            if event_id in club_data['events']:
                user_id = str(user.id)
                if user_id not in club_data['events'][event_id]['attendees']:
                    club_data['events'][event_id]['attendees'].append(user_id)
                    save_data()
        
        # Handle attendance
        elif "Session ID:" in embed.footer.text:
            session_id = embed.footer.text.split(": ")[1]
            if session_id in club_data['attendance']:
                user_id = str(user.id)
                if user_id not in club_data['attendance'][session_id]['present']:
                    club_data['attendance'][session_id]['present'].append(user_id)
                    save_data()

# ========== REMINDER SYSTEM ==========

@tasks.loop(minutes=30)
async def check_reminders():
    """Check for upcoming events and send reminders"""
    current_time = datetime.now()
    reminder_time = current_time + timedelta(hours=1)  # 1 hour before event
    
    for event_id, event in club_data['events'].items():
        event_time = datetime.fromisoformat(event['datetime'])
        
        # Send reminder 1 hour before event
        if current_time < event_time <= reminder_time:
            for guild in bot.guilds:
                club_key = event['club']
                role = get_club_role(guild, club_key)
                if role:
                    channel = discord.utils.get(guild.text_channels, name="general")
                    if channel:
                        club_info = CAMPUS_CLUBS[club_key]
                        embed = discord.Embed(
                            title="⏰ Event Reminder",
                            description=f"**{event['title']}** starts in 1 hour!",
                            color=club_info['color']
                        )
                        await channel.send(f"{role.mention}", embed=embed)

# ========== HELP COMMAND ==========

@bot.command(name="help", help="Show all available commands")
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Campus Club Bot Commands",
        description="Here are all the available commands:",
        color=0x3498db
    )
    
    # Club commands
    club_commands = [
        ("!clubs", "List all available campus clubs"),
        ("!join <club>", "Join a campus club"),
        ("!leave <club>", "Leave a campus club"),
        ("!myclubs", "Show your club memberships")
    ]
    
    embed.add_field(
        name="🏫 Club Management",
        value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in club_commands]),
        inline=False
    )
    
    # Event commands
    event_commands = [
        ("!event <club> \"title\" \"desc\" YYYY-MM-DD HH:MM", "Create an event (Moderators only)"),
        ("!events [club]", "List upcoming events"),
        ("!announce <club> \"message\"", "Make announcement (Moderators only)"),
        ("!attendance <club> [minutes]", "Start attendance (Moderators only)")
    ]
    
    embed.add_field(
        name="📅 Events & Announcements",
        value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in event_commands]),
        inline=False
    )
    
    # Basic commands
    basic_commands = [
        ("!hello", "Greet the bot"),
        ("!ping", "Check bot latency"),
        ("!roll NdN", "Roll dice (e.g., !roll 2d6)")
    ]
    
    embed.add_field(
        name="🎮 Basic Commands",
        value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in basic_commands]),
        inline=False
    )
    
    embed.set_footer(text="React with ✅ on events to RSVP • React with ✅ on attendance to mark present")
    await ctx.send(embed=embed)

# ========== DICE ROLL (from original) ==========

@bot.command(name="roll", help="Roll dice in NdN format, e.g., !roll 2d6")
async def roll(ctx, dice: str = "1d6"):
    try:
        rolls, limit = map(int, dice.lower().split('d'))
        if rolls > 20:
            await ctx.send("❌ I can't roll more than 20 dice at once!")
            return
        results = [random.randint(1, limit) for _ in range(rolls)]
        await ctx.send(f"🎲 {ctx.author.mention} rolled: {', '.join(map(str, results))} (Total: {sum(results)})")
    except Exception:
        await ctx.send("❌ Format has to be NdN! Example: !roll 2d6")

# ========== MODERATION (from original) ==========

@bot.command(name="kick", help="Kick a member. Usage: !kick @user [reason]")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member} was kicked. Reason: {reason if reason else 'No reason provided.'}")
        logging.info(f"{ctx.author} kicked {member} from {ctx.guild} for: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to kick {member}: {e}")

@bot.command(name="ban", help="Ban a member. Usage: !ban @user [reason]")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member} was banned. Reason: {reason if reason else 'No reason provided.'}")
        logging.info(f"{ctx.author} banned {member} from {ctx.guild} for: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to ban {member}: {e}")

# ========== Run Bot ==========

if __name__ == "__main__":
    bot.run(TOKEN)