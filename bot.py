import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv
import random

# For Koyeb hosting - keeps bot alive
from threading import Thread
from fastapi import FastAPI
import uvicorn

load_dotenv()

# ==================== WEB SERVER FOR KOYEB ====================
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "GTA Heist Bot is Online! 🎮", "status": "running"}

def run_web_server():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def start_web_server():
    t = Thread(target=run_web_server)
    t.start()
# ==============================================================

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class GTAHeistBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced commands for {self.user}")

bot = GTAHeistBot()

# Configuration - UPDATE THIS WITH YOUR HEIST ROLE ID!
HEIST_ROLE_ID = 1467926741388361860  # You'll update this later
DATA_FILE = 'credits.json'

# Premium colors
COLORS = {
    'primary': 0x3498db,
    'success': 0x2ecc71,
    'warning': 0xf1c40f,
    'danger': 0xe74c3c,
    'gold': 0xf1c40f
}

# Load/Save functions
def load_credits():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_credits(credits):
    with open(DATA_FILE, 'w') as f:
        json.dump(credits, f, indent=4)

credits_data = load_credits()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="GTA Heists | /help"
        )
    )
    
    daily_credits.start()
    start_web_server()
    print("🌐 Web server started on port 8080")

# ==================== TASKS ====================
@tasks.loop(hours=24)
async def daily_credits():
    print(f"💰 Running daily credit task at {datetime.now()}")
    
    for guild in bot.guilds:
        heist_role = guild.get_role(HEIST_ROLE_ID)
        if not heist_role:
            continue
        
        for member in heist_role.members:
            user_id = str(member.id)
            
            if user_id not in credits_data:
                credits_data[user_id] = {"balance": 0, "last_daily": None}
            
            credits_data[user_id]["balance"] += 5
            credits_data[user_id]["last_daily"] = datetime.now().isoformat()
    
    save_credits(credits_data)

@daily_credits.before_loop
async def before_daily_credits():
    await bot.wait_until_ready()
    now = datetime.now()
    target = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now > target:
        target += timedelta(days=1)
    await asyncio.sleep((target - now).total_seconds())

