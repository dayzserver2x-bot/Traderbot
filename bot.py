import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# -------------------------------
# 🌐 KEEP ALIVE SERVER
# -------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_keep_alive():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_keep_alive)
    t.start()

# -------------------------------
# ⚙️ LOAD ENVIRONMENT
# -------------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ROLE = os.getenv("BOT_ROLE")
BOT_ROLE_ID = os.getenv("BOT_ROLE_ID")

# -------------------------------
# 🤖 DISCORD SETUP
# -------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------
# 🔐 ROLE CHECK
# -------------------------------
def has_bot_role(member: discord.Member) -> bool:
    if BOT_ROLE_ID and BOT_ROLE_ID.isdigit() and any(role.id == int(BOT_ROLE_ID) for role in member.roles):
        return True
    if BOT_ROLE and any(role.name.lower() == BOT_ROLE.lower() for role in member.roles):
        return True
    return False

# -------------------------------
# 📦 JSON HELPERS
# -------------------------------
def load_items():
    try:
        with open("items.json", "r") as f:
            data = json.load(f)
        return repair_items(data)
    except (FileNotFoundError, json.JSONDecodeError):
        with open("items.json", "w") as f:
            json.dump({}, f, indent=4)
        return {}

def save_items(data):
    with open("items.json", "w") as f:
        json.dump(data, f, indent=4)

def repair_items(data):
    fixed = {}
    for k, v in data.items():
        if isinstance(v, dict):
            buy = v.get("buy", 0)
            sell = v.get("sell", 0)
        else:
            buy = v
            sell = 0
        fixed[k.lower()] = {"buy": float(buy), "sell": float(sell)}
    return fixed

# -------------------------------
# 🚀 BOT READY
# -------------------------------
@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")
    print(f"🔁 Synced {len(synced)} slash commands")

# -------------------------------
# 💬 SHOP COMMANDS
# -------------------------------
@bot.tree.command(name="shop", description="View all available shop items")
async def shop(interaction: discord.Interaction):
    items = load_items()
    if not items:
        await interaction.response.send_message("⚠️ The shop is currently empty.")
        return

    items = dict(sorted(items.items()))
    per_page = 10
    item_list = list(items.items())
    pages = []

    for i in range(0, len(item_list), per_page):
        chunk = item_list[i:i + per_page]
        embed = discord.Embed(
            title="🛍️ **SLOW TRADERS SHOP**",
            description="Browse all available items below.\nUse </price:0> or `/price <item>` for details.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Page {len(pages)+1}/{(len(item_list)-1)//per_page + 1}")

        for name, data in chunk:
            embed.add_field(
                name=f"✨ {name.title()}",
                value=f"💰 **Buy:** `${data['buy']:.2f}`\n💵 **Sell:** `${data['sell']:.2f}`",
                inline=True
            )

        pages.append(embed)

    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=90)
            self.page = 0

        @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, _):
            if self.page > 0:
                self.page -= 1
                await interaction.response.edit_message(embed=pages[self.page], view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, _):
            if self.page < len(pages) - 1:
                self.page += 1
                await interaction.response.edit_message(embed=pages[self.page], view=self)
            else:
                await interaction.response.defer()

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True

    await interaction.response.send_message(embed=pages[0], view=ShopView())

# -------------------------------
# 🧮 ADD ITEM
# -------------------------------
@bot.tree.command(name="additem", description="Add a new item (Role restricted)")
async def additem(interaction: discord.Interaction, name: str, buy_price: float, sell_price: float):
    if not has_bot_role(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if buy_price < 0 or sell_price < 0:
        await interaction.response.send_message("⚠️ Prices must be non-negative.", ephemeral=True)
        return

    items = load_items()
    name = name.lower()
    if name in items:
        await interaction.response.send_message(f"⚠️ {name.title()} already exists.")
        return

    items[name] = {"buy": buy_price, "sell": sell_price}
    save_items(items)

    embed = discord.Embed(
        title="✅ Item Added",
        description=f"**{name.title()}** has been added to the shop.",
        color=discord.Color.green()
    )
    embed.add_field(name="💰 Buy Price", value=f"${buy_price:.2f}")
    embed.add_field(name="💵 Sell Price", value=f"${sell_price:.2f}")
    await interaction.response.send_message(embed=embed)

# -------------------------------
# 🗑️ REMOVE ITEM
# -------------------------------
@bot.tree.command(name="removeitem", description="Remove an item (Role restricted)")
async def removeitem(interaction: discord.Interaction, name: str):
    if not has_bot_role(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    items = load_items()
    name = name.lower()
    if name not in items:
        await interaction.response.send_message(f"❌ {name.title()} not found.")
        return

    del items[name]
    save_items(items)

    embed = discord.Embed(
        title="🗑️ Item Removed",
        description=f"**{name.title()}** has been removed from the shop.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

# -------------------------------
# 💲 PRICE COMMAND
# -------------------------------
@bot.tree.command(name="price", description="Check the buy/sell price of an item")
async def price(interaction: discord.Interaction, item_name: str):
    items = load_items()
    item_name = item_name.lower()
    if item_name in items:
        data = items[item_name]
        embed = discord.Embed(
            title=f"💎 {item_name.title()}",
            description="Here are the current market values:",
            color=discord.Color.blurple()
        )
        embed.add_field(name="💰 Buy Price", value=f"${data['buy']:.2f}")
        embed.add_field(name="💵 Sell Price", value=f"${data['sell']:.2f}")
        embed.set_footer(text="Use /shop to see all items")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ {item_name.title()} not found.")

# -------------------------------
# 🚀 RUN BOT WITH KEEP ALIVE
# -------------------------------
if not TOKEN:
    print("❌ ERROR: Discord token not found in .env")
else:
    keep_alive()
    bot.run(TOKEN)
