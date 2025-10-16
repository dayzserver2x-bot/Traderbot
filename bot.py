from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
import os
import json

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
ALLOWED_ROLE = os.getenv("ALLOWED_ROLE")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# JSON helpers
def load_items():
    try:
        with open("items.json", "r") as f:
            return repair_items(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_items(data):
    with open("items.json", "w") as f:
        json.dump(data, f, indent=4)

def repair_items(data):
    for key, value in data.items():
        if "buy" not in value or "sell" not in value:
            data[key] = {"buy": 0, "sell": 0}
    return data

def has_allowed_role(user: discord.Member):
    return any(str(role.id) == ALLOWED_ROLE or role.name == ALLOWED_ROLE for role in user.roles)

# Keep track of users' total message IDs
user_total_messages = {}

# ✅ Persistent TotalView Class
class TotalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_items = list(dict.fromkeys(preselected_items))
        self.page = 0
        self.update_dropdown_and_embed()

    def update_dropdown_and_embed(self):
        items = load_items()
        item_names = sorted(items.keys())
        per_page = 25
        start = self.page * per_page
        end = start + per_page
        options = [
            discord.SelectOption(label=name, description=f"Buy: {items[name]['buy']} | Sell: {items[name]['sell']}")
            for name in item_names[start:end]
        ]

        self.select_menu = discord.ui.Select(
            placeholder="Select up to 25 items...",
            min_values=1,
            max_values=min(25, len(options)),
            options=options,
            custom_id=f"select_page_{self.page}"  # ✅ unique ID
        )
        self.select_menu.callback = self.handle_select
        self.clear_items()
        self.add_item(self.select_menu)
        self.add_item(self.prev_page)
        self.add_item(self.next_page)
        self.add_item(self.view_selected)
        self.add_item(self.calculate_total)

        desc = "\n".join(
            [f"• {name}: Buy {items[name]['buy']}, Sell {items[name]['sell']}" for name in self.selected_items]
        )
        desc = desc if desc else "No items selected yet."
        self.current_embed = discord.Embed(
            title=f"Shop Total — Page {self.page+1}",
            description=desc,
            color=discord.Color.blue(),
        )

    async def handle_select(self, interaction: discord.Interaction):
        newly_selected = self.select_menu.values
        self.selected_items = list(set(self.selected_items) | set(newly_selected))
        self.update_dropdown_and_embed()
        await interaction.response.edit_message(embed=self.current_embed, view=self)

    @discord.ui.button(label="⬅️ Prev Page", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_dropdown_and_embed()
            await interaction.response.edit_message(embed=self.current_embed, view=self)

    @discord.ui.button(label="➡️ Next Page", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = load_items()
        if (self.page + 1) * 25 < len(items):
            self.page += 1
            self.update_dropdown_and_embed()
            await interaction.response.edit_message(embed=self.current_embed, view=self)

    @discord.ui.button(label="📋 View Selected Items", style=discord.ButtonStyle.primary, custom_id="view_selected")
    async def view_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
        desc = "\n".join(self.selected_items) or "No items selected."
        embed = discord.Embed(title="Selected Items", description=desc, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="✅ Calculate Total", style=discord.ButtonStyle.success, custom_id="calc_total")
    async def calculate_total(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = load_items()
        selected = self.selected_items
        total_buy = 0
        total_sell = 0
        details = []

        for name in selected:
            if name in items:
                total_buy += items[name]['buy']
                total_sell += items[name]['sell']
                details.append(f"• {name}: Buy {items[name]['buy']}, Sell {items[name]['sell']}")

        embed = discord.Embed(
            title="Total Summary",
            description="\n".join(details) or "No items selected.",
            color=discord.Color.gold()
        )
        embed.add_field(name="💰 Total Buy", value=total_buy, inline=True)
        embed.add_field(name="💎 Total Sell", value=total_sell, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ✅ Register persistent view on startup
@bot.event
async def on_ready():
    bot.add_view(TotalView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Logged in as {bot.user}")
        print(f"🔁 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"⚠️ Slash command sync failed: {e}")

# /total command
@bot.tree.command(name="total", description="Calculate total buy/sell value of multiple items")
async def total(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    user_id = interaction.user.id

    # Reuse existing total message if present
    if user_id in user_total_messages:
        try:
            msg = await interaction.channel.fetch_message(user_total_messages[user_id])
            await interaction.followup.send(f"🔁 Reusing your existing total view: {msg.jump_url}", ephemeral=True)
            return
        except:
            pass

    global preselected_items
    preselected_items = []
    view = TotalView()
    msg = await interaction.followup.send(embed=view.current_embed, view=view)
    user_total_messages[user_id] = msg.id

# Start the bot
bot.run(TOKEN)
