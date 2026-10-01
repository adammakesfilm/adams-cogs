import re
import urllib.parse
import discord
import asyncio
from redbot.core import commands

class LinkSanitizer(commands.Cog):
    """Sanitizes social media links to remove tracking and improve embeds."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content
        sanitized = False
        new_links = []
        
        url_regex = r'(https?://[^\s]+)'
        urls = re.findall(url_regex, content)
        
        if not urls:
            return

        domain_map = {
            "twitter.com": "fxtwitter.com",
            "www.twitter.com": "fxtwitter.com",
            "x.com": "fxtwitter.com",
            "www.x.com": "fxtwitter.com",
            "instagram.com": "kkinstagram.com",
            "www.instagram.com": "kkinstagram.com",
            "facebook.com": "facebed.com",
            "www.facebook.com": "facebed.com",
            "tumblr.com": "fxtumblr.com",
            "www.tumblr.com": "fxtumblr.com",
            "reddit.com": "vxreddit.com",
            "www.reddit.com": "vxreddit.com",
            "deviantart.com": "fxdeviantart.com",
            "www.deviantart.com": "fxdeviantart.com",
            "pixiv.net": "phixiv.net",
            "www.pixiv.net": "phixiv.net",
            "tiktok.com": "tfxktok.com",
            "www.tiktok.com": "tfxktok.com",
            "vm.tiktok.com": "tfxktok.com",
            "vt.tiktok.com": "tfxktok.com"
        }
            
        for url in urls:
            try:
                parsed = urllib.parse.urlparse(url)
                netloc = parsed.netloc.lower()
                
                if netloc in domain_map:
                    parsed = parsed._replace(netloc=domain_map[netloc])
                    
                elif netloc in ["youtube.com", "www.youtube.com", "youtu.be"]:
                    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                    if "si" in query_params:
                        del query_params["si"]
                        new_query = urllib.parse.urlencode(query_params, doseq=True)
                        parsed = parsed._replace(query=new_query)
                
                new_url = urllib.parse.urlunparse(parsed)
                
                if new_url != url:
                    new_links.append(new_url)
                    sanitized = True
                    
            except Exception:
                continue
                
        if sanitized and new_links:
            # Send the cleaned links as a reply FIRST so the user isn't waiting
            reply_content = "🔗 **Fixed Links:**\n" + "\n".join(new_links)
            await message.reply(reply_content, mention_author=False)

            # Check if bot has permission to manage messages
            permissions = message.channel.permissions_for(message.guild.me)
            if permissions.manage_messages:
                # Wait 2 seconds to let Discord naturally generate the YouTube embed
                await asyncio.sleep(2)
                try:
                    await message.edit(suppress=True)
                except discord.HTTPException:
                    pass