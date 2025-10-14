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
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------
# ✨ EMBED HELPER
# -------------------------------
def make_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)

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
# 🧮 ADD ITEM
# -------------------------------
@bot.tree.command(name="additem", description="Add a new item (Role restricted)")
async def additem(interaction: discord.Interaction, name: str, buy_price: float, sell_price: float):
    if not has_bot_role(interaction.user):
        embed = make_embed("🚫 Permission Denied", "You don't have permission to use this command.", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if buy_price < 0 or sell_price < 0:
        embed = make_embed("⚠️ Invalid Price", "Prices must be non-negative.", discord.Color.orange())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    items = load_items()
    name = name.lower()
    if name in items:
        embed = make_embed("⚠️ Item Exists", f"**{name.title()}** already exists.", discord.Color.orange())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    items[name] = {"buy": buy_price, "sell": sell_price}
    save_items(items)
    embed = make_embed("✅ Item Added", f"**{name.title()}**\n💰 Buy: ${buy_price:,.2f}\n💵 Sell: ${sell_price:,.2f}", discord.Color.green())
    await interaction.response.send_message(embed=embed)

# -------------------------------
# 🗑️ REMOVE ITEM
# -------------------------------
@bot.tree.command(name="removeitem", description="Remove an item (Role restricted)")
async def removeitem(interaction: discord.Interaction, name: str):
    if not has_bot_role(interaction.user):
        embed = make_embed("🚫 Permission Denied", "You don't have permission to use this command.", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    items = load_items()
    name = name.lower()
    if name not in items:
        embed = make_embed("❌ Not Found", f"**{name.title()}** not found.", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    del items[name]
    save_items(items)
    embed = make_embed("🗑️ Item Removed", f"**{name.title()}** has been removed.", discord.Color.orange())
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
        embed = discord.Embed(title=f"{item_name.title()} 💰", color=discord.Color.green())
        embed.add_field(name="Buy", value=f"${data['buy']:,.2f}")
        embed.add_field(name="Sell", value=f"${data['sell']:,.2f}")
    else:
        embed = make_embed("❌ Not Found", f"**{item_name.title()}** not found.", discord.Color.red())
    await interaction.response.send_message(embed=embed)

# -------------------------------
# 🔎 SEARCH COMMAND + FIXED TOTAL VIEW CALL
# -------------------------------
user_selected_items = {}  # user_id: set of item names

# ✅ Helper for showing total view safely
async def show_total_view(interaction: discord.Interaction):
    items = load_items()
    if not items:
        embed = make_embed("⚠️ Empty Shop", "There are no items in the shop.", discord.Color.orange())
        await interaction.followup.send(embed=embed)
        return

    user_id = interaction.user.id
    preselected_items = list(user_selected_items.get(user_id, set()))
    all_items_list = list(sorted(items.items()))
    total_pages = (len(all_items_list) - 1) // 25 + 1

    class TotalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.selected_items = list(dict.fromkeys(preselected_items))
            self.page = 0
            self.update_dropdown_and_embed()

        def create_page_embed(self):
            start = self.page * 25
            end = start + 25
            current_page_items = all_items_list[start:end]
            embed = discord.Embed(
                title=f"🛍️ Shop Items (Page {self.page + 1}/{total_pages})",
                description="Select items below to include in your total.",
                color=discord.Color.gold()
            )
            for name, data in current_page_items:
                embed.add_field(
                    name=name.title(),
                    value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
                    inline=True
                )
            embed.set_footer(text=f"Preselected items: {len(self.selected_items)}")
            return embed

        def update_dropdown_and_embed(self):
            start = self.page * 25
            end = start + 25
            current_page_items = all_items_list[start:end]
            options = [
                discord.SelectOption(
                    label=name.title(),
                    description=f"Buy ${data['buy']:,.2f} | Sell ${data['sell']:,.2f}"
                )
                for name, data in current_page_items
            ]
            for child in list(self.children):
                if isinstance(child, discord.ui.Select):
                    self.remove_item(child)
            self.select_menu = discord.ui.Select(
                placeholder="Select up to 25 items...",
                min_values=1,
                max_values=min(25, len(options)),
                options=options
            )
            self.select_menu.callback = self.handle_select
            self.add_item(self.select_menu)
            self.current_embed = self.create_page_embed()

        async def handle_select(self, interaction: discord.Interaction):
            newly_selected = [i.lower() for i in self.select_menu.values]
            self.selected_items.extend(newly_selected)
            self.selected_items = list(dict.fromkeys(self.selected_items))
            user_selected_items.setdefault(user_id, set()).update(self.selected_items)
            embed = make_embed("✅ Items Added", f"Added: {', '.join([i.title() for i in newly_selected])}\n🧾 Total selected: {len(self.selected_items)} items", discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page -= 1
                self.update_dropdown_and_embed()
                await interaction.response.edit_message(embed=self.current_embed, view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page < total_pages - 1:
                self.page += 1
                self.update_dropdown_and_embed()
                await interaction.response.edit_message(embed=self.current_embed, view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="📋 View Selected", style=discord.ButtonStyle.primary)
        async def view_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.selected_items:
                embed = make_embed("⚠️ No Items", "You haven't selected any items yet.", discord.Color.orange())
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title="📋 Selected Items",
                description=f"Currently selected ({len(self.selected_items)} items):",
                color=discord.Color.blue()
            )
            for item in self.selected_items[:25]:
                data = items.get(item.lower())
                if data:
                    embed.add_field(
                        name=item.title(),
                        value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
                        inline=True
                    )
            await interaction.response.send_message(embed=embed)

    view = TotalView()
    await interaction.followup.send(embed=view.current_embed, view=view)

# -------------------------------
# 💰 TOTAL COMMAND (FIXED)
# -------------------------------
@bot.tree.command(name="total", description="Calculate total buy/sell value of multiple items")
async def total(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    await show_total_view(interaction)

# -------------------------------
# 🔎 SEARCH COMMAND
# -------------------------------
@bot.tree.command(name="search", description="Search for items in the shop by name")
async def search(interaction: discord.Interaction, query: str):
    items = load_items()
    query = query.lower()
    results = {name: data for name, data in items.items() if query in name}

    if not results:
        embed = make_embed("❌ No Results", f"No items found matching '{query}'.", discord.Color.red())
        await interaction.response.send_message(embed=embed)
        return

    results = dict(sorted(results.items()))
    embed = discord.Embed(
        title=f"🔎 Results for '{query}'",
        description=f"Found **{len(results)}** item(s):",
        color=discord.Color.blue()
    )
    for name, data in list(results.items())[:25]:
        embed.add_field(
            name=name.title(),
            value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
            inline=True
        )

    await interaction.response.send_message(embed=embed)

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
