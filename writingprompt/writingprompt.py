import aiohttp
import random
import time as time_module
import discord
from discord.ext import tasks
from datetime import time, timezone, datetime
from typing import Optional, Literal
from redbot.core import commands, Config
from redbot.core.bot import Red


class WritingPrompt(commands.Cog):
    """Posts a daily writing prompt at 4pm UTC and gives LLM feedback."""

    # Cooldown in seconds between feedback requests per user
    FEEDBACK_COOLDOWN = 60

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7598204103)
        self.config.register_guild(
            channel=None,
            use_reddit=True,
            custom_prompts=[],
            # {message_id: {"prompt": str, "timestamp": iso8601_str}}
            prompt_messages={},
            daily_enabled=True,
        )
        self.config.register_global(
            openrouter_api_key=None,
        )

        # Runtime state (not persisted)
        self.processed_messages = set()
        self.user_cooldowns = {}

        self.default_prompts = [
            "A dragon knocks on your door, but it's not here to fight—it's here to borrow sugar.",
            "You find a diary written by your future self. The last entry reads: 'Whatever you do, don't trust them.'",
            "Every night at 3:17 AM, your phone receives a text from your own number.",
            "You wake up in a world where lying is physically impossible—and you're the last person who still can.",
            "The last human on Earth sits in a room. There is a knock at the door.",
            "Your pet cat suddenly speaks, and the first thing it says is 'They're coming.'",
            "You discover that the reflection in your mirror has been living its own life.",
            "A time traveler shows up and tells you to avoid a specific restaurant tomorrow.",
            "You receive a letter dated 100 years from now, and it's addressed to you by name.",
            "The universe is a simulation, and today the debug console appeared in your living room.",
            "You're a villain's sidekick, and today you realized the hero is actually the bad guy.",
            "An antique mirror shows the room as it was 50 years ago—but today, someone in the mirror waved at you.",
            "You find a library card for a building that doesn't exist—yet.",
            "Every song on the radio today is about you, and no one else seems to notice.",
            "The ocean recedes overnight, revealing structures no one has ever seen before.",
            "Your shadow starts moving independently of you. It seems friendly.",
            "You find a map that shows places that don't exist—until you fold it a certain way.",
            "A stranger hands you a key and says, 'You'll know the door when you see it.'",
            "You wake up with a tattoo you don't remember getting. It's a date: tomorrow.",
            "The rain today is warm and smells like honey. People are starting to change.",
        ]

    def cog_load(self):
        """Called when the cog is loaded. Start the loop."""
        self.daily_prompt.start()

    def cog_unload(self):
        """Called when the cog is unloaded. Stop the loop."""
        self.daily_prompt.cancel()

    # --- Helpers ---

    def _make_prompt_entry(self, prompt: str, dt: datetime) -> dict:
        """Create a Config-safe prompt entry dict."""
        return {
            "prompt": prompt,
            "timestamp": dt.astimezone(timezone.utc).isoformat(),
        }

    def _parse_prompt_entry(self, entry) -> tuple[str, datetime]:
        """
        Parse a stored prompt entry into (prompt_text, datetime).
        Handles legacy formats (plain strings or old tuples) gracefully.
        """
        # New format: dict with 'prompt' and 'timestamp' keys
        if isinstance(entry, dict):
            prompt_text = entry.get("prompt", "(No prompt context available)")
            ts_str = entry.get("timestamp")
            if ts_str:
                try:
                    prompt_date = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    prompt_date = datetime.now(timezone.utc)
            else:
                prompt_date = datetime.now(timezone.utc)
            return prompt_text, prompt_date

        # Legacy format: plain string
        if isinstance(entry, str):
            return entry, datetime.now(timezone.utc)

        # Legacy format: list/tuple [prompt, timestamp_str_or_something]
        if isinstance(entry, (list, tuple)) and len(entry) >= 1:
            return str(entry[0]), datetime.now(timezone.utc)

        return "(No prompt context available)", datetime.now(timezone.utc)

    # --- Core Logic ---

    async def fetch_reddit_prompt(self) -> Optional[str]:
        """Fetch the top daily [WP] post from r/WritingPrompts."""
        url = "https://www.reddit.com/r/WritingPrompts/top/.json?t=day&limit=10"
        headers = {"User-Agent": "Red-DiscordBot-WritingPromptCog/1.0"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        title = post["data"]["title"]
                        if title.startswith("[WP]"):
                            return title.replace("[WP]", "").strip()
                    if posts:
                        return posts[0]["data"]["title"]
        except Exception:
            return None
        return None

    async def get_prompt(self, guild: discord.Guild) -> str:
        """Get a prompt based on guild settings."""
        use_reddit = await self.config.guild(guild).use_reddit()

        if use_reddit:
            prompt = await self.fetch_reddit_prompt()
            if prompt:
                return prompt

        custom = await self.config.guild(guild).custom_prompts()
        if custom:
            return random.choice(custom)
        return random.choice(self.default_prompts)

    async def get_llm_feedback(self, prompt: str, writing: str) -> Optional[str]:
        """Send writing to OpenRouter's GPT-OSS-120B and get feedback."""
        api_key = await self.config.openrouter_api_key()
        if not api_key:
            return None

        system_msg = (
            "You are a constructive writing feedback assistant. "
            "A writer was given a writing prompt and wrote a response. "
            "Provide thoughtful, encouraging feedback on their writing. "
            "If the prompt seems unrelated to the user's response, assume it was a bug and focus on giving feedback on the writing itself."
            "Comment on strengths and areas for improvement, provide examples of how fixes could be implemented. "
            "Be specific and kind. Keep your response concise (under 500 words).\n\n"
            "Format your response for Discord: use bullet points or numbered lists for clarity, and use **bold text** for emphasis. "
            "Do NOT use markdown tables, headers, or code blocks, as they do not render well."
        )

        user_msg = (
            f"**Writing Prompt:** {prompt}\n\n"
            f"**Writer's Response:**\n{writing}\n\n"
            f"Please provide constructive feedback on this writing."
        )

        payload = {
            "model": "openai/gpt-oss-120b:free",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/red-discord-bot",
            "X-Title": "WritingPrompt Cog",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    # --- Daily Task ---

    @tasks.loop(time=time(hour=16, minute=0, tzinfo=timezone.utc))
    async def daily_prompt(self):
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            if not data.get("daily_enabled", True):
                continue
            channel_id = data.get("channel")
            if channel_id is None:
                continue
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            prompt = await self.get_prompt(guild)

            embed = discord.Embed(
                title="✍️ Daily Writing Prompt",
                description=prompt,
                color=discord.Color.brand_red(),
            )
            embed.set_footer(text="Reply with your writing, then react with ❓ for AI feedback!")

            try:
                msg = await channel.send(embed=embed)
                async with self.config.guild(guild).prompt_messages() as pms:
                    pms[str(msg.id)] = self._make_prompt_entry(prompt, msg.created_at)
                    if len(pms) > 7:
                        oldest = sorted(pms.keys(), key=int)[:-7]
                        for k in oldest:
                            del pms[k]
            except discord.Forbidden:
                pass

    @daily_prompt.before_loop
    async def before_daily_prompt(self):
        await self.bot.wait_until_ready()

    # --- Reaction Listener ---

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Listen for ❓ reactions on messages in the prompt channel."""
        if payload.emoji.name != "❓":
            return
        if payload.user_id == self.bot.user.id:
            return
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        config_channel_id = await self.config.guild(guild).channel()
        if channel.id != config_channel_id:
            return

        if payload.message_id in self.processed_messages:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        if message.author.id == self.bot.user.id:
            return
        if payload.user_id != message.author.id:
            return

        if not message.content or not message.content.strip():
            try:
                await message.reply(
                    "❌ I can't find any text content on this message to give feedback on. "
                    "Make sure I have the Message Content intent enabled."
                )
            except discord.Forbidden:
                pass
            return

        # Check per-user cooldown
        now = time_module.time()
        last_request = self.user_cooldowns.get(payload.user_id, 0)
        if now - last_request < self.FEEDBACK_COOLDOWN:
            remaining = int(self.FEEDBACK_COOLDOWN - (now - last_request))
            try:
                await message.reply(
                    f"⏳ Please wait {remaining} seconds before requesting feedback again."
                )
            except discord.Forbidden:
                pass
            return

        api_key = await self.config.openrouter_api_key()
        if not api_key:
            try:
                await message.reply(
                    "❌ No OpenRouter API key configured. "
                    "The bot owner needs to set one with `/writingprompt apikey`."
                )
            except discord.Forbidden:
                pass
            return

        # Mark as processed and set cooldown BEFORE the API call
        self.processed_messages.add(payload.message_id)
        self.user_cooldowns[payload.user_id] = now

        # --- Resolve the prompt context ---
        prompt_text = None
        prompt_date = datetime.now(timezone.utc)
        prompt_messages = await self.config.guild(guild).prompt_messages()

        # Attempt 1: user directly replied to a known prompt message
        if message.reference and message.reference.message_id:
            ref_id = str(message.reference.message_id)
            if ref_id in prompt_messages:
                prompt_text, prompt_date = self._parse_prompt_entry(prompt_messages[ref_id])

        # Attempt 2: fall back to the most recently posted prompt by timestamp
        if not prompt_text and prompt_messages:
            parsed = [self._parse_prompt_entry(e) for e in prompt_messages.values()]
            parsed.sort(key=lambda x: x[1], reverse=True)
            prompt_text, prompt_date = parsed[0]

        if not prompt_text:
            prompt_text = "(No prompt context available)"

        # Format the date for the thread name (e.g., "May 06, 2026")
        thread_name_date = prompt_date.strftime("%B %d, %Y")

        # Create a thread under the user's message
        try:
            thread = await message.create_thread(
                name=thread_name_date,
                auto_archive_duration=1440
            )
            processing_msg = await thread.send("🔍 Getting feedback on your writing...")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[WritingPrompt] Error creating thread: {e}")
            self.processed_messages.discard(payload.message_id)
            self.user_cooldowns.pop(payload.user_id, None)
            try:
                await message.reply(
                    "❌ I failed to create a feedback thread. "
                    "Please ensure I have permission to Create Public Threads."
                )
            except discord.Forbidden:
                pass
            return

        # Get LLM feedback
        feedback = await self.get_llm_feedback(prompt_text, message.content)

        if feedback:
            truncated = False
            if len(feedback) > 4000:
                feedback = feedback[:4000] + "..."
                truncated = True

            embed = discord.Embed(
                title="📝 Writing Feedback",
                description=feedback,
                color=discord.Color.green(),
            )
            footer = f"Feedback for {message.author.display_name}"
            if truncated:
                footer += " • Response was truncated"
            embed.set_footer(text=footer)

            try:
                await processing_msg.edit(content=None, embed=embed)
            except discord.HTTPException:
                await processing_msg.edit(
                    content=f"📝 **Writing Feedback:**\n{feedback[:1900]}"
                )
        else:
            self.processed_messages.discard(payload.message_id)
            self.user_cooldowns.pop(payload.user_id, None)
            try:
                await processing_msg.edit(
                    content="❌ Could not get feedback from the LLM. "
                    "The API may be down or rate-limited. Try again later."
                )
            except discord.Forbidden:
                pass

        # Remove the ❓ reaction
        try:
            await message.remove_reaction("❓", message.author)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    # --- Hybrid Commands ---

    @commands.hybrid_group()
    async def writingprompt(self, ctx: commands.Context):
        """Writing prompt configuration."""
        pass

    @writingprompt.command(name="apikey")
    @commands.is_owner()
    async def set_apikey(self, ctx: commands.Context, *, api_key: str):
        """Set the OpenRouter API key (bot owner only)."""
        await self.config.openrouter_api_key.set(api_key)

        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
            await ctx.send("✅ OpenRouter API key set!")
        else:
            await ctx.send("✅ OpenRouter API key set!", ephemeral=True)

    @writingprompt.command()
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for daily writing prompts."""
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f"✅ Daily writing prompts will be posted in {channel.mention}.")

    @writingprompt.command()
    async def reddit(self, ctx: commands.Context, enabled: bool):
        """Enable or disable fetching prompts from Reddit."""
        await self.config.guild(ctx.guild).use_reddit.set(enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Reddit prompt fetching **{status}**.")

    @writingprompt.command()
    async def add(self, ctx: commands.Context, *, prompt: str):
        """Add a custom writing prompt to the rotation."""
        async with self.config.guild(ctx.guild).custom_prompts() as prompts:
            prompts.append(prompt)
        await ctx.send(f"✅ Custom prompt added: *{prompt}*")

    @writingprompt.command()
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a custom prompt by its index."""
        async with self.config.guild(ctx.guild).custom_prompts() as prompts:
            if index < 1 or index > len(prompts):
                await ctx.send("❌ Invalid index. Use `/writingprompt list` to see indices.")
                return
            removed = prompts.pop(index - 1)
        await ctx.send(f"✅ Removed prompt: *{removed}*")

    @writingprompt.command(name="list")
    async def list_prompts(self, ctx: commands.Context):
        """List all custom prompts for this server."""
        custom = await self.config.guild(ctx.guild).custom_prompts()
        if not custom:
            await ctx.send("No custom prompts set. Using the default list (and Reddit if enabled).")
            return
        lines = [f"{i+1}. {p}" for i, p in enumerate(custom)]
        text = "\n".join(lines)
        if len(text) > 2000:
            text = text[:1997] + "..."
        await ctx.send(f"**Custom Prompts:**\n{text}")

    @writingprompt.command()
    async def pull(
        self,
        ctx: commands.Context,
        source: Literal["auto", "reddit", "custom", "default"] = "auto",
    ):
        """Pull a writing prompt on demand."""
        if source == "reddit":
            prompt = await self.fetch_reddit_prompt()
            if not prompt:
                await ctx.send("❌ Could not fetch from Reddit.")
                return
            source_label = "Reddit"
        elif source == "custom":
            custom = await self.config.guild(ctx.guild).custom_prompts()
            if not custom:
                await ctx.send("❌ No custom prompts set.")
                return
            prompt = random.choice(custom)
            source_label = "Custom List"
        elif source == "default":
            prompt = random.choice(self.default_prompts)
            source_label = "Default List"
        else:
            prompt = await self.get_prompt(ctx.guild)
            source_label = "Auto"

        embed = discord.Embed(
            title="✍️ Writing Prompt",
            description=prompt,
            color=discord.Color.brand_red(),
        )
        embed.set_footer(text=f"Source: {source_label}")
        msg = await ctx.send(embed=embed)

        # Save to history if posted in the configured channel
        configured_channel_id = await self.config.guild(ctx.guild).channel()
        if configured_channel_id and ctx.channel.id == configured_channel_id:
            async with self.config.guild(ctx.guild).prompt_messages() as pms:
                pms[str(msg.id)] = self._make_prompt_entry(prompt, msg.created_at)
                if len(pms) > 7:
                    oldest = sorted(pms.keys(), key=int)[:-7]
                    for k in oldest:
                        del pms[k]

    @writingprompt.command()
    async def post(self, ctx: commands.Context):
        """Manually post today's prompt to the configured channel."""
        channel_id = await self.config.guild(ctx.guild).channel()
        if channel_id is None:
            await ctx.send("❌ No channel set. Use `/writingprompt channel #channel` first.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send("❌ Configured channel not found.")
            return

        prompt = await self.get_prompt(ctx.guild)

        embed = discord.Embed(
            title="✍️ Daily Writing Prompt",
            description=prompt,
            color=discord.Color.brand_red(),
        )
        embed.set_footer(text="Reply with your writing, then react with ❓ for AI feedback!")

        try:
            msg = await channel.send(embed=embed)
            async with self.config.guild(ctx.guild).prompt_messages() as pms:
                pms[str(msg.id)] = self._make_prompt_entry(prompt, msg.created_at)
                if len(pms) > 7:
                    oldest = sorted(pms.keys(), key=int)[:-7]
                    for k in oldest:
                        del pms[k]
            await ctx.send(f"✅ Prompt posted to {channel.mention}!")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in that channel.")

    @writingprompt.command()
    async def settings(self, ctx: commands.Context):
        """Show current writing prompt settings."""
        data = await self.config.guild(ctx.guild).all()
        channel = ctx.guild.get_channel(data["channel"]) if data.get("channel") else None
        channel_text = channel.mention if channel else "Not set"
        reddit_text = "Enabled" if data.get("use_reddit") else "Disabled"
        custom_count = len(data.get("custom_prompts", []))
        api_key_set = bool(await self.config.openrouter_api_key())
        api_text = "Set ✅" if api_key_set else "Not set ❌"

        daily_text = "Enabled" if data.get("daily_enabled", True) else "Disabled"

        embed = discord.Embed(title="Writing Prompt Settings", color=discord.Color.brand_red())
        embed.add_field(name="Channel", value=channel_text, inline=True)
        embed.add_field(name="Daily Post", value=daily_text, inline=True) # <--- ADD THIS LINE
        embed.add_field(name="Reddit Fetch", value=reddit_text, inline=True)
        embed.add_field(name="Custom Prompts", value=str(custom_count), inline=True)
        embed.add_field(name="LLM API Key", value=api_text, inline=True)
        await ctx.send(embed=embed)


    @writingprompt.command(name="daily")
    async def toggle_daily(self, ctx: commands.Context, enabled: bool):
        """Enable or disable automatic daily prompting."""
        await self.config.guild(ctx.guild).daily_enabled.set(enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Daily prompt posting is now **{status}**.")
