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

        @discord.ui.button(label="➕ Add More", style=discord.ButtonStyle.secondary)
        async def add_more(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.update_dropdown_and_embed()
            await interaction.response.edit_message(embed=self.current_embed, view=self)

        # ✅ NEW — clean, non-recursive modal batching
        @discord.ui.button(label="✅ Calculate Total", style=discord.ButtonStyle.success)
        async def calculate_total(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.selected_items:
                await interaction.response.send_message("⚠️ You haven't selected any items yet!", ephemeral=True)
                return

            items_data = load_items()
            selected_items = list(dict.fromkeys(self.selected_items))

            total_buy = 0.0
            total_sell = 0.0
            details = []

            # Split into batches of 5 per modal
            batches = [selected_items[i:i + 5] for i in range(0, len(selected_items), 5)]

            class QuantityModal(discord.ui.Modal, title="Enter Quantities"):
                def __init__(self, batch_index=0):
                    super().__init__()
                    self.batch_index = batch_index
                    for item in batches[batch_index]:
                        self.add_item(discord.ui.TextInput(
                            label=f"{item.title()} Quantity",
                            placeholder="Enter a number (e.g., 3)",
                            required=True
                        ))

                async def on_submit(self, modal_interaction: discord.Interaction):
                    nonlocal total_buy, total_sell, details
                    current_batch = batches[self.batch_index]

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
                        details.append(
                            f"• {item.title()} × {qty} → 🛒 Buy: `${buy_val:,.2f}` | 💵 Sell: `${sell_val:,.2f}`"
                        )

                    # Show next modal if there are more batches
                    if self.batch_index + 1 < len(batches):
                        next_modal = QuantityModal(self.batch_index + 1)
                        await modal_interaction.response.send_modal(next_modal)
                    else:
                        # Final results
                        summary = discord.Embed(
                            title="📦 Total Calculation",
                            color=discord.Color.blurple()
                        )
                        detail_text = "\n".join(details)
                        summary.add_field(name="Details", value=detail_text[:1024], inline=False)
                        summary.add_field(name="💰 Total Buy", value=f"${total_buy:,.2f}")
                        summary.add_field(name="💵 Total Sell", value=f"${total_sell:,.2f}")
                        await modal_interaction.response.send_message(embed=summary)

            # Start with first modal
            await interaction.response.send_modal(QuantityModal(0))

    view = TotalView()
    await interaction.response.send_message(embed=view.current_embed, view=view)
