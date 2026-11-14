import re
import logging
import urllib.parse
import discord
import asyncio
from redbot.core import commands

log = logging.getLogger("red.linksanitizer")

YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be",
}

DOMAIN_MAP = {
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
    "vt.tiktok.com": "tfxktok.com",
}

class LinkSanitizer(commands.Cog):
    """Sanitizes social media links to remove tracking and improve embeds."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        urls = re.findall(r'(https?://[^\s<>]+)', message.content)
        if not urls:
            return

        new_links = []
        for url in urls:
            try:
                parsed = urllib.parse.urlparse(url)
                netloc = parsed.netloc.lower()

                if netloc in DOMAIN_MAP:
                    parsed = parsed._replace(netloc=DOMAIN_MAP[netloc])

                elif netloc in YOUTUBE_HOSTS:
                    pairs = [
                        (k, v) for k, v in urllib.parse.parse_qsl(
                            parsed.query, keep_blank_values=True)
                        if k != "si"
                    ]
                    parsed = parsed._replace(query=urllib.parse.urlencode(pairs))

                new_url = urllib.parse.urlunparse(parsed)
                if new_url != url:
                    new_links.append(new_url)

            except Exception:
                log.exception("Failed to sanitize URL: %s", url)

        if not new_links:
            return

        await message.reply("🔗 **Fixed Links:**\n" + "\n".join(new_links),
                            mention_author=False)

        permissions = message.channel.permissions_for(message.guild.me)
        if permissions.manage_messages:
            await asyncio.sleep(2)
            try:
                await message.edit(suppress=True)
            except discord.HTTPException:
                log.warning("Could not suppress embeds on message %s", message.id)
