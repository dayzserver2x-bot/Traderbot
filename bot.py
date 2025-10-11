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
        await interaction.response.send_message("❌ You don't have permission to use this command.",  ephemeral=False)
        return
    if buy_price < 0 or sell_price < 0:
        await interaction.response.send_message("⚠️ Prices must be non-negative.",  ephemeral=False)
        return
    items = load_items()
    name = name.lower()
    if name in items:
        await interaction.response.send_message(f"⚠️ {name.title()} already exists.")
        return
    items[name] = {"buy": buy_price, "sell": sell_price}
    save_items(items)
    await interaction.response.send_message(f"✅ Added {name.title()} (Buy: ${buy_price}, Sell: ${sell_price})",  ephemeral=False)

# -------------------------------
# 🗑️ REMOVE ITEM
# -------------------------------
@bot.tree.command(name="removeitem", description="Remove an item (Role restricted)")
async def removeitem(interaction: discord.Interaction, name: str):
    if not has_bot_role(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.",  ephemeral=False)
        return
    items = load_items()
    name = name.lower()
    if name not in items:
        await interaction.response.send_message(f"❌ {name.title()} not found.")
        return
    del items[name]
    save_items(items)
    await interaction.response.send_message(f"🗑️ Removed {name.title()}",  ephemeral=False)

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
# 🔎 SEARCH COMMAND
# -------------------------------
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
    for name, data in results.items():
        embed.add_field(
            name=name.title(),
            value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
            inline=True
        )
    if len(embed.fields) > 25:
        embed.clear_fields()
        limited = list(results.items())[:25]
        for name, data in limited:
            embed.add_field(
                name=name.title(),
                value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
                inline=True
            )
        embed.set_footer(text="⚠️ Showing first 25 results only.")
    await interaction.response.send_message(embed=embed)

# -------------------------------
# 💰 TOTAL COMMAND (Improved Modal Input)
# -------------------------------
@bot.tree.command(name="total", description="Calculate total buy/sell value of multiple items")
async def total(interaction: discord.Interaction):
    items = load_items()
    if not items:
        await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=False)
        return

    all_items_list = list(sorted(items.items()))
    total_pages = (len(all_items_list) - 1) // 25 + 1

    class TotalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.selected_items = []
            self.page = 0
            self.update_dropdown_and_embed()

        def create_page_embed(self):
            start = self.page * 25
            end = start + 25
            current_page_items = all_items_list[start:end]
            embed = discord.Embed(
                title=f"🛍️ Available Shop Items (Page {self.page + 1}/{total_pages})",
                description="Select items below to include in your total.",
                color=discord.Color.gold()
            )
            for name, data in current_page_items:
                embed.add_field(
                    name=name.title(),
                    value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
                    inline=True
                )
            embed.set_footer(text="Use ➕ Add More to continue selecting items.")
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
            newly_selected = self.select_menu.values
            self.selected_items.extend(newly_selected)
            self.selected_items = list(dict.fromkeys(self.selected_items))
            await interaction.response.send_message(
                f"✅ Added: {', '.join(newly_selected)}\n🧾 Total selected: {len(self.selected_items)} items",
               ephemeral=False
            )

        @discord.ui.button(label="⬅️ Prev Page", style=discord.ButtonStyle.secondary)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page -= 1
                self.update_dropdown_and_embed()
                await interaction.response.edit_message(embed=self.current_embed, view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="➡️ Next Page", style=discord.ButtonStyle.secondary)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page < total_pages - 1:
                self.page += 1
                self.update_dropdown_and_embed()
                await interaction.response.edit_message(embed=self.current_embed, view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="➕ Add More", style=discord.ButtonStyle.secondary)
        async def add_more(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.update_dropdown_and_embed()
            await interaction.response.edit_message(embed=self.current_embed, view=self)

        # ✅ Improved multi-modal system
        @discord.ui.button(label="✅ Calculate Total", style=discord.ButtonStyle.success)
        async def calculate_total(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.selected_items:
                await interaction.response.send_message("⚠️ You haven't selected any items yet!",  ephemeral=False)
                return

            selected_items = list(dict.fromkeys(self.selected_items))
            items_data = load_items()

            total_buy = 0.0
            total_sell = 0.0
            details = []

            async def process_batch(start_index=0):
                """Handle 5 items per modal batch"""
                end_index = min(start_index + 5, len(selected_items))
                current_batch = selected_items[start_index:end_index]

                class QuantityModal(discord.ui.Modal, title=f"Enter Quantities ({start_index + 1}-{end_index})"):
                    def __init__(self):
                        super().__init__()
                        for item in current_batch:
                            self.add_item(discord.ui.TextInput(
                                label=f"{item.title()} Quantity",
                                placeholder="Enter a number (e.g., 3)",
                                required=True
                            ))

                    async def on_submit(self, modal_interaction: discord.Interaction):
                        nonlocal total_buy, total_sell, details
                        for i, item in enumerate(current_batch):
                            try:
                                qty = float(self.children[i].value)
                            except ValueError:
                                qty = 0
                            data = items_data.get(item.lower())
                            if not data:
                                continue
                            buy_val = data["buy"] * qty
                            sell_val = data["sell"] * qty
                            total_buy += buy_val
                            total_sell += sell_val
                            details.append(f"• {item.title()} × {qty} → 🛒 Buy: `${buy_val:,.2f}` | 💵 Sell: `${sell_val:,.2f}`")

                        # Continue to next modal batch if needed
                        if end_index < len(selected_items):
                            await process_batch(end_index)
                        else:
                            # All done → show final result
                            summary = discord.Embed(title="📦 Total Calculation", color=discord.Color.blurple())
                            summary.add_field(name="Details", value="\n".join(details)[:1024], inline=False)
                            summary.add_field(name="💰 Total Buy", value=f"${total_buy:,.2f}")
                            summary.add_field(name="💵 Total Sell", value=f"${total_sell:,.2f}")
                            await modal_interaction.response.send_message(embed=summary)

                await interaction.response.send_modal(QuantityModal())

            await process_batch()

    view = TotalView()
    await interaction.response.send_message(embed=view.current_embed, view=view)

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