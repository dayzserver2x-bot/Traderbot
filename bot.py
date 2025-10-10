import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# --- Load Environment ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ROLE = os.getenv("BOT_ROLE")  # e.g. "Shop Manager"
BOT_ROLE_ID = os.getenv("BOT_ROLE_ID")  # Optional: role ID instead of name

# --- Discord Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Needed to check member roles
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Role Check Helper ---
def has_bot_role(member: discord.Member) -> bool:
	"""Check if the member has the required role (by name or ID)."""
	if BOT_ROLE_ID and any(role.id == int(BOT_ROLE_ID) for role in member.roles):
		return True
	if BOT_ROLE and any(role.name.lower() == BOT_ROLE.lower() for role in member.roles):
		return True
	return False

# --- JSON Helpers ---
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

# --- Bot Ready ---
@bot.event
async def on_ready():
	synced = await bot.tree.sync()
	print(f"✅ Logged in as {bot.user}")
	print(f"🔁 Synced {len(synced)} slash commands")

# --- SHOP COMMAND ---
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
				value=f"💰 Buy: ${data['buy']}\n💵 Sell: ${data['sell']}",
				inline=True
			)
		pages.append(embed)

	class ShopView(discord.ui.View):
		def __init__(self):
			super().__init__(timeout=60)
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

# --- ADD ITEM ---
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
	await interaction.response.send_message(f"✅ Added {name.title()} (Buy: ${buy_price}, Sell: ${sell_price})")

# --- REMOVE ITEM ---
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
	await interaction.response.send_message(f"🗑️ Removed {name.title()}")

# --- PRICE COMMAND ---
@bot.tree.command(name="price", description="Check the buy/sell price of an item")
async def price(interaction: discord.Interaction, item_name: str):
	items = load_items()
	item_name = item_name.lower()
	if item_name in items:
		data = items[item_name]
		embed = discord.Embed(title=item_name.title(), color=discord.Color.green())
		embed.add_field(name="Buy", value=f"${data['buy']}")
		embed.add_field(name="Sell", value=f"${data['sell']}")
		await interaction.response.send_message(embed=embed)
	else:
		await interaction.response.send_message(f"❌ {item_name.title()} not found.")

# --- MULTI-BATCH TOTAL SYSTEM (same as before, unchanged) ---
class NextBatchView(discord.ui.View):
	def __init__(self, all_selected, shop_items, next_index, total_buy, total_sell, breakdown):
		super().__init__(timeout=120)
		self.all_selected = all_selected
		self.shop_items = shop_items
		self.next_index = next_index
		self.total_buy = total_buy
		self.total_sell = total_sell
		self.breakdown = breakdown

	@discord.ui.button(label="➡️ Continue", style=discord.ButtonStyle.primary)
	async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
		modal = QuantityModal(
			self.all_selected,
			self.shop_items,
			start_index=self.next_index,
			partial_buy=self.total_buy,
			partial_sell=self.total_sell,
			partial_breakdown=self.breakdown,
		)
		await interaction.response.send_modal(modal)

class QuantityModal(discord.ui.Modal):
	def __init__(self, selected, shop_items, start_index=0, partial_buy=0, partial_sell=0, partial_breakdown=None):
		super().__init__(title="Enter Quantities")
		self.all_selected = selected
		self.shop_items = shop_items
		self.start_index = start_index
		self.partial_buy = partial_buy
		self.partial_sell = partial_sell
		self.partial_breakdown = partial_breakdown or []
		self.selected = selected[start_index:start_index + 5]
		for item in self.selected:
			self.add_item(discord.ui.TextInput(label=f"{item.title()} Quantity", required=True))

	async def on_submit(self, interaction: discord.Interaction):
		total_buy = self.partial_buy
		total_sell = self.partial_sell
		breakdown = self.partial_breakdown.copy()
		for i, item in enumerate(self.selected):
			try:
				qty = float(self.children[i].value)
				if qty <= 0:
					raise ValueError
			except ValueError:
				await interaction.response.send_message(
					f"⚠️ Invalid quantity for {item.title()}. Please enter a positive number.", ephemeral=True
				)
				return
			data = self.shop_items[item]
			buy = data["buy"] * qty
			sell = data["sell"] * qty
			total_buy += buy
			total_sell += sell
			breakdown.append(f"• {item.title()} × {int(qty)} — Buy: ${buy:,.2f}, Sell: ${sell:,.2f}")
		next_index = self.start_index + 5
		if next_index < len(self.all_selected):
			await interaction.response.send_message(
				f"✅ Recorded quantities for {len(self.selected)} items.\n"
				f"➡️ {len(self.all_selected) - next_index} items remaining. Click Continue to enter the next batch.",
				view=NextBatchView(self.all_selected, self.shop_items, next_index, total_buy, total_sell, breakdown)
			)
			return
		embed = discord.Embed(title="🧾 Total Calculation", color=discord.Color.blue())
		embed.add_field(name="💰 Total Buy", value=f"${total_buy:,.2f}", inline=True)
		embed.add_field(name="💵 Total Sell", value=f"${total_sell:,.2f}", inline=True)
		embed.add_field(name="📦 Breakdown", value="\n".join(breakdown), inline=False)
		await interaction.response.send_message(embed=embed)

