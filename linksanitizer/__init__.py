from .link_sanitizer import LinkSanitizer

async def setup(bot):
    await bot.add_cog(LinkSanitizer(bot))