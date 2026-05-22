from .faq import FAQ


async def setup(bot):
    await bot.add_cog(FAQ(bot))
