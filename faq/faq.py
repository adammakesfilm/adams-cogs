import discord
from redbot.core import commands, app_commands

class FAQ(commands.Cog):
    """FAQ - Display FAQ information in embeds"""

    def __init__(self, bot):
        self.bot = bot

        # Easy to add new FAQs - just add entries here!
        self.faq_data = {
            "armorstand": {
                "title": "Armor Statues",
                "thumbnail": "https://i.imgur.com/8UpGiwA.png",
                "description": "To obtain the armor statues book, sign a book and quill with the title `Statues`. You can run the in-game command `/trigger as_help` for more info. Here is an in-depth beginner tutorial on how to use the Armor Statues book from ZombieCleo: https://youtu.be/nV9-_RacnoI\n\nYou can also use [Armorposer](https://modrinth.com/mod/armor-poser) for a GUI by shift-clicking on an armor stand."
            },
            "mobheads": {
                "title": "Mob Heads",
                "thumbnail": "https://i.imgur.com/CsYUv8G.png",
                "description": "Each mob has a chance of dropping its head. You can see all the drop rates here: https://link-here.com\n\nThe heads will also make the appropriate mob's sound when placed on top of a powered note block."
            },
            "hud": {
                "title": "HUD Display",
                "thumbnail": "https://i.imgur.com/XBhpZmz.png",
                "description": "Adds your XYZ Coords and a 24hr clock to your actionbar. To toggle it on and off use `/trigger ch_toggle`."
            },
            "duraping": {
                "title": "Duraping",
                "thumbnail": "https://i.imgur.com/VGfXFBo.png",
                "description": "Get notified when you damage an item with 10% or less durability. You can customize what items it works for and how it notifies you using `/trigger duraPing`."
            },
            "playerme": {
                "title": "Playerme",
                "thumbnail": "https://i.imgur.com/IGVAVEG.png",
                "description": "A server-side AFK clicker that also allows you to AFK on the server without being on your PC.\n\n**Commands:**\n`/playerme attack <interval>` - The player performs the left click equivalent action. The interval is in ticks.\n`/playerme use` - The player performs the right click equivalent action. The interval is in ticks.\n`/playerme shadow` - This will replace you with a fake player on the server. It will continue to perform any scheduled actions that you have set.\n`/playerme stop` - The player stops moving and cancels all actions the player is doing."
            },
            "craft tweaks": {
                "title": "Crafting Tweaks",
                "thumbnail": "https://i.imgur.com/phxPXzz.png",
                "description": "Here are all the crafting changes on the server:\n• Turn slabs and stairs back into blocks\n• Craft 12 trapdoors instead of 3\n• Craft 4 bark blocks instead of 3\n• Craft 8 stair blocks instead of 4\n• Craft 4 brick blocks instead of 1\n• Craft a dispenser using sticks and string with a dropper\n• You can craft nametags\n• Universal Dyeing ([demo video](https://www.youtube.com/watch?v=lfcwKXhjC9Y&t=610s))\n\nAll crafting recipes have been unlocked upon logging into the server for the first time, so these are all in your crafting book."
            },
            "spectator": {
                "title": "Spectator Mode",
                "thumbnail": "https://i.imgur.com/ueyPL1x.png",
                "description": "Enter spectator mode whenever you'd like using the command `/cs`. Fly around as much as you'd like and use `/cs` again to return to survival mode.\n\nTo enable night vision, run `/trigger night_vision`. This effect will go away when you return to survival.\n\n*Note: It will save the location you were in when you used the command so you will tp back to where you were. You cannot use the command when mobs are around either.*"
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
                "title": "Mini-Blocks",
                "thumbnail": "https://i.imgur.com/c15xzm4.png",
                "description": "Use a stonecutter to craft certain blocks into mini blocks (heads with textures resembling blocks).\nYou can see all blocks that have a \"mini-block\" variant here:"
            }
        }

    # Autocomplete function
    async def faq_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        # This filters the keys based on what the user is typing
        return [
            app_commands.Choice(name=topic, value=topic)
            for topic in self.faq_data.keys()
            if current.lower() in topic.lower()
        ][:25] # Discord limits autocomplete to 25 items

    @app_commands.command(name="faq", description="Get FAQ information about a specific topic")
    @app_commands.describe(topic="The FAQ topic you want information about")
    async def faq(self, interaction: discord.Interaction, topic: str):
        """Display FAQ information for a specific topic"""

        # Convert topic to lowercase for case-insensitive matching
        topic_lower = topic.lower()

        # Special case for topics with spaces
        if topic_lower in ["flipping cactus", "craft tweaks"]:
            if topic_lower in self.faq_data:
                faq = self.faq_data[topic_lower]
                embed = self._create_embed(faq)
                await interaction.response.send_message(embed=embed)
                return

        # Check if the topic exists in FAQ data
        if topic_lower not in self.faq_data:
            available_topics = ", ".join(self.faq_data.keys())
            embed = discord.Embed(
                title="FAQ Not Found",
                description=f"Sorry, I don't have an FAQ for '{topic}'.\n\nAvailable topics:\n{available_topics}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get the FAQ data
        faq = self.faq_data[topic_lower]

        # Create and send the embed
        embed = self._create_embed(faq)
        await interaction.response.send_message(embed=embed)

    def _create_embed(self, faq):
        """Helper method to create a simple embed from FAQ data"""
        # Use a consistent color for all FAQ embeds
        embed = discord.Embed(
            title=faq["title"],
            description=faq["description"],
            color=0xFFD74E
        )

        # Add thumbnail if specified
        if "thumbnail" in faq and faq["thumbnail"]:
            embed.set_thumbnail(url=faq["thumbnail"])

        return embed

    @app_commands.command(name="faqlist", description="List all available FAQ topics")
    async def faq_list(self, interaction: discord.Interaction):
        """Display a list of all available FAQ topics"""

        # Create embed with all topics
        embed = discord.Embed(
            title="Available FAQ Topics",
            description="Use /faq <topic> to get information about a specific topic:",
            color=0x5865F2  # Discord blue
        )

        # Add each topic as a field
        for topic, data in self.faq_data.items():
            embed.add_field(
                name=f"/faq {topic}",
                value=data["title"],
                inline=True
            )

        embed.set_footer(text="Tip: Use /faq <topic> to get detailed information")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FAQ(bot))
