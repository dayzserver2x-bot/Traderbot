import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import logging
import asyncio

# Enable logging to see full errors
logging.basicConfig(level=logging.INFO)

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
    t = Thread(target=run_keep_alive, daemon=True)
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
    if BOT_ROLE_ID and any(role.id == int(BOT_ROLE_ID) for role in member.roles):
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
# 💬 SHOP COMMAND
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
            title="🛍️ **SLOW TRADERS BOT**",
            description="Browse all available items.\nUse /price <item> for more info.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Page {len(pages)+1}/{(len(item_list)-1)//per_page + 1}")
        for name, data in chunk:
            embed.add_field(
                name=f"{name.title()}",
                value=f"💰 Buy: ${data['buy']:,.2f}\n💵 Sell: ${data['sell']:,.2f}",
                inline=True
            )
        pages.append(embed)

    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
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

    await interaction.response.send_message(embed=pages[0], view=ShopView())

# -------------------------------
# 🧮 ADD ITEM
# -------------------------------
@bot.tree.command(name="additem", description="Add a new item (Role restricted)")
async def additem(interaction: discord.Interaction, name: str, buy_price: float, sell_price: float):
    if not has_bot_role(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=False)
        return
    if buy_price < 0 or sell_price < 0:
        await interaction.response.send_message("⚠️ Prices must be non-negative.", ephemeral=False)
        return
    items = load_items()
    name = name.lower()
    if name in items:
        await interaction.response.send_message(f"⚠️ {name.title()} already exists.")
        return
    items[name] = {"buy": buy_price, "sell": sell_price}
    save_items(items)
    await interaction.response.send_message(f"✅ Added {name.title()} (Buy: ${buy_price}, Sell: ${sell_price})", ephemeral=False)

# -------------------------------
# 🗑️ REMOVE ITEM
# -------------------------------
@bot.tree.command(name="removeitem", description="Remove an item (Role restricted)")
async def removeitem(interaction: discord.Interaction, name: str):
    if not has_bot_role(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=False)
        return
    items = load_items()
    name = name.lower()
    if name not in items:
        await interaction.response.send_message(f"❌ {name.title()} not found.")
        return
    del items[name]
    save_items(items)
    await interaction.response.send_message(f"🗑️ Removed {name.title()}", ephemeral=False)

# -------------------------------
# 💲 PRICE COMMAND
# -------------------------------
@bot.tree.command(name="price", description="Check the buy/sell price of an item")
async def price(interaction: discord.Interaction, item_name: str):
    items = load_items()
    item_name = item_name.lower()
    if item_name in items:
        data = items[item_name]
        embed = discord.Embed(title=item_name.title(), color=discord.Color.green())
        embed.add_field(name="Buy", value=f"${data['buy']:,.2f}")
        embed.add_field(name="Sell", value=f"${data['sell']:,.2f}")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ {item_name.title()} not found.")

# -------------------------------
# 🔎 SEARCH COMMAND (Enhanced)
# -------------------------------
user_selected_items = {}

@bot.tree.command(name="search", description="Search for items in the shop by name")
async def search(interaction: discord.Interaction, query: str):
    items = load_items()
    query = query.lower()
    results = {name: data for name, data in items.items() if query in name}
    if not results:
        await interaction.response.send_message(f"❌ No items found matching '{query}'.", ephemeral=False)
        return

    results = dict(sorted(results.items()))
    embed = discord.Embed(
        title=f"🔎 Search Results for '{query}'",
        description=f"Found {len(results)} item(s):",
        color=discord.Color.blue()
    )
    for name, data in list(results.items())[:25]:
        embed.add_field(
            name=name.title(),
            value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
            inline=True
        )
    if len(results) > 25:
        embed.set_footer(text="⚠️ Showing first 25 results only.")

    class SearchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.select(
            placeholder="Select an item to add to total...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=name.title(), description=f"Buy ${data['buy']:,.2f} | Sell ${data['sell']:,.2f}")
                for name, data in list(results.items())[:25]
            ],
        )
        async def select_callback(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            user_id = str(select_interaction.user.id)
            selected_item = select.values[0].lower()
            if user_id not in user_selected_items:
                user_selected_items[user_id] = []
            if selected_item not in user_selected_items[user_id]:
                user_selected_items[user_id].append(selected_item)
                await select_interaction.response.send_message(
                    f"✅ Added **{selected_item.title()}** to your total list. Use `/total` to calculate quantities!",
                    ephemeral=True
                )
            else:
                await select_interaction.response.send_message(
                    f"⚠️ {selected_item.title()} is already in your total list.",
                    ephemeral=True
                )

        @discord.ui.button(label="View My Total List", style=discord.ButtonStyle.success)
        async def view_total(self, btn_interaction: discord.Interaction, _):
            user_id = str(btn_interaction.user.id)
            if user_id not in user_selected_items or not user_selected_items[user_id]:
                await btn_interaction.response.send_message("🛒 Your total list is empty!", ephemeral=True)
                return
            selected = user_selected_items[user_id]
            embed = discord.Embed(
                title="🧾 Your Current Total List",
                description="\n".join(f"• {item.title()}" for item in selected),
                color=discord.Color.green()
            )
            embed.set_footer(text="Use /total to calculate final buy/sell values.")
            await btn_interaction.response.send_message(embed=embed, ephemeral=True)

    await interaction.response.send_message(embed=embed, view=SearchView())

# -------------------------------
# 💰 TOTAL COMMAND (Enhanced)
# -------------------------------
@bot.tree.command(name="total", description="Calculate total buy/sell value of multiple items")
async def total(interaction: discord.Interaction):
    items = load_items()
    if not items:
        await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=False)
        return

    user_id = str(interaction.user.id)
    preselected = user_selected_items.get(user_id, [])
    user_selected_items[user_id] = []

    all_items_list = list(sorted(items.items()))
    total_pages = (len(all_items_list) - 1) // 25 + 1

    class TotalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.selected_items = preselected[:]
            self.page = 0
            self.update_dropdown_and_embed()
    # (Your existing TotalView logic continues here, unchanged)

# -------------------------------
# 🔄 MANUAL SYNC COMMAND
# -------------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await ctx.send("🔄 Syncing slash commands...")
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced {len(synced)} global slash commands.")

# -------------------------------
# 🚀 RUN BOT WITH KEEP ALIVE
# -------------------------------
if not TOKEN:
    print("❌ ERROR: Discord token not found in .env")
else:
    keep_alive()
    bot.run(TOKEN)