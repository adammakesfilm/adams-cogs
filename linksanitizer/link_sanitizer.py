import re
import urllib.parse
import discord
from redbot.core import commands

class LinkSanitizer(commands.Cog):
    """Sanitizes social media links to remove tracking and improve embeds."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (prevents infinite loops) and DMs
        if message.author.bot or not message.guild:
            return

        content = message.content
        sanitized = False
        new_links = []
        
        # Simple regex to extract URLs from the message
        url_regex = r'(https?://[^\s]+)'
        urls = re.findall(url_regex, content)
        
        if not urls:
            return
            
        for url in urls:
            try:
                parsed = urllib.parse.urlparse(url)
                netloc = parsed.netloc.lower()
                
                # Setup domain replacements
                if netloc in ["twitter.com", "www.twitter.com", "x.com", "www.x.com"]:
                    parsed = parsed._replace(netloc="fxtwitter.com")
                elif netloc in ["instagram.com", "www.instagram.com"]:
                    parsed = parsed._replace(netloc="kkinstagram.com")
                elif netloc in ["facebook.com", "www.facebook.com"]:
                    parsed = parsed._replace(netloc="facebed.com")
                elif netloc in ["tumblr.com", "www.tumblr.com"]:
                    parsed = parsed._replace(netloc="fxtumblr.com")
                elif netloc in ["reddit.com", "www.reddit.com"]:
                    parsed = parsed._replace(netloc="vxreddit.com")
                elif netloc in ["deviantart.com", "www.deviantart.com"]:
                    parsed = parsed._replace(netloc="fxdeviantart.com")
                elif netloc in ["tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]:
                    parsed = parsed._replace(netloc="vxtiktok.com")
                elif netloc in ["pixiv.net", "www.pixiv.net"]:
                    parsed = parsed._replace(netloc="phixiv.net")
                    
                # Handle YouTube ?si= tracking parameter removal
                if netloc in ["youtube.com", "www.youtube.com", "youtu.be"]:
                    # Parse the query string into a dictionary
                    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                    if "si" in query_params:
                        del query_params["si"]
                        # Re-encode the URL parameters without the 'si' tag
                        new_query = urllib.parse.urlencode(query_params, doseq=True)
                        parsed = parsed._replace(query=new_query)
                
                # Reconstruct the URL
                new_url = urllib.parse.urlunparse(parsed)
                
                # If the URL was modified, add it to our list
                if new_url != url:
                    new_links.append(new_url)
                    sanitized = True
                    
            except Exception:
                # If a specific URL fails parsing, skip it and continue
                continue
                
        if sanitized and new_links:
            # Check if bot has permission to manage messages (needed to suppress embeds)
            permissions = message.channel.permissions_for(message.guild.me)
            if permissions.manage_messages:
                try:
                    # Suppress the broken/tracked embeds on the user's original message
                    await message.edit(suppress=True)
                except discord.HTTPException:
                    pass
            
            # Send the cleaned links as a reply
            reply_content = "🔗 **Fixed Links:**\n" + "\n".join(new_links)
            await message.reply(reply_content, mention_author=False)