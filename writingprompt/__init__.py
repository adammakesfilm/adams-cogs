from .writingprompt import WritingPrompt

async def setup(bot):
    await bot.add_cog(WritingPrompt(bot))