class ItemSelect(discord.ui.Select):
	def __init__(self, items, page_index, total_pages):
		self.per_page = 25
		self.page_index = page_index
		sorted_items = sorted(items.items(), key=lambda x: x[0].lower())
		start = page_index * self.per_page
		end = start + self.per_page
		sliced = sorted_items[start:end]
		options = [
			discord.SelectOption(
				label=item.title(),
				description=f"Buy: ${data['buy']} | Sell: ${data['sell']}"
			) for item, data in sliced
		]
		super().__init__(
			placeholder=f"Select items (Page {page_index + 1}/{total_pages})...",
			min_values=1,
			max_values=min(25, len(options)),
			options=options
		)

	async def callback(self, interaction: discord.Interaction):
		selected = [v.lower() for v in self.values]
		self.view.selected_items.update(selected)
		await interaction.response.send_message(
			f"✅ Added {len(selected)} items from this page. "
			f"Total selected so far: **{len(self.view.selected_items)}**"
		)

class TotalView(discord.ui.View):
	def __init__(self, shop_items):
		super().__init__(timeout=180)
		self.shop_items = dict(sorted(shop_items.items(), key=lambda x: x[0].lower()))
		self.page_index = 0
		self.items_per_page = 25
		self.selected_items = set()
		total_items = len(self.shop_items)
		self.total_pages = (total_items // self.items_per_page) + (1 if total_items % self.items_per_page != 0 else 0)
		self.update_menu()

	def get_page_embed(self):
		start = self.page_index * self.items_per_page
		end = start + self.items_per_page
		sliced = list(self.shop_items.items())[start:end]
		embed = discord.Embed(
			title=f"🧾 Total Calculator — Page {self.page_index + 1}/{self.total_pages}",
			description="Select up to **25 items per page**. You can calculate all selected later.",
			color=discord.Color.gold()
		)
		for name, data in sliced:
			embed.add_field(
				name=name.title(),
				value=f"💰 Buy: ${data['buy']}\n💵 Sell: ${data['sell']}",
				inline=True
			)
		embed.set_footer(text="Use ⬅️ / ➡️ to browse pages • ❌ to close")
		return embed

	def update_menu(self):
		for child in self.children[:]:
			if isinstance(child, ItemSelect):
				self.remove_item(child)
		self.add_item(ItemSelect(self.shop_items, self.page_index, self.total_pages))

	async def refresh_view(self, interaction: discord.Interaction):
		self.update_menu()
		embed = self.get_page_embed()
		await interaction.response.edit_message(embed=embed, view=self)

	@discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
	async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.page_index > 0:
			self.page_index -= 1
			await self.refresh_view(interaction)
		else:
			await interaction.response.defer()

	@discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
	async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.page_index < self.total_pages - 1:
			self.page_index += 1
			await self.refresh_view(interaction)
		else:
			await interaction.response.defer()

	@discord.ui.button(label="🧮 Calculate Total", style=discord.ButtonStyle.success)
	async def calculate(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not self.selected_items:
			await interaction.response.send_message("⚠️ No items selected.", ephemeral=True)
			return
		selected_list = list(self.selected_items)
		modal = QuantityModal(selected_list, self.shop_items, start_index=0)
		await interaction.response.send_modal(modal)

	@discord.ui.button(label="❌ Close Bitch", style=discord.ButtonStyle.danger)
	async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
		await interaction.message.delete()

# --- /total COMMAND ---
@bot.tree.command(name="total", description="Calculate total buy/sell prices interactively")
async def total(interaction: discord.Interaction):
	shop_items = load_items()
	if not shop_items:
		await interaction.response.send_message("⚠️ The shop is empty.")
		return
	view = TotalView(shop_items)
	embed = view.get_page_embed()
	await interaction.response.send_message(embed=embed, view=view)

# --- RUN BOT ---
if not TOKEN:
	print("❌ ERROR: Discord token not found in .env")
else:
	bot.run(TOKEN)