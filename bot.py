import difflib
import json
import logging
import os
from threading import Thread

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask

# Enable logging to see full errors
logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ITEMS_FILE = os.path.join(BASE_DIR, "items.json")

# -------------------------------
# 🌐 KEEP ALIVE SERVER
# -------------------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running!"


def run_keep_alive():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run_keep_alive, daemon=True)
    t.start()


# -------------------------------
# ⚙️ LOAD ENVIRONMENT
# -------------------------------
load_dotenv(os.path.join(BASE_DIR, ".env"))
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
        with open(ITEMS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return repair_items(data)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        return {}


def save_items(data):
    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
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
# 🧾 CALCULATOR DATA
# -------------------------------
# user_id: {item_name: integer_quantity}
user_selected_items = {}
# user_id: "buy" or "sell"
user_calc_mode = {}

MODE_INFO = {
    "buy": ("💰", "Buying", "Buy"),
    "sell": ("💵", "Selling", "Sell"),
}

CATEGORY_ORDER = [
    "Weapons",
    "Ammo & Magazines",
    "Attachments",
    "Armor & Clothing",
    "Medical",
    "Tools & Repair",
    "Base & Storage",
    "Explosives",
    "Hunting & Pelts",
    "Vehicle & Power",
    "Misc",
]

WEAPONS = {
    "blaze", "m79", "auga1", "augax", "bizon", "bk133", "cr527", "crossbow",
    "deagle", "dmr", "golddeagle", "ka101", "ka74", "ka74u", "kam", "lar",
    "lemas", "longhorn", "m16a2", "m4a1", "mosin", "pioneer", "repeater",
    "revolver", "savannah", "sg5k", "sks", "sv98", "sval", "tundra", "usg45",
    "vaiga", "vikhr", "vsd", "vss",
}

AMMO_MAGS = {
    "60rd", "ammobox", "dmr20rd", "highcal", "ka7445rd", "kam75rd", "lowcal",
    "mediumcal", "othermag", "shotgunshells", "standardized", "viaga 20rd",
}

ATTACHMENTS = {
    "4x6x", "allweaponparts", "bottle suppressor", "marksman scope", "nvg scopes",
    "normalizedsuppressor", "otherscopes", "pistolsuppressor", "reddots", "riflewrap",
}

ARMOR_CLOTHING = {
    "36slot", "42slot", "65slot", "assaultvest", "ballisticsvest", "beltattachments",
    "belts", "boots", "bottoms", "buttpack", "cloak", "eyewear", "face mask",
    "gas mask filters", "gasmask", "gloves", "goggles", "hats", "headstrap", "helmet",
    "holster", "hood", "hunting vest", "nbcboots", "nbcgloves", "nbchood", "nbcjacket",
    "nbcpants", "nvg", "platecarrier", "pouches", "sheath", "shrug", "suit",
    "tacticalvest", "tops/shirts/jackets",
}

MEDICAL = {
    "antidote", "bandage", "disinfectant", "firstaidbag", "injections", "ivstarter",
    "saline", "vitamins/tetra",
}

TOOLS_REPAIR = {
    "blowtorch", "clothsewing", "electicalrepair", "fireaxe", "guncleaningkit", "hacksaw",
    "handsaw", "hatchet", "leathersewing", "pipewrench", "pliers", "poxy putty",
    "screwdriver", "sharpeningstone", "shovel/pickaxe", "splittingaxe", "wrench",
}

BASE_STORAGE = {
    "barbwire", "barrel", "builtprotectivecase", "cartent", "flags", "fourdial",
    "largetent", "mediumtent", "metalwire", "nails", "protectivecase", "seachest",
    "threedial",
}

EXPLOSIVES = {
    "4mmgas", "4mmgrenade", "claymore", "detonator", "fireworks", "frags",
    "gasgrenade", "landmines", "plasticexplosive", "smoke",
}

HUNTING_PELTS = {
    "bearpelts", "beartrap", "cowpelts", "deerpelt", "foxpelts", "pigpelts/boar",
    "sheep/goat/lamb", "wolfpelts",
}

VEHICLE_POWER = {
    "batterycharger", "gascanisters", "generator", "jerrycan", "v9battery",
}


def get_item_category(item_name: str) -> str:
    name = item_name.lower()
    if name in WEAPONS:
        return "Weapons"
    if name in AMMO_MAGS:
        return "Ammo & Magazines"
    if name in ATTACHMENTS:
        return "Attachments"
    if name in ARMOR_CLOTHING:
        return "Armor & Clothing"
    if name in MEDICAL:
        return "Medical"
    if name in TOOLS_REPAIR:
        return "Tools & Repair"
    if name in BASE_STORAGE:
        return "Base & Storage"
    if name in EXPLOSIVES:
        return "Explosives"
    if name in HUNTING_PELTS:
        return "Hunting & Pelts"
    if name in VEHICLE_POWER:
        return "Vehicle & Power"
    return "Misc"


def build_categories(items):
    categories = {category: [] for category in CATEGORY_ORDER}
    for name in sorted(items):
        categories[get_item_category(name)].append(name)
    return {name: values for name, values in categories.items() if values}


def price_for_mode(item_data, mode: str) -> float:
    return float(item_data[mode])


def mode_text(mode):
    if mode not in MODE_INFO:
        return "Not selected"
    emoji, long_name, _ = MODE_INFO[mode]
    return f"{emoji} {long_name}"


def cart_stats(user_id: int, items, mode=None):
    cart = user_selected_items.get(user_id, {})
    line_items = len(cart)
    units = sum(cart.values())
    total = 0.0
    if mode in MODE_INFO:
        for name, qty in cart.items():
            data = items.get(name)
            if data:
                total += price_for_mode(data, mode) * qty
    return line_items, units, total


def normalized_text(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def find_item_matches(items, query: str, limit=25):
    query = query.strip().lower()
    if not query:
        return []

    query_norm = normalized_text(query)
    ranked = []
    for name in items:
        name_lower = name.lower()
        name_norm = normalized_text(name_lower)
        ratio = difflib.SequenceMatcher(None, query_norm, name_norm).ratio()

        if query in name_lower or query_norm in name_norm:
            score = 3.0 + ratio
        else:
            query_parts = [p for p in query.replace("/", " ").split() if p]
            if query_parts and all(part in name_lower for part in query_parts):
                score = 2.0 + ratio
            elif ratio >= 0.42:
                score = ratio
            else:
                continue

        ranked.append((score, name))

    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in ranked[:limit]]


def chunk_lines(lines, max_chars=950, max_chunks=5):
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        needed = len(line) + (1 if current else 0)
        if current and current_len + needed > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
            if len(chunks) >= max_chunks:
                break
        current.append(line)
        current_len += needed

    if current and len(chunks) < max_chunks:
        chunks.append("\n".join(current))
    return chunks


# -------------------------------
# 🧮 QUANTITY MODAL
# -------------------------------
class QuantityModal(discord.ui.Modal):
    def __init__(self, main_view, item_name, source_view=None, source_message=None):
        super().__init__(title="Enter Quantity")
        self.main_view = main_view
        self.item_name = item_name.lower()
        self.source_view = source_view
        self.source_message = source_message

        current_qty = user_selected_items.get(main_view.owner_id, {}).get(self.item_name)
        self.quantity = discord.ui.TextInput(
            label=f"{self.item_name.title()} Quantity"[:45],
            placeholder="Whole number (example: 3)",
            required=True,
            default="" if current_qty is None else str(current_qty),
            max_length=8,
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.main_view.owner_id:
            await interaction.response.send_message("❌ This calculator belongs to someone else.", ephemeral=True)
            return

        raw = self.quantity.value.strip().replace(",", "")
        try:
            qty = int(raw)
        except ValueError:
            await interaction.response.send_message("⚠️ Please enter a whole number like `1`, `5`, or `20`.", ephemeral=True)
            return

        if qty < 0:
            await interaction.response.send_message("⚠️ Quantity cannot be negative.", ephemeral=True)
            return

        items = load_items()
        item_data = items.get(self.item_name)
        if not item_data:
            await interaction.response.send_message("❌ That item no longer exists in the shop.", ephemeral=True)
            return

        cart = user_selected_items.setdefault(self.main_view.owner_id, {})
        if qty == 0:
            cart.pop(self.item_name, None)
            action = f"🗑️ Removed **{self.item_name.title()}** from your cart."
        else:
            cart[self.item_name] = qty
            mode = self.main_view.mode
            if mode in MODE_INFO:
                subtotal = price_for_mode(item_data, mode) * qty
                action = f"✅ **{self.item_name.title()} × {qty}** saved — `${subtotal:,.2f}` subtotal."
            else:
                action = f"✅ **{self.item_name.title()} × {qty}** saved."

        if not cart:
            user_selected_items.pop(self.main_view.owner_id, None)

        line_items, units, total = cart_stats(self.main_view.owner_id, items, self.main_view.mode)
        if self.main_view.mode in MODE_INFO:
            status = f"🛒 Cart: **{line_items} items / {units} units** • Running total: **${total:,.2f}**"
        else:
            status = f"🛒 Cart: **{line_items} items / {units} units**"

        await interaction.response.send_message(f"{action}\n{status}", ephemeral=True)
        await self.main_view.refresh_main_message()

        if self.source_view is not None and self.source_message is not None:
            try:
                if hasattr(self.source_view, "reload_from_cart"):
                    self.source_view.reload_from_cart()
                self.source_view.update_view()
                await self.source_message.edit(embed=self.source_view.current_embed, view=self.source_view)
            except (discord.HTTPException, AttributeError):
                pass


# -------------------------------
# 📖 BROWSE / SEARCH RESULTS VIEW
# -------------------------------
class ItemBrowserView(discord.ui.View):
    def __init__(self, main_view, item_names, title, page=0, timeout=180):
        super().__init__(timeout=timeout)
        self.main_view = main_view
        self.owner_id = main_view.owner_id
        self.item_names = list(item_names)
        self.title = title
        self.page = page
        self.page_size = 25
        self.current_embed = None
        self.select_menu = None
        self.update_view()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This calculator belongs to someone else.", ephemeral=True)
            return False
        return True

    @property
    def page_count(self):
        return max(1, (len(self.item_names) - 1) // self.page_size + 1)

    def page_items(self):
        start = self.page * self.page_size
        return self.item_names[start:start + self.page_size]

    def create_embed(self):
        items = load_items()
        mode = self.main_view.mode
        if mode not in MODE_INFO:
            return discord.Embed(
                title=self.title,
                description="Choose **Buying** or **Selling** on the main calculator first.",
                color=discord.Color.orange(),
            )

        emoji, long_name, short_name = MODE_INFO[mode]
        lines = []
        cart = user_selected_items.get(self.owner_id, {})
        for name in self.page_items():
            data = items.get(name)
            if not data:
                continue
            qty = cart.get(name)
            qty_text = f" • 📦 x{qty}" if qty else ""
            lines.append(f"• **{name.title()}** — {emoji} ${price_for_mode(data, mode):,.2f}{qty_text}")

        if not lines:
            lines = ["No items found on this page."]

        embed = discord.Embed(
            title=f"{self.title} (Page {self.page + 1}/{self.page_count})",
            description=(
                f"**Mode:** {emoji} {long_name}\n"
                f"Select an item below to enter its quantity.\n\n"
                + "\n".join(lines)
            ),
            color=discord.Color.gold(),
        )
        line_items, units, total = cart_stats(self.owner_id, items, mode)
        embed.set_footer(text=f"Cart: {line_items} items / {units} units • {short_name} total: ${total:,.2f}")
        return embed

    def update_view(self):
        items = load_items()
        mode = self.main_view.mode

        for child in list(self.children):
            if isinstance(child, discord.ui.Select):
                self.remove_item(child)

        options = []
        for name in self.page_items():
            data = items.get(name)
            if not data:
                continue
            cart_qty = user_selected_items.get(self.owner_id, {}).get(name)
            if mode in MODE_INFO:
                price = price_for_mode(data, mode)
                desc = f"${price:,.2f}"
            else:
                desc = "Choose Buy/Sell first"
            if cart_qty:
                desc += f" • Cart x{cart_qty}"
            options.append(discord.SelectOption(label=name.title()[:100], value=name, description=desc[:100]))

        if options:
            self.select_menu = discord.ui.Select(
                placeholder="Select an item to enter quantity...",
                min_values=1,
                max_values=1,
                options=options,
                row=0,
            )
            self.select_menu.callback = self.handle_select
            self.add_item(self.select_menu)

        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.page_count - 1
        self.current_embed = self.create_embed()

    async def handle_select(self, interaction: discord.Interaction):
        selected_item = self.select_menu.values[0]
        await interaction.response.send_modal(
            QuantityModal(self.main_view, selected_item, source_view=self, source_message=interaction.message)
        )

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        self.update_view()
        await interaction.response.edit_message(embed=self.current_embed, view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.page_count - 1:
            self.page += 1
        self.update_view()
        await interaction.response.edit_message(embed=self.current_embed, view=self)


# -------------------------------
# 📂 CATEGORY PICKER
# -------------------------------
class CategoryView(discord.ui.View):
    def __init__(self, main_view):
        super().__init__(timeout=180)
        self.main_view = main_view
        self.owner_id = main_view.owner_id
        items = load_items()
        self.categories = build_categories(items)

        options = [
            discord.SelectOption(label=name, value=name, description=f"{len(names)} item(s)")
            for name, names in self.categories.items()
        ]
        select = discord.ui.Select(
            placeholder="Choose a category...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self.select_category
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This calculator belongs to someone else.", ephemeral=True)
            return False
        return True

    async def select_category(self, interaction: discord.Interaction):
        category = interaction.data["values"][0]
        names = self.categories.get(category, [])
        browser = ItemBrowserView(self.main_view, names, f"📂 {category}")
        await interaction.response.edit_message(embed=browser.current_embed, view=browser)


# -------------------------------
# 🔎 SEARCH MODAL
# -------------------------------
class SearchItemModal(discord.ui.Modal, title="Search Shop Items"):
    query = discord.ui.TextInput(
        label="Item name",
        placeholder="Example: battery, aug, ammo...",
        required=True,
        max_length=80,
    )

    def __init__(self, main_view):
        super().__init__()
        self.main_view = main_view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.main_view.owner_id:
            await interaction.response.send_message("❌ This calculator belongs to someone else.", ephemeral=True)
            return

        items = load_items()
        matches = find_item_matches(items, str(self.query.value), limit=25)
        if not matches:
            await interaction.response.send_message(
                f"❌ No items found matching **{self.query.value}**.",
                ephemeral=True,
            )
            return

        browser = ItemBrowserView(
            self.main_view,
            matches,
            f"🔎 Search: {str(self.query.value).strip()}",
        )
        await interaction.response.send_message(embed=browser.current_embed, view=browser, ephemeral=False)


# -------------------------------
# 🛒 CART VIEW
# -------------------------------
class CartView(ItemBrowserView):
    def __init__(self, main_view):
        names = list(user_selected_items.get(main_view.owner_id, {}).keys())
        super().__init__(main_view, names, "🛒 Your Cart", timeout=180)

    def reload_from_cart(self):
        self.item_names = list(user_selected_items.get(self.owner_id, {}).keys())
        self.item_names.sort()
        self.page = min(self.page, self.page_count - 1)

    def create_embed(self):
        items = load_items()
        mode = self.main_view.mode
        cart = user_selected_items.get(self.owner_id, {})

        if not cart:
            return discord.Embed(
                title="🛒 Your Cart",
                description="Your cart is empty. Use **Search**, **Categories**, or **Browse All** to add items.",
                color=discord.Color.blue(),
            )

        lines = []
        for name in self.page_items():
            qty = cart.get(name)
            data = items.get(name)
            if not qty or not data:
                continue
            if mode in MODE_INFO:
                emoji, _, _ = MODE_INFO[mode]
                subtotal = price_for_mode(data, mode) * qty
                lines.append(f"• **{name.title()} × {qty}** — {emoji} ${subtotal:,.2f}")
            else:
                lines.append(f"• **{name.title()} × {qty}**")

        line_items, units, total = cart_stats(self.owner_id, items, mode)
        description = "Select an item below to change its quantity. Enter `0` to remove it.\n\n" + "\n".join(lines)
        embed = discord.Embed(
            title=f"🛒 Your Cart (Page {self.page + 1}/{self.page_count})",
            description=description,
            color=discord.Color.blue(),
        )
        if mode in MODE_INFO:
            emoji, long_name, _ = MODE_INFO[mode]
            embed.add_field(name=f"{emoji} {long_name} Total", value=f"**${total:,.2f}**", inline=False)
        embed.set_footer(text=f"{line_items} item(s) • {units} total unit(s)")
        return embed

    def update_view(self):
        self.reload_from_cart()
        super().update_view()


# -------------------------------
# 🗑️ CLEAR CONFIRMATION
# -------------------------------
class ConfirmClearView(discord.ui.View):
    def __init__(self, main_view):
        super().__init__(timeout=60)
        self.main_view = main_view
        self.owner_id = main_view.owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This calculator belongs to someone else.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🗑️ Clear Cart", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_selected_items.pop(self.owner_id, None)
        await interaction.response.edit_message(content="🧹 Your calculator cart has been cleared.", embed=None, view=None)
        await self.main_view.refresh_main_message()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Clear cancelled.", embed=None, view=None)


# -------------------------------
# 🧮 MAIN CALCULATOR VIEW
# -------------------------------
class TotalView(discord.ui.View):
    def __init__(self, owner: discord.Member | discord.User):
        super().__init__(timeout=900)
        self.owner_id = owner.id
        self.owner_name = owner.display_name
        self.mode = user_calc_mode.get(self.owner_id)
        self.message = None
        self.sync_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"❌ This calculator belongs to **{self.owner_name}**. Run `/total` to open your own.",
                ephemeral=True,
            )
            return False
        return True

    def sync_controls(self):
        mode_selected = self.mode in MODE_INFO
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "calc:buy":
                child.style = discord.ButtonStyle.success if self.mode == "buy" else discord.ButtonStyle.secondary
            elif child.custom_id == "calc:sell":
                child.style = discord.ButtonStyle.success if self.mode == "sell" else discord.ButtonStyle.secondary
            elif child.custom_id in {"calc:search", "calc:categories", "calc:browse", "calc:calculate"}:
                child.disabled = not mode_selected

    def create_dashboard_embed(self):
        items = load_items()
        line_items, units, total = cart_stats(self.owner_id, items, self.mode)

        if self.mode in MODE_INFO:
            emoji, long_name, short_name = MODE_INFO[self.mode]
            running_total = f"{emoji} **${total:,.2f}** {short_name.lower()} total"
            instruction = (
                "Find an item with **Search**, pick a **Category**, or use **Browse All**. "
                "Your cart stays saved until you calculate or clear it."
            )
        else:
            long_name = "Not selected"
            running_total = "Choose **Buying** or **Selling** first."
            instruction = "Start by choosing whether you are calculating **Buying** or **Selling** prices."

        embed = discord.Embed(
            title="🛍️ Trader Calculator",
            description=instruction,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Mode", value=mode_text(self.mode), inline=True)
        embed.add_field(name="🛒 Cart", value=f"**{line_items}** item(s) • **{units}** unit(s)", inline=True)
        embed.add_field(name="Running Total", value=running_total, inline=False)

        if line_items:
            cart = user_selected_items.get(self.owner_id, {})
            preview = []
            for name, qty in list(cart.items())[:5]:
                preview.append(f"• {name.title()} × {qty}")
            if line_items > 5:
                preview.append(f"• …and {line_items - 5} more")
            embed.add_field(name="Current Cart", value="\n".join(preview), inline=False)

        embed.set_footer(text=f"Only {self.owner_name} can use these controls • Session buttons expire after 15 minutes")
        return embed

    async def refresh_main_message(self):
        self.sync_controls()
        if self.message is not None:
            try:
                await self.message.edit(embed=self.create_dashboard_embed(), view=self)
            except discord.HTTPException:
                pass

    async def set_mode(self, interaction: discord.Interaction, mode: str):
        self.mode = mode
        user_calc_mode[self.owner_id] = mode
        self.sync_controls()
        await interaction.response.edit_message(embed=self.create_dashboard_embed(), view=self)

    @discord.ui.button(label="💰 Buying", style=discord.ButtonStyle.secondary, row=0, custom_id="calc:buy")
    async def buying(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_mode(interaction, "buy")

    @discord.ui.button(label="💵 Selling", style=discord.ButtonStyle.secondary, row=0, custom_id="calc:sell")
    async def selling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_mode(interaction, "sell")

    @discord.ui.button(label="🔎 Search Item", style=discord.ButtonStyle.primary, row=1, custom_id="calc:search")
    async def search_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchItemModal(self))

    @discord.ui.button(label="📂 Categories", style=discord.ButtonStyle.primary, row=1, custom_id="calc:categories")
    async def categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = load_items()
        if not items:
            await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=True)
            return
        view = CategoryView(self)
        embed = discord.Embed(
            title="📂 Shop Categories",
            description="Choose a category to narrow down the shop items.",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @discord.ui.button(label="📖 Browse All", style=discord.ButtonStyle.secondary, row=1, custom_id="calc:browse")
    async def browse_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = load_items()
        if not items:
            await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=True)
            return
        browser = ItemBrowserView(self, sorted(items), "📖 Browse All Items")
        await interaction.response.send_message(embed=browser.current_embed, view=browser, ephemeral=False)

    @discord.ui.button(label="🛒 View / Edit Cart", style=discord.ButtonStyle.primary, row=2, custom_id="calc:cart")
    async def view_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_selected_items.get(self.owner_id):
            await interaction.response.send_message(
                "🛒 Your cart is empty. Use **Search**, **Categories**, or **Browse All** to add something.",
                ephemeral=True,
            )
            return
        cart_view = CartView(self)
        await interaction.response.send_message(embed=cart_view.current_embed, view=cart_view, ephemeral=False)

    @discord.ui.button(label="✅ Calculate", style=discord.ButtonStyle.success, row=2, custom_id="calc:calculate")
    async def calculate_total(self, interaction: discord.Interaction, button: discord.ui.Button):
        cart = user_selected_items.get(self.owner_id, {})
        if not cart:
            await interaction.response.send_message("⚠️ Your cart is empty.", ephemeral=True)
            return
        if self.mode not in MODE_INFO:
            await interaction.response.send_message("⚠️ Choose **Buying** or **Selling** first.", ephemeral=True)
            return

        items = load_items()
        emoji, long_name, short_name = MODE_INFO[self.mode]
        total = 0.0
        lines = []
        valid_line_count = 0

        for name, qty in cart.items():
            data = items.get(name)
            if not data:
                continue
            unit_price = price_for_mode(data, self.mode)
            subtotal = unit_price * qty
            total += subtotal
            valid_line_count += 1
            lines.append(f"• **{name.title()} × {qty}** — ${unit_price:,.2f} ea. → **${subtotal:,.2f}**")

        summary = discord.Embed(
            title=f"{emoji} {long_name} Calculation",
            description=f"Calculator result for **{self.owner_name}**",
            color=discord.Color.green(),
        )

        chunks = chunk_lines(lines, max_chars=950, max_chunks=5)
        for index, text in enumerate(chunks):
            field_name = "Items" if index == 0 else "Items (continued)"
            summary.add_field(name=field_name, value=text, inline=False)

        shown_lines = sum(chunk.count("\n") + 1 for chunk in chunks) if chunks else 0
        if valid_line_count > shown_lines:
            summary.add_field(
                name="More Items",
                value=f"…plus {valid_line_count - shown_lines} additional line item(s).",
                inline=False,
            )

        summary.add_field(name=f"{emoji} Total {short_name}", value=f"**${total:,.2f}**", inline=False)
        summary.set_footer(text="Cart cleared after calculation")

        await interaction.response.send_message(embed=summary, ephemeral=False)
        user_selected_items.pop(self.owner_id, None)
        await self.refresh_main_message()

    @discord.ui.button(label="🗑️ Clear", style=discord.ButtonStyle.danger, row=2, custom_id="calc:clear")
    async def clear_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_selected_items.get(self.owner_id):
            await interaction.response.send_message("🛒 Your cart is already empty.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Are you sure you want to clear your whole cart?",
            view=ConfirmClearView(self),
            ephemeral=True,
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                embed = self.create_dashboard_embed()
                embed.set_footer(text="This calculator session expired • Run /total to reopen it")
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


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
    await interaction.response.send_message(
        f"✅ Added {name.title()} (Buy: ${buy_price:,.2f}, Sell: ${sell_price:,.2f})",
        ephemeral=False,
    )


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
        matches = find_item_matches(items, item_name, limit=5)
        if matches:
            suggestions = ", ".join(f"`{name.title()}`" for name in matches)
            await interaction.response.send_message(
                f"❌ {item_name.title()} not found. Did you mean: {suggestions}?",
                ephemeral=False,
            )
        else:
            await interaction.response.send_message(f"❌ {item_name.title()} not found.", ephemeral=False)


# -------------------------------
# 🧮 CALCULATOR COMMANDS
# -------------------------------
async def open_calculator(interaction: discord.Interaction):
    items = load_items()
    if not items:
        await interaction.response.send_message("⚠️ The shop is empty.", ephemeral=False)
        return

    view = TotalView(interaction.user)
    await interaction.response.send_message(embed=view.create_dashboard_embed(), view=view, ephemeral=False)
    view.message = await interaction.original_response()


@bot.tree.command(name="total", description="Open the shop calculator")
async def total(interaction: discord.Interaction):
    await open_calculator(interaction)


@bot.tree.command(name="calculator", description="Open the easy shop calculator")
async def calculator(interaction: discord.Interaction):
    await open_calculator(interaction)


# -------------------------------
# 🔎 SEARCH COMMAND (kept for compatibility)
# -------------------------------
@bot.tree.command(name="search", description="Search for items in the shop by name")
async def search(interaction: discord.Interaction, query: str):
    items = load_items()
    matches = find_item_matches(items, query, limit=25)

    if not matches:
        await interaction.response.send_message(f"❌ No items found matching '{query}'.", ephemeral=False)
        return

    embed = discord.Embed(
        title=f"🔎 Search Results for '{query}'",
        description=f"Found {len(matches)} close match(es). Use `/total` or `/calculator` to add items to a cart.",
        color=discord.Color.blue(),
    )

    for name in matches[:25]:
        data = items[name]
        embed.add_field(
            name=name.title(),
            value=f"💰 Buy: ${data['buy']:,.2f} | 💵 Sell: ${data['sell']:,.2f}",
            inline=True,
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
