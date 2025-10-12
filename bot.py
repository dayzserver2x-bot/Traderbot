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
        await interaction.response.send_message(f"⚠️ {name.title()} already exists.", ephemeral=True)
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
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    items = load_items()
    name = name.lower()
    if name not in items:
        await interaction.response.send_message(f"❌ {name.title()} not found.", ephemeral=True)
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
        await interaction.response.send_message(f"❌ {item_name.title()} not found.", ephemeral=False)

# -------------------------------
# 🔎 SEARCH COMMAND
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

    class SearchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=600)  # ⏰ 10-minute timeout
            self.options = [
                discord.SelectOption(label=name.title(), description=f"Buy ${data['buy']:,.2f} | Sell ${data['sell']:,.2f}")
                for name, data in list(results.items())[:25]
            ]
            self.selected_item = None
            self.select = discord.ui.Select(
                placeholder="Select an item to add to total...",
                options=self.options,
                min_values=1,
                max_values=1
            )
            self.select.callback = self.select_callback
            self.add_item(self.select)

        async def on_timeout(self):
            for child in self.children:
                if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                    child.disabled = True
            try:
                await self.message.edit(content="⏰ This menu has timed out.", view=self)
            except Exception:
                pass

        async def select_callback(self, inter: discord.Interaction):
            self.selected_item = self.select.values[0].lower()
            await inter.response.send_message(
                f"✅ Selected **{self.selected_item.title()}**. Click 'Add to Total' to save it.",
                ephemeral=True
            )

        @discord.ui.button(label="➕ Add to Total", style=discord.ButtonStyle.success)
        async def add_to_total(self, inter: discord.Interaction, button: discord.ui.Button):
            if not self.selected_item:
                await inter.response.send_message("⚠️ Please select an item first.", ephemeral=False)
                return

            user_id = inter.user.id
            user_selected_items.setdefault(user_id, [])
            if self.selected_item not in user_selected_items[user_id]:
                user_selected_items[user_id].append(self.selected_item)
                await inter.response.send_message(
                    f"🛒 Added **{self.selected_item.title()}** to your total list!",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    f"⚠️ **{self.selected_item.title()}** is already in your total list.",
                    ephemeral=True
                )

    view = SearchView()
    sent_msg = await interaction.response.send_message(embed=embed, view=view)
    view.message = await sent_msg.original_response()

# -------------------------------
# 💰 TOTAL COMMAND (with timeout)
# -------------------------------
@bot.tree.command(name="total", description="Calculate total buy/sell value of multiple items")
async def total(interaction: discord.Interaction):
    items = load_items()
    if not items:
        await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=False)
        return

    user_id = interaction.user.id
    preselected_items = [i.lower() for i in user_selected_items.get(user_id, [])]
    all_items_list = list(sorted(items.items()))
    total_pages = (len(all_items_list) - 1) // 25 + 1

    class TotalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=600)  # ⏰ 10-minute timeout
            self.selected_items = list(dict.fromkeys(preselected_items))
            self.page = 0
            self.update_dropdown_and_embed()

        async def on_timeout(self):
            for child in self.children:
                if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                    child.disabled = True
            try:
                await self.message.edit(content="⏰ This total menu has timed out.", view=self)
            except Exception:
                pass

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
            await interaction.response.send_message(
                f"✅ Added: {', '.join([i.title() for i in newly_selected])}\n🧾 Total selected: {len(self.selected_items)} items",
                ephemeral=True
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

        @discord.ui.button(label="📋 View Selected Items", style=discord.ButtonStyle.primary)
        async def view_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.selected_items:
                await interaction.response.send_message("⚠️ You haven't selected any items yet!", ephemeral=False)
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

            if len(self.selected_items) > 25:
                embed.set_footer(text="⚠️ Showing first 25 items only.")

            await interaction.response.send_message(embed=embed, ephemeral=False)

        @discord.ui.button(label="✅ Calculate Total", style=discord.ButtonStyle.success)
        async def calculate_total(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.selected_items:
                await interaction.response.send_message("⚠️ You haven't selected any items yet!", ephemeral=False)
                return

            items_data = load_items()
            selected_items = list(dict.fromkeys(self.selected_items))
            batches = [selected_items[i:i + 5] for i in range(0, len(selected_items), 5)]

            total_buy = 0.0
            total_sell = 0.0
            details = []

            class QuantityModal(discord.ui.Modal, title="Enter Quantities"):
                def __init__(self, batch):
                    super().__init__()
                    self.batch = batch
                    for item in batch:
                        self.add_item(discord.ui.TextInput(
                            label=f"{item.title()} Quantity",
                            placeholder="Enter a number (e.g., 3)",
                            required=True
                        ))

                async def on_submit(self, modal_interaction: discord.Interaction):
                    nonlocal total_buy, total_sell, details

                    for i, item in enumerate(self.batch):
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
                        details.append(
                            f"• {item.title()} × {qty} → 🛒 Buy: `${buy_val:,.2f}` | 💵 Sell: `${sell_val:,.2f}`"
                        )

                    if batches:
                        await modal_interaction.response.send_message(
                            f"✅ Recorded {len(self.batch)} items.\nPress **Continue** to enter more quantities or **Finish** to calculate totals.",
                            ephemeral=False,
                            view=ContinueView()
                        )
                    else:
                        await send_summary(modal_interaction)

            async def send_summary(inter):
                summary = discord.Embed(title="📦 Total Calculation", color=discord.Color.blurple())
                detail_text = "\n".join(details)
                summary.add_field(name="Details", value=(detail_text[:1020] + "…") if len(detail_text) > 1024 else detail_text, inline=False)
                summary.add_field(name="💰 Total Buy", value=f"${total_buy:,.2f}")
                summary.add_field(name="💵 Total Sell", value=f"${total_sell:,.2f}")
                await inter.response.send_message(embed=summary)

                if user_id in user_selected_items:
                    del user_selected_items[user_id]
                self.selected_items.clear()
                await inter.followup.send("🧹 All selected items have been cleared.", ephemeral=False)

            class ContinueView(discord.ui.View):
                @discord.ui.button(label="Continue", style=discord.ButtonStyle.secondary)
                async def continue_button(self, inter: discord.Interaction, _):
                    if batches:
                        next_batch = batches.pop(0)
                        await inter.response.send_modal(QuantityModal(next_batch))
                    else:
                        await inter.response.send_message("✅ All items recorded.", ephemeral=False)

                @discord.ui.button(label="Finish", style=discord.ButtonStyle.success)
                async def finish_button(self, inter: discord.Interaction, _):
                    await send_summary(inter)

            first_batch = batches.pop(0)
            await interaction.response.send_modal(QuantityModal(first_batch))

    view = TotalView()
    sent_msg = await interaction.response.send_message(embed=view.current_embed, view=view)
    view.message = await sent_msg.original_response()

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