# ==================== USER COMMANDS ====================
@bot.tree.command(name="balance", description="💰 Check your heist credit balance")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_id = str(target.id)
    
    balance = credits_data.get(user_id, {}).get("balance", 0)
    
    embed = discord.Embed(
        title="💰 Heist Credit Balance",
        color=COLORS['primary'],
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Member", value=target.mention, inline=True)
    embed.add_field(name="Balance", value=f"**{balance}** credits", inline=True)
    
    if balance > 0:
        bars = min(int(balance / 10) + 1, 10)
        progress = "█" * bars + "░" * (10 - bars)
        embed.add_field(name="Progress", value=f"`{progress}`", inline=False)
    
    embed.set_footer(text="1 credit = 1 heist participation", icon_url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="🏆 View the top credit holders")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(
        credits_data.items(), 
        key=lambda x: x[1]["balance"], 
        reverse=True
    )[:10]
    
    embed = discord.Embed(
        title="🏆 Heist Credit Leaderboard",
        description="Top credit holders in the server",
        color=COLORS['gold'],
        timestamp=datetime.now()
    )
    
    if not sorted_users:
        embed.description = "No credits have been distributed yet!"
    else:
        leaderboard_text = ""
        for i, (user_id, data) in enumerate(sorted_users, 1):
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id[:4]}"
            
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = "📊"
            
            leaderboard_text += f"{medal} **{i}.** {name}: **{data['balance']}** credits\n"
        
        embed.description = leaderboard_text
    
    embed.set_footer(text="Heist Crew Rankings")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="📅 Claim your daily bonus credits")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    if user_id not in credits_data:
        credits_data[user_id] = {"balance": 0, "last_daily_claim": None}
    
    last_claim = credits_data[user_id].get("last_daily_claim")
    
    if last_claim:
        last_claim_date = datetime.fromisoformat(last_claim)
        if datetime.now() - last_claim_date < timedelta(hours=24):
            remaining = timedelta(hours=24) - (datetime.now() - last_claim_date)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            
            embed = discord.Embed(
                title="⏳ Daily Bonus",
                description=f"You already claimed your daily bonus!",
                color=COLORS['warning'],
                timestamp=datetime.now()
            )
            embed.add_field(name="Time Remaining", value=f"**{hours}h {minutes}m** until next claim", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    bonus = random.randint(3, 8)
    credits_data[user_id]["balance"] += bonus
    credits_data[user_id]["last_daily_claim"] = datetime.now().isoformat()
    save_credits(credits_data)
    
    embed = discord.Embed(
        title="✅ Daily Bonus Claimed!",
        description=f"You received **{bonus}** bonus credits!",
        color=COLORS['success'],
        timestamp=datetime.now()
    )
    embed.add_field(name="New Balance", value=f"**{credits_data[user_id]['balance']}** credits", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ==================== ADMIN COMMANDS ====================
@bot.tree.command(name="grant", description="[ADMIN] Grant credits to a user")
@app_commands.default_permissions(administrator=True)
async def grant(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "No reason provided"):
    user_id = str(member.id)
    
    if user_id not in credits_data:
        credits_data[user_id] = {"balance": 0, "last_daily": None}
    
    old_balance = credits_data[user_id]["balance"]
    credits_data[user_id]["balance"] += amount
    save_credits(credits_data)
    
    embed = discord.Embed(
        title="✅ Credits Granted",
        color=COLORS['success'],
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Amount", value=f"+{amount}", inline=True)
    embed.add_field(name="New Balance", value=f"**{credits_data[user_id]['balance']}**", inline=True)
    embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove", description="[ADMIN] Remove credits from a user")
@app_commands.default_permissions(administrator=True)
async def remove(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "No reason provided"):
    user_id = str(member.id)
    
    if user_id not in credits_data:
        credits_data[user_id] = {"balance": 0, "last_daily": None}
    
    old_balance = credits_data[user_id]["balance"]
    credits_data[user_id]["balance"] = max(0, credits_data[user_id]["balance"] - amount)
    save_credits(credits_data)
    
    embed = discord.Embed(
        title="✅ Credits Removed",
        color=COLORS['warning'],
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Amount", value=f"-{amount}", inline=True)
    embed.add_field(name="New Balance", value=f"**{credits_data[user_id]['balance']}**", inline=True)
    embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="📚 Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 GTA Heist Bot Commands",
        description="Premium credit management for heist crews",
        color=COLORS['primary']
    )
    
    embed.add_field(
        name="👤 **User Commands**",
        value="`/balance` - Check your credits\n`/balance @user` - Check someone's credits\n`/leaderboard` - View top holders\n`/daily` - Claim bonus credits",
        inline=False
    )
    
    if interaction.user.guild_permissions.administrator:
        embed.add_field(
            name="🛡️ **Admin Commands**",
            value="`/grant @user amount` - Add credits\n`/remove @user amount` - Remove credits",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ **Info**",
        value="• 5 credits automatically added daily to Heist role members\n• 1 credit = 1 heist participation\n• Daily bonus gives 3-8 extra credits",
        inline=False
    )
    
    embed.set_footer(text="Premium Heist Bot • 24/7 Online")
    await interaction.response.send_message(embed=embed)

@bot.command()
async def sync(ctx):
    if ctx.author.guild_permissions.administrator:
        try:
            synced = await bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} command(s)!")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")
    else:
        await ctx.send("Admin only!")

if __name__ == "__main__":
    TOKEN = os.getenv('TOKEN')
    if not TOKEN:
        print("❌ No token found! Make sure TOKEN is set in .env file")
    else:
        bot.run(TOKEN)
