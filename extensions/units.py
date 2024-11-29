from logging import getLogger
from discord.ext.commands import GroupCog, Bot
from discord import Interaction, app_commands as ac, Member, ui, ButtonStyle, SelectOption
from discord.ui import View
from models import Player, Unit as Unit_model, UnitStatus
from customclient import CustomClient
import os
logger = getLogger(__name__)

class Unit(GroupCog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.session = bot.session

    @ac.command(name="create", description="Create a new unit for a player")
    @ac.describe(unit_name="The name of the unit to create")
    async def createunit(self, interaction: Interaction, unit_name: str):
        class UnitSelect(ui.Select):
            def __init__(self):
                options = [SelectOption(label=unit_type, value=unit_type) for unit_type in bot.config["unit_types"]]
                super().__init__(placeholder="Select the type of unit to create", options=options)

            async def callback(self, interaction: Interaction):
                await interaction.response.defer(ephemeral=True)

        class CreateUnitView(ui.View):
            def __init__(self):
                super().__init__()
                self.session = CustomClient().session
                self.add_item(UnitSelect())

            @ui.button(label="Create Unit", style=ButtonStyle.primary)
            async def create_unit_callback(self, interaction: Interaction, button: ui.Button):
                player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
                if not player:
                    await interaction.response.send_message("You don't have a Meta Campaign company", ephemeral=CustomClient().use_ephemeral)
                    return

                units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.status == "PROPOSED").all()
                logger.debug(f"Number of proposed units: {len(units)}")
                if len(units) >= 3:
                    await interaction.response.send_message("You already have 3 proposed Units, which is the maximum allowed", ephemeral=CustomClient().use_ephemeral)
                    return

                unit_type = self.children[1].values[0]
                logger.debug(f"Unit type selected: {unit_type}")

                if self.session.query(Unit_model).filter(Unit_model.name == unit_name, Unit_model.player_id == player.id).first():
                    await interaction.response.send_message("You already have a unit with that name", ephemeral=CustomClient().use_ephemeral)
                    return
                if len(unit_name) > 30:
                    await interaction.response.send_message("Unit name is too long, please use a shorter name", ephemeral=CustomClient().use_ephemeral)
                    return
                if any(char in unit_name for char in os.getenv("BANNED_CHARS", "")+":"): # : is banned to disable urls
                    await interaction.response.send_message("Unit names cannot contain discord tags", ephemeral=CustomClient().use_ephemeral)
                    return
                if not unit_name.isascii():
                    await interaction.response.send_message("Unit names must be ASCII", ephemeral=CustomClient().use_ephemeral)
                    return
                unit = Unit_model(player_id=player.id, name=unit_name, unit_type=unit_type, active=False)
                self.session.add(unit)
                self.session.commit()
                logger.debug(f"Unit {unit.name} created for player {player.name}")
                button.disabled = True
                await interaction.response.send_message(f"Unit {unit.name} created", ephemeral=CustomClient().use_ephemeral)

        view = CreateUnitView()
        await interaction.response.send_message("Please select the unit type and enter the unit name", view=view, ephemeral=CustomClient().use_ephemeral)

    @ac.command(name="activate", description="Activate a unit")
    @ac.describe(callsign="The callsign of the unit to activate, must be globally unique")
    async def activateunit(self, interaction: Interaction, callsign: str):
        logger.debug(f"Activating unit for {interaction.user.global_name} with callsign {callsign}")
        if len(callsign) > 10:
            await interaction.response.send_message("Callsign is too long, please use a shorter callsign", ephemeral=CustomClient().use_ephemeral)
            return
        if any(char in callsign for char in os.getenv("BANNED_CHARS", "")):
            await interaction.response.send_message("Callsigns cannot contain discord tags", ephemeral=CustomClient().use_ephemeral)
            return
        if not callsign.isascii():
            await interaction.response.send_message("Callsigns must be ASCII", ephemeral=CustomClient().use_ephemeral)
            return
        logger.debug(f"Activating unit for {interaction.user.id}")
        player: Player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
        if not player:
            await interaction.response.send_message("You don't have a Meta Campaign company", ephemeral=CustomClient().use_ephemeral)
            return
        units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id).all()
        if not units:
            await interaction.response.send_message("You don't have any units", ephemeral=CustomClient().use_ephemeral)
            return
        active_unit = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.active == True).first()
        if active_unit:
            await interaction.response.send_message("You already have an active unit", ephemeral=CustomClient().use_ephemeral)
            return
        if self.session.query(Unit_model).filter(Unit_model.callsign == callsign).first():
            await interaction.response.send_message("That callsign is already taken", ephemeral=CustomClient().use_ephemeral)
            return

        class UnitSelect(ui.Select):
            def __init__(self):
                options = [SelectOption(label=unit.name, value=unit.name) for unit in units]
                self.session = CustomClient().session
                super().__init__(placeholder="Select the unit to activate", options=options)

            async def callback(self, interaction: Interaction):
                unit: Unit_model = self.session.query(Unit_model).filter(Unit_model.name == self.values[0]).filter(Unit_model.player_id == player.id).first()
                if not unit.status == UnitStatus.INACTIVE:
                    await interaction.response.send_message("That unit is not inactive", ephemeral=CustomClient().use_ephemeral)
                    return
                active_unit = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.active == True).first()
                if active_unit:
                    await interaction.response.send_message("You already have an active unit", ephemeral=CustomClient().use_ephemeral)
                    return
                if self.session.query(Unit_model).filter(Unit_model.callsign == callsign).first():
                    await interaction.response.send_message("That callsign is already taken", ephemeral=CustomClient().use_ephemeral)
                    return
                logger.debug(f"Activating unit {unit.name}")
                unit.active = True
                unit.callsign = callsign
                unit.status = UnitStatus.ACTIVE
                self.session.commit()
                await interaction.response.send_message(f"Unit {unit.name} activated", ephemeral=CustomClient().use_ephemeral)

        view = View()
        view.add_item(UnitSelect())
        await interaction.response.send_message("Please select the unit to activate", view=view, ephemeral=CustomClient().use_ephemeral)

    @ac.command(name="remove_unit", description="Remove a proposed unit from your company")
    async def remove_unit(self, interaction: Interaction):
        player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
        if not player:
            await interaction.response.send_message("You don't have a Meta Campaign company", ephemeral=CustomClient().use_ephemeral)
            return
        units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.status == UnitStatus.PROPOSED).all()
        if not units:
            await interaction.response.send_message("You don't have any proposed units", ephemeral=CustomClient().use_ephemeral)
            return

        class UnitSelect(ui.Select):
            def __init__(self):
                options = [SelectOption(label=unit.name, value=unit.name) for unit in units]
                self.session = CustomClient().session
                super().__init__(placeholder="Select the unit to remove", options=options)

            async def callback(self, interaction: Interaction):
                unit: Unit_model = self.session.query(Unit_model).filter(Unit_model.name == self.values[0]).first()
                logger.debug(f"Removing unit {unit.name}")
                self.session.delete(unit)
                self.session.commit()
                CustomClient().queue.put_nowait((1, player))
                await interaction.response.send_message(f"Unit {unit.name} removed", ephemeral=CustomClient().use_ephemeral)

        view = View()
        view.add_item(UnitSelect())
        await interaction.response.send_message("Please select the unit to remove", view=view, ephemeral=CustomClient().use_ephemeral)
        
    @ac.command(name="deactivate", description="Deactivate a unit")
    async def deactivateunit(self, interaction: Interaction):
        logger.debug(f"Deactivating unit for {interaction.user.id}")
        player: Player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
        if not player:
            await interaction.response.send_message("You don't have a Meta Campaign company", ephemeral=CustomClient().use_ephemeral)
            return
        
        active_unit = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.active == True).first()
        if not active_unit:
            await interaction.response.send_message("You don't have any active units", ephemeral=CustomClient().use_ephemeral)
            return
                
        logger.debug(f"Deactivating unit with callsign {active_unit.callsign}")
        active_unit.active = False
        active_unit.status = UnitStatus.INACTIVE if active_unit.status == UnitStatus.ACTIVE else active_unit.status
        active_unit.callsign = None
        self.session.commit()
        await interaction.response.send_message(f"Unit with callsign {active_unit.callsign} deactivated", ephemeral=CustomClient().use_ephemeral)

    @ac.command(name="units", description="Display a list of all Units for a Player")
    @ac.describe(player="The player to deliver results for")
    async def units(self, interaction: Interaction, player: Member):
        player = self.session.query(Player).filter(Player.discord_id == player.id).first()
        if not player:
            await interaction.response.send_message("User doesn't have a Meta Campaign company", ephemeral=self.bot.use_ephemeral)
            return
        
        units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id).all()
        if not units:
            await interaction.response.send_message("User doesn't have any Units", ephemeral=CustomClient().use_ephemeral)
            return
        
        # Create a table with unit details
        unit_table = "| Unit Name | Callsign | Unit Type | Status |\n"
        unit_table += "|-----------|-----------|-----------|--------|\n"
        for unit in units:
            unit_table += f"| {unit.name} | {unit.callsign} | {unit.unit_type} | {unit.status} |\n"

        # Send the table to the user
        await interaction.response.send_message(f"Here are {player.name}'s Units:\n\n{unit_table}", ephemeral=CustomClient().use_ephemeral)

    #@ac.command(name="edit_proposed", description="Edit a proposed unit")
    async def edit_proposed(self, interaction: Interaction):
        # create a view with a select menu for all of the user's proposed units
        # when a unit is selected, create a view with a "rename" button and a unit type select menu
        # when the rename button is clicked, create a modal for the text input
        # when the unit type select menu is clicked, update the unit type
        class UnitSelect(ui.View):
            def __init__(self):
                super().__init__()
                self.session = CustomClient().session
                player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
                if not player:
                    raise Exception("You don't have a Meta Campaign company")
                units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id, Unit_model.status == UnitStatus.PROPOSED).all()
                if not units:
                    raise Exception("You don't have any proposed units") # we cannot use interaction in init because init cannot be async, so we raise with the message and catch it in the caller
                options = [SelectOption(label=unit.name, value=unit.name) for unit in units]
                self.select = ui.Select(placeholder="Select the unit to edit", options=options)
                self.select.callback = self.unit_select_callback
                self.add_item(self.select)

            async def unit_select_callback(self, interaction: Interaction):
                await interaction.response.defer(ephemeral=True)
                unit: Unit_model = self.session.query(Unit_model).filter(Unit_model.name == self.select.values[0]).first()
                if not unit:
                    raise Exception("Unit not found")
                self.edit_proposed_view = EditProposedView(unit)
                await interaction.followup.send("Please select the action to perform", view=self.edit_proposed_view, ephemeral=CustomClient().use_ephemeral)

        class EditProposedView(ui.View):
            def __init__(self, unit: Unit_model):
                super().__init__()
                self.unit = unit
                rename_button = ui.Button(label="Rename", style=ButtonStyle.primary, custom_id="rename")
                rename_button.callback = self.rename_callback
                self.add_item(rename_button)
                unit_type_select = ui.Select(placeholder="Select the unit type", options=[SelectOption(label=unit_type, value=unit_type) for unit_type in bot.config["unit_types"]])
                unit_type_select.callback = self.unit_type_select_callback
                self.add_item(unit_type_select)

            async def rename_callback(self, interaction: Interaction):
                # cannot defer if we want to send a modal
                modal = ui.Modal(title="Rename Unit", custom_id="rename_unit", components=[ui.InputText(label="New Name", custom_id="new_name", value=self.unit.name)])
                modal.callback = self.rename_modal_callback
                await interaction.response.send_modal(modal)

            async def rename_modal_callback(self, interaction: Interaction):
                new_name = interaction.data["components"][0]["components"][0]["value"]
                if len(new_name) > 32:
                    await interaction.response.send_message("Unit name is too long, please use a shorter name", ephemeral=CustomClient().use_ephemeral)
                    return
                if any(char in new_name for char in os.getenv("BANNED_CHARS", "")):
                    await interaction.response.send_message("Unit names cannot contain discord tags", ephemeral=CustomClient().use_ephemeral)
                    return
                self.unit.name = new_name
                self.session.commit()
                await interaction.response.send_message(f"Unit {self.unit.name} renamed to {new_name}", ephemeral=CustomClient().use_ephemeral)

            async def unit_type_select_callback(self, interaction: Interaction):
                new_unit_type = interaction.data["components"][0]["components"][0]["value"]
                self.unit.unit_type = new_unit_type
                self.session.commit()
                await interaction.response.send_message(f"Unit {self.unit.name} unit type changed to {new_unit_type}", ephemeral=CustomClient().use_ephemeral)

    @ac.command(name="rename", description="Rename a unit")
    async def rename(self, interaction: Interaction):
        logger.info("rename command invoked")
        player = self.session.query(Player).filter(Player.discord_id == interaction.user.id).first()
        if not player:
            logger.error("Player not found for rename command")
            await interaction.response.send_message("You don't have a Meta Campaign company", ephemeral=CustomClient().use_ephemeral)
            return
        units = self.session.query(Unit_model).filter(Unit_model.player_id == player.id).all()
        if not units:
            logger.error("No units found for rename command")
            await interaction.response.send_message("You don't have any units", ephemeral=CustomClient().use_ephemeral)
            return

        class UnitSelect(ui.Select):
            def __init__(self):
                options = [SelectOption(label=unit.name, value=unit.name) for unit in units]
                self.session = CustomClient().session
                super().__init__(placeholder="Select the unit to rename", options=options)

            async def callback(self, interaction: Interaction):
                self.unit: Unit_model = self.session.query(Unit_model).filter(Unit_model.name == self.values[0]).first()
                if not self.unit:
                    logger.error("Unit not found for rename command")
                    await interaction.response.send_message("Unit not found", ephemeral=CustomClient().use_ephemeral)
                    return

                modal = ui.Modal(title="Rename Unit", custom_id="rename_unit")
                modal.add_item(ui.TextInput(label="New Name", custom_id="new_name", placeholder=self.unit.name, max_length=32))
                modal.on_submit = self.rename_modal_callback
                await interaction.response.send_modal(modal)

            async def rename_modal_callback(self, interaction: Interaction):
                new_name = interaction.data["components"][0]["components"][0]["value"]
                logger.debug(f"New name: {new_name}")
                if self.session.query(Unit_model).filter(Unit_model.name == new_name, Unit_model.player_id == player.id).first():
                    logger.error(f"Unit with name {new_name} already exists for rename command")
                    await interaction.response.send_message("You already have a unit with that name", ephemeral=CustomClient().use_ephemeral)
                    return
                if len(new_name) > 32:
                    logger.error("Unit name is too long for rename command")
                    await interaction.response.send_message("Unit name is too long, please use a shorter name", ephemeral=CustomClient().use_ephemeral)
                    return
                if any(char in new_name for char in os.getenv("BANNED_CHARS", "")+":"): # : is banned to disable urls
                    logger.error("Unit name contains banned characters for rename command")
                    await interaction.response.send_message("Unit names cannot contain discord tags", ephemeral=CustomClient().use_ephemeral)
                    return
                if not new_name.isascii():
                    logger.error("Unit name is not ASCII for rename command")
                    await interaction.response.send_message("Unit names must be ASCII", ephemeral=CustomClient().use_ephemeral)
                    return
                self.unit.name = new_name
                self.session.commit()
                logger.info(f"Unit renamed to {new_name}")
                await interaction.response.send_message(f"Unit renamed to {new_name}", ephemeral=CustomClient().use_ephemeral)

        view = View()
        view.add_item(UnitSelect())
        await interaction.response.send_message("Please select the unit to rename", view=view, ephemeral=CustomClient().use_ephemeral)
bot: Bot = None
async def setup(_bot: Bot):
    global bot
    bot = _bot
    logger.info("Setting up Unit cog")
    await bot.add_cog(Unit(bot))

async def teardown():
    logger.info("Tearing down Unit cog")
    bot.remove_cog(Unit.__name__) # remove_cog takes a string, not a class
