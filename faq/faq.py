import discord
from redbot.core import commands, app_commands

class FAQ(commands.Cog):
    """FAQ - Display FAQ information in embeds"""

    def __init__(self, bot):
        self.bot = bot

        # Easy to add new FAQs - just add entries here!
        self.faq_data = {
            "darkmode": {
                "title": "Dark Mode FAQ",
                "description": "Everything you need to know about dark mode",
                "color": 0x2f3136,
                "fields": [
                    {
                        "name": "How do I enable dark mode?",
                        "value": "Go to User Settings > Appearance > Dark Mode",
                        "inline": False
                    },
                    {
                        "name": "Is dark mode available on mobile?",
                        "value": "Yes! Dark mode is available on both iOS and Android versions of Discord.",
                        "inline": False
                    },
                    {
                        "name": "Can I customize the dark mode theme?",
                        "value": "Yes! You can adjust colors in Appearance > Theme Colors",
                        "inline": False
                    }
                ],
                "footer": "Still having issues? Contact support!"
            },
            "verification": {
                "title": "Verification FAQ",
                "description": "How to get verified on our server",
                "color": 0x00bfff,
                "fields": [
                    {
                        "name": "How do I get verified?",
                        "value": "Read the rules in #rules and click the verification button",
                        "inline": False
                    },
                    {
                        "name": "What are the benefits?",
                        "value": "Access to all channels, ability to post images, and special roles!",
                        "inline": False
                    }
                ],
                "footer": "Contact mods if you have issues"
            },
            "commands": {
                "title": "Bot Commands FAQ",
                "description": "Common questions about bot commands",
                "color": 0x00ff00,
                "fields": [
                    {
                        "name": "How do I use slash commands?",
                        "value": "Type '/' and select a command from the menu",
                        "inline": False
                    },
                    {
                        "name": "Why isn't a command working?",
                        "value": "Make sure you have the required permissions and the bot is online",
                        "inline": False
                    }
                ],
                "footer": "Use /help for more info"
            }
        }

    @app_commands.command(name="faq", description="Get FAQ information about a specific topic")
    @app_commands.describe(topic="The FAQ topic you want information about")
    async def faq(self, interaction: discord.Interaction, topic: str):
        """Display FAQ information for a specific topic"""

        # Convert topic to lowercase for case-insensitive matching
        topic_lower = topic.lower()

        # Check if the topic exists in FAQ data
        if topic_lower not in self.faq_data:
            available_topics = ", ".join(self.faq_data.keys())
            embed = discord.Embed(
                title="FAQ Not Found",
                description=f"Sorry, I don't have an FAQ for '{topic}'.\n\nAvailable topics: {available_topics}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get the FAQ data
        faq = self.faq_data[topic_lower]

        # Create the embed
        embed = discord.Embed(
            title=faq["title"],
            description=faq["description"],
            color=faq["color"]
        )

        # Add all fields
        for field in faq["fields"]:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )

        # Add footer if specified
        if "footer" in faq:
            embed.set_footer(text=faq["footer"])

        # Send the embed
        await interaction.response.send_message(embed=embed)

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
