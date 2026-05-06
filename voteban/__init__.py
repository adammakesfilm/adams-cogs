from .voteban import Voteban

async def setup(bot):
    await bot.add_cog(Voteban(bot))
