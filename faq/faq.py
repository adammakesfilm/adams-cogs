import discord
from redbot.core import commands, app_commands
from typing import List

class FAQ(commands.Cog):
    """FAQ - Display FAQ information in embeds"""

    def __init__(self, bot):
        self.bot = bot

        # --- FAQ Data ---
        self.faq_data = {
            "armorstand": {
                "title": "Armor Statues",
                "thumbnail": "https://i.imgur.com/8UpGiwA.png",
                "description": "To obtain the armor statues book, sign a book and quill with the title `Statues`. You can run the in-game command `/trigger as_help` for more info. Here is an in-depth beginner tutorial on how to use the Armor Statues book from ZombieCleo: https://youtu.be/nV9-_RacnoI\n\nYou can also use [Armorposer](https://modrinth.com/mod/armor-poser) mod for a GUI by shift-clicking on an armor stand."
            },
            "mobheads": {
                "title": "Mob Heads",
                "thumbnail": "https://i.imgur.com/CsYUv8G.png",
                "description": "Each mob has a chance of dropping its head. You can see all the drop rates here: https://link.me/qcraftmobs\n\nThe heads will also make the appropriate mob's sound when placed on top of a powered note block."
            },
            "hud": {
                "title": "HUD Display",
                "thumbnail": "https://i.imgur.com/XBhpZmz.png",
                "description": "Adds your XYZ Coords and a 24hr clock to your actionbar. To toggle it on and off use `/trigger ch_toggle`."
            },
            "duraping": {
                "title": "DuraPing",
                "thumbnail": "https://i.imgur.com/VGfXFBo.png",
                "description": "Get notified when you damage an item with 10% or less durability. You can customize what items it works for and how it notifies you using `/trigger duraPing`."
            },
            "playerme": {
                "title": "PlayerMe",
                "thumbnail": "https://i.imgur.com/IGVAVEG.png",
                "description": (
                    "A server-side AFK clicker that also allows you to AFK on the server without being on your PC.\n\n"
                    "**Commands:**\n"
                    "`/playerme attack <interval>` - The player performs the left click equivalent action. The interval is in ticks.\n"
                    "`/playerme use` - The player performs the right click equivalent action. The interval is in ticks.\n"
                    "`/playerme shadow` - This will replace you with a fake player on the server. It will continue to perform any scheduled actions that you have set.\n"
                    "`/playerme stop` - The player stops moving and cancels all actions the player is doing."
                )
            },
            "craft tweaks": {
                "title": "Craft Tweaks",
                "thumbnail": "https://i.imgur.com/phxPXzz.png",
                "description": (
                    "Here are all the crafting changes on the server:\n"
                    "• Turn slabs and stairs back into blocks\n"
                    "• Craft 12 trapdoors instead of 3\n"
                    "• Craft 4 bark blocks instead of 3\n"
                    "• Craft 8 stair blocks instead of 4\n"
                    "• Craft 4 brick blocks instead of 1\n"
                    "• Craft a dispenser using sticks and string with a dropper\n"
                    "• You can craft nametags using a iron nugget and paper\n"
                    "• Craft coral blocks using coral plants\n"
                    "• Craft a sponge using yellow dye, slime balls, and a kelp block\n"
                    "• Universal Dyeing ([demo video](https://www.youtube.com/watch?v=lfcwKXhjC9Y&t=610s))\n\n"
                    "All crafting recipes have been unlocked upon logging into the server for the first time, so these are all in your crafting book."
                )
            },
            "spectator": {
                "title": "Spectator Mode",
                "thumbnail": "https://i.imgur.com/ueyPL1x.png",
                "description": (
                    "Enter spectator mode whenever you'd like using the command `/cs`. Fly around as much as you'd like and use `/cs` again to return to survival mode.\n\n"
                    "To enable night vision, run `/trigger night_vision`. This effect will go away when you return to survival.\n\n"
                    "*Note: It will save the location you were in when you used the command so you will tp back to where you were. You cannot use the command when mobs are around either.*"
                )
            },
            "flipping cactus": {
                "title": "Flipping Cactus",
                "thumbnail": "https://i.imgur.com/YAB3ldn.png",
                "description": "Players can flip and rotate blocks by right clicking on a block with a cactus. Doesn't cause block updates when rotated/flipped.\n\nApplies to pistons, observers, droppers, repeaters, stairs, glazed terracotta etc..."
            },
            "playerhead": {
                "title": "Player Heads",
                "thumbnail": "https://i.imgur.com/bQTyCjW.png",
                "description": "A player will drop their head when killed by another player. The item displays who the killer is. The head will be from the skin worn at the time of death. This means you can wear skins with unique heads for use in decoration."
            },
            "miniblocks": {
                "title": "Miniblocks",
                "thumbnail": "https://i.imgur.com/CsYUv8G.png",
                "description": "Use a stonecutter to craft certain blocks into mini blocks (heads with textures resembling blocks).\nYou can see all blocks that have a \"mini-block\" variant here: https://link.me/qcraftminiblocks"
            },
            "deepslate": {
                "title": "Renewable Deepslate",
                "thumbnail": "https://i.imgur.com/3PnDjtN.png",
                "description": "Lava and water generate deepslate and cobbled deepslate instead below y0. This means you can create infinite deepslate by building a cobblestone generator below y0."
            },
            "custom portals": {
                "title": "Custom Portals",
                "thumbnail": "https://i.imgur.com/wXy2uUK.png",
                "description": "Ignite nether portals of any shape and size you like, or using crying obsidian in the portal frame."
            },
            "named items": {
                "title": "Named Items don't despawn",
                "thumbnail": "https://i.imgur.com/IGVAVEG.png",
                "description": "Items when named will not despawn, so it's important that you name your gear so that it doesn't despawn if you die with it. This also means you can name items and use them as decorations without worrying about them despawning."
            },
            "dragon drops": {
                "title": "Dragon Drops",
                "thumbnail": "https://i.imgur.com/i00YUP7.png",
                "description": "When the Ender Dragon is killed, it drops both an elytra and an egg. This allows players to obtain elytra without having to find an end city and also allows them to obtain multiple eggs if they want."
            },
            "back to blocks": {
                "title": "Back to Blocks",
                "thumbnail": "https://i.imgur.com/kcJSf0G.png",
                "description": "Allows you to craft full blocks from stairs and slabs. This is especially useful for building and storage purposes. You can also use it to turn mini-blocks back into their full block variants."
            },
            "master cutter": {
                "title": "Master Cutter",
                "thumbnail": "https://i.imgur.com/3oUMPl4.png",
                "description": "Custom datapack that adds over 500 new recipies to the stonecutter. It also provides some quality-of-life features, such as the possibility to switch between variants of the same block (eg. form polished to base), the ability to cut deepslate and stone into their cobbled forms and/or direct derivatives and so much more! Discover all the new recipes and features by using the stonecutter or by looking at the datapack's project page: https://modrinth.com/project/DuUMFIfX"
            }
        }

    # --- Autocomplete Logic ---
    async def faq_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=topic, value=topic)
            for topic in self.faq_data.keys()
            if current.lower() in topic.lower()
        ][:25]

    # --- Commands ---
    @app_commands.command(name="faq", description="Get FAQ information about a specific topic")
    @app_commands.autocomplete(topic=faq_autocomplete)
    @app_commands.describe(topic="The FAQ topic you want information about")
    async def faq(self, interaction: discord.Interaction, topic: str):
        if topic.lower() not in self.faq_data:
            await interaction.response.send_message("Topic not found.", ephemeral=True)
            return

        embed = self._create_embed(self.faq_data[topic.lower()])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="faqlist", description="List all available FAQ topics")
    async def faq_list(self, interaction: discord.Interaction):
        topic_list = ", ".join(self.faq_data.keys())
        embed = discord.Embed(title="Available FAQ Topics", description=topic_list, color=0x5865F2)
        await interaction.response.send_message(embed=embed)

    # --- Helper Methods ---
    def _create_embed(self, data):
        embed = discord.Embed(
            title=data["title"], 
            description=data["description"], 
            color=0xFFD74E

        )
        if "thumbnail" in data:
            embed.set_thumbnail(url=data["thumbnail"])
        return embed

async def setup(bot):
    await bot.add_cog(FAQ(bot))
