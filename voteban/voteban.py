import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import pagify
from datetime import datetime, timedelta
import asyncio
from discord import app_commands
from discord.ui import View, Button, button

class VotebanView(View):
    """Button view for anonymous voting"""

    def __init__(self, vote_id, cog):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.cog = cog

    @button(label='Vote to Ban', style=discord.ButtonStyle.danger, emoji='🔨')
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle ban vote button"""
        await self.cog.handle_vote_button(interaction, self.vote_id, 'ban')

    @button(label='Vote to Keep', style=discord.ButtonStyle.success, emoji='🛡️')
    async def keep_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle keep vote button"""
        await self.cog.handle_vote_button(interaction, self.vote_id, 'keep')

    @button(label='Check Status', style=discord.ButtonStyle.secondary, emoji='📊')
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle status check button"""
        await self.cog.handle_status_button(interaction, self.vote_id)

class Voteban(commands.Cog):
    """Public starter voting system to ban users with quorum requirement"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, 
            identifier=1234567890,  # Unique identifier for your cog
            force_registration=True
        )

        # Define config structure
        self.config.register_global(
            active_votes={},  # {vote_id: {target_id, starter_id, starter_name, reason, start_time, votes: {user_id: vote}, message_id, guild_id, channel_id}}
            immunities={},    # {user_id: immunity_end_time}
            cooldowns={},     # {user_id: cooldown_end_time}
            vote_counter=0    # To generate unique vote IDs
        )

        self.vote_check_task = self.bot.loop.create_task(self.check_votes())

    def cog_unload(self):
        self.vote_check_task.cancel()

    async def check_votes(self):
        """Background task to check for completed votes"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.process_completed_votes()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                print(f"Error in vote check task: {e}")
                await asyncio.sleep(60)

    async def process_completed_votes(self):
        """Process votes that have completed"""
        async with self.config.active_votes() as votes:
            current_time = datetime.now()
            completed_votes = []

            for vote_id, vote_data in votes.items():
                start_time = datetime.fromisoformat(vote_data['start_time'])
                if current_time - start_time >= timedelta(hours=24):
                    completed_votes.append(vote_id)

            for vote_id in completed_votes:
                await self.finalize_vote(vote_id, votes.pop(vote_id))

    async def finalize_vote(self, vote_id, vote_data):
        """Finalize a vote and take action based on results"""
        guild = self.bot.get_guild(vote_data['guild_id'])
        if not guild:
            return

        target = guild.get_member(vote_data['target_id'])
        if not target:
            return

        votes = vote_data['votes']
        ban_votes = sum(1 for v in votes.values() if v == 'ban')
        total_votes = len(votes)

        if total_votes == 0:
            return  # No votes, nothing to do

        # Calculate quorum - need 1/3 of server members
        # Filter out bots from member count
        human_members = len([m for m in guild.members if not m.bot])
        required_votes = max(1, int(human_members / 3))

        ban_percentage = (ban_votes / total_votes) * 100

        # Check quorum and vote percentage
        async with self.config.immunities() as immunities:
            # Check if quorum is met
            quorum_met = total_votes >= required_votes

            if quorum_met and ban_percentage > 50:
                # Ban the user - quorum met and majority voted to ban
                try:
                    await guild.ban(target, reason=f"Ban vote passed by {vote_data['starter_name']}: {vote_data['reason']} ({ban_votes}/{total_votes} votes)")
                    # Remove immunity if they had any
                    if str(target.id) in immunities:
                        del immunities[str(target.id)]
                    result = "BANNED"
                    result_emoji = "🔨"
                    color = 0xFF0000
                except discord.Forbidden:
                    result = "FAILED (Missing Permissions)"
                    result_emoji = "⚠️"
                    color = 0xFFA500
            else:
                # Grant immunity for 6 months if quorum was met but vote failed
                if quorum_met:
                    immunity_end = (datetime.now() + timedelta(days=180)).isoformat()
                    immunities[str(target.id)] = immunity_end
                    result = "KEPT (Immunity Granted)"
                    result_emoji = "🛡️"
                    color = 0x00FF00
                else:
                    # Quorum not met - no immunity granted, no cooldown
                    result = "FAILED (Quorum Not Met)"
                    result_emoji = "📊"
                    color = 0x808080

        # Remove cooldown if quorum wasn't met
        if not quorum_met:
            async with self.config.cooldowns() as cooldowns:
                if str(vote_data['starter_id']) in cooldowns:
                    del cooldowns[str(vote_data['starter_id'])]

        # Update the original message to show results
        if 'message_id' in vote_data:
            try:
                channel = guild.get_channel(vote_data['channel_id'])
                if channel:
                    message = await channel.fetch_message(vote_data['message_id'])

                    embed = discord.Embed(
                        title="🗳️ Ban Vote Completed",
                        description=f"Vote against {target.mention}",
                        color=color
                    )

                    embed.add_field(name="Result", value=f"**{result}** {result_emoji}", inline=False)
                    embed.add_field(name="Votes", value=f"🔨 {ban_votes} vs 🛡️ {total_votes - ban_votes}", inline=False)
                    embed.add_field(name="Percentage", value=f"{ban_percentage:.1f}% voted to ban", inline=False)
                    embed.add_field(name="Quorum", value=f"Required: {required_votes} votes • Actual: {total_votes} votes", inline=False)
                    embed.add_field(name="Starter", value=f"{vote_data['starter_name']} (ID: {vote_data['starter_id']})", inline=False)
                    embed.add_field(name="Reason", value=vote_data['reason'], inline=False)
                    embed.set_footer(text=f"Vote ID: {vote_id}")

                    view = VotebanView(vote_id, self)
                    for child in view.children:
                        child.disabled = True

                    await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Error updating vote completion message: {e}")

    async def handle_vote_button(self, interaction: discord.Interaction, vote_id: str, choice: str):
        """Handle anonymous voting via buttons"""
        async with self.config.active_votes() as votes:
            if vote_id not in votes:
                await interaction.response.send_message("Invalid vote ID or the vote has ended.", ephemeral=True)
                return

            vote_data = votes[vote_id]

            # Check if vote is still active
            start_time = datetime.fromisoformat(vote_data['start_time'])
            if datetime.now() - start_time >= timedelta(hours=24):
                await interaction.response.send_message("This vote has already ended.", ephemeral=True)
                return

            # Cast the vote (anonymous)
            previous_vote = vote_data['votes'].get(str(interaction.user.id))
            vote_data['votes'][str(interaction.user.id)] = choice

            # Create response based on whether they changed their vote
            if previous_vote:
                response_text = f"Your vote has been changed from {previous_vote} to {choice}."
            else:
                response_text = f"Your vote has been cast anonymously for {choice}."

            await interaction.response.send_message(response_text, ephemeral=True)

            # Update the message embed with current vote count
            await self.update_vote_message(interaction, vote_id, vote_data)

    async def handle_status_button(self, interaction: discord.Interaction, vote_id: str):
        """Handle status check button"""
        async with self.config.active_votes() as votes:
            if vote_id not in votes:
                await interaction.response.send_message("Invalid vote ID or the vote has ended.", ephemeral=True)
                return

            vote_data = votes[vote_id]
            start_time = datetime.fromisoformat(vote_data['start_time'])
            remaining = timedelta(hours=24) - (datetime.now() - start_time)

            if remaining.total_seconds() <= 0:
                remaining_str = "Voting has ended"
            else:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                remaining_str = f"{hours}h {minutes}m remaining"

            total_votes = len(vote_data['votes'])
            ban_votes = sum(1 for v in vote_data['votes'].values() if v == 'ban')

            # Calculate quorum status
            guild = self.bot.get_guild(vote_data['guild_id'])
            human_members = len([m for m in guild.members if not m.bot])
            required_votes = max(1, int(human_members / 3))
            quorum_status = f"{total_votes}/{required_votes} votes needed"

            embed = discord.Embed(
                title="📊 Vote Status",
                description=f"Current vote progress",
                color=0x00BFFF
            )

            embed.add_field(name="Target", value=f"<@{vote_data['target_id']}>", inline=False)
            embed.add_field(name="Starter", value=f"{vote_data['starter_name']}", inline=True)
            embed.add_field(name="Reason", value=vote_data['reason'], inline=True)
            embed.add_field(name="Time Remaining", value=remaining_str, inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
            embed.add_field(name="Quorum Status", value=quorum_status, inline=True)
            embed.add_field(name="Vote Breakdown", value=f"🔨 Ban: {ban_votes}\n🛡️ Keep: {total_votes - ban_votes}", inline=False)

            if total_votes > 0:
                percentage = (ban_votes / total_votes) * 100
                embed.add_field(name="Current Percentage", value=f"{percentage:.1f}% voting to ban", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def update_vote_message(self, interaction: discord.Interaction, vote_id: str, vote_data: dict):
        """Update the vote message with current stats"""
        try:
            message = await interaction.channel.fetch_message(vote_data['message_id'])

            total_votes = len(vote_data['votes'])
            ban_votes = sum(1 for v in vote_data['votes'].values() if v == 'ban')
            start_time = datetime.fromisoformat(vote_data['start_time'])
            remaining = timedelta(hours=24) - (datetime.now() - start_time)

            if remaining.total_seconds() <= 0:
                remaining_str = "Voting has ended"
            else:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                remaining_str = f"{hours}h {minutes}m remaining"

            # Calculate quorum status
            guild = self.bot.get_guild(vote_data['guild_id'])
            human_members = len([m for m in guild.members if not m.bot])
            required_votes = max(1, int(human_members / 3))
            quorum_status = f"{total_votes}/{required_votes} votes needed"

            embed = discord.Embed(
                title="🗳️ Ban Vote Started",
                description=f"Vote to ban <@{vote_data['target_id']}> from the server",
                color=0xFF4500
            )

            embed.add_field(name="Started By", value=f"{vote_data['starter_name']}", inline=False)
            embed.add_field(name="Reason", value=vote_data['reason'], inline=False)
            embed.add_field(name="Time Remaining", value=remaining_str, inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
            embed.add_field(name="Quorum", value=quorum_status, inline=True)
            embed.add_field(name="Current Results", value=f"🔨 {ban_votes} vs 🛡️ {total_votes - ban_votes}", inline=False)

            if total_votes > 0:
                percentage = (ban_votes / total_votes) * 100
                embed.add_field(name="Percentage", value=f"{percentage:.1f}% voting to ban", inline=False)

            embed.add_field(name="Anonymous Voting", value="Your vote is completely anonymous. Press the buttons below to cast your vote.", inline=False)
            embed.set_footer(text=f"Vote ID: {vote_id}")

            view = VotebanView(vote_id, self)
            await message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Error updating vote message: {e}")

    @app_commands.command(name='voteban', description='Start a public vote to ban a user with a reason')
    @app_commands.describe(
        target='The user to start a ban vote against',
        reason='The reason for proposing the ban (will be displayed publicly)'
    )
    async def voteban_slash(self, interaction: discord.Interaction, target: discord.Member, reason: str):
        """Start a public vote to ban a user using slash command"""
        # Validate reason length
        if len(reason) < 10:
            await interaction.response.send_message("Please provide a detailed reason (at least 10 characters).", ephemeral=True)
            return

        if len(reason) > 500:
            await interaction.response.send_message("Reason is too long. Please keep it under 500 characters.", ephemeral=True)
            return

        # Defer the response since we need to do async operations
        await interaction.response.defer()

        # Check if user is on cooldown
        async with self.config.cooldowns() as cooldowns:
            if str(interaction.user.id) in cooldowns:
                cooldown_end = datetime.fromisoformat(cooldowns[str(interaction.user.id)])
                if datetime.now() < cooldown_end:
                    remaining = cooldown_end - datetime.now()
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    await interaction.followup.send(f"You can start another ban vote in {days} days and {hours} hours.")
                    return

        # Check if target has immunity
        async with self.config.immunities() as immunities:
            if str(target.id) in immunities:
                immunity_end = datetime.fromisoformat(immunities[str(target.id)])
                if datetime.now() < immunity_end:
                    remaining = immunity_end - datetime.now()
                    days = remaining.days
                    await interaction.followup.send(f"This user has immunity for another {days} days.")
                    return

        # Check if there's already an active vote for this user in this server
        async with self.config.active_votes() as votes:
            for vote_data in votes.values():
                if vote_data['guild_id'] == interaction.guild.id and vote_data['target_id'] == target.id:
                    await interaction.followup.send("There is already an active ban vote for this user.")
                    return

            # Create new vote
            async with self.config.vote_counter() as counter:
                self.config.vote_counter.set(counter + 1)
                vote_id = str(counter)

            vote_data = {
                'guild_id': interaction.guild.id,
                'channel_id': interaction.channel.id,
                'target_id': target.id,
                'starter_id': interaction.user.id,
                'starter_name': interaction.user.display_name,
                'reason': reason,
                'start_time': datetime.now().isoformat(),
                'votes': {str(interaction.user.id): 'ban'},  # Starter automatically votes to ban
                'message_id': None  # Will be set after sending the message
            }

            votes[vote_id] = vote_data

        # Set cooldown for the starter
        async with self.config.cooldowns() as cooldowns:
            cooldown_end = (datetime.now() + timedelta(days=180)).isoformat()
            cooldowns[str(interaction.user.id)] = cooldown_end

        # Calculate quorum for display
        human_members = len([m for m in interaction.guild.members if not m.bot])
        required_votes = max(1, int(human_members / 3))

        # Create and send the embed with buttons
        embed = discord.Embed(
            title="🗳️ Ban Vote Started",
            description=f"Vote to ban {target.mention} from the server",
            color=0xFF4500
        )

        embed.add_field(name="Started By", value=f"{interaction.user.display_name}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Time Remaining", value="24h", inline=True)
        embed.add_field(name="Total Votes", value="1", inline=True)
        embed.add_field(name="Quorum Required", value=f"{required_votes} votes needed (1/3 of {human_members} members)", inline=False)
        embed.add_field(name="Current Results", value="🔨 1 vs 🛡️ 0", inline=False)
        embed.add_field(name="Anonymous Voting", value="Your vote is completely anonymous. Use the buttons below to cast your vote.", inline=False)
        embed.set_footer(text=f"Vote ID: {vote_id}")

        view = VotebanView(vote_id, self)
        message = await interaction.followup.send(embed=embed, view=view)

        # Store the message ID for updating
        async with self.config.active_votes() as votes:
            votes[vote_id]['message_id'] = message.id

    @app_commands.command(name='votestatus', description='Check the status of a ban vote')
    @app_commands.describe(vote_id='The vote ID to check (optional, leave empty for all active votes)')
    async def votestatus_slash(self, interaction: discord.Interaction, vote_id: str = None):
        """Check the status of a ban vote using slash command"""
        await interaction.response.defer()

        async with self.config.active_votes() as votes:
            if vote_id:
                if vote_id not in votes:
                    await interaction.followup.send("Invalid vote ID or the vote has ended.")
                    return

                vote_data = votes[vote_id]
                start_time = datetime.fromisoformat(vote_data['start_time'])
                remaining = timedelta(hours=24) - (datetime.now() - start_time)

                if remaining.total_seconds() <= 0:
                    remaining_str = "Voting has ended"
                else:
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    remaining_str = f"{hours}h {minutes}m remaining"

                total_votes = len(vote_data['votes'])
                ban_votes = sum(1 for v in vote_data['votes'].values() if v == 'ban')

                # Calculate quorum status
                guild = self.bot.get_guild(vote_data['guild_id'])
                human_members = len([m for m in guild.members if not m.bot])
                required_votes = max(1, int(human_members / 3))
                quorum_status = f"{total_votes}/{required_votes} votes needed"

                embed = discord.Embed(
                    title="📊 Vote Status",
                    description=f"Status for vote {vote_id}",
                    color=0x00BFFF
                )

                embed.add_field(name="Target", value=f"<@{vote_data['target_id']}>", inline=False)
                embed.add_field(name="Starter", value=f"{vote_data['starter_name']}", inline=True)
                embed.add_field(name="Reason", value=vote_data['reason'], inline=True)
                embed.add_field(name="Time Remaining", value=remaining_str, inline=True)
                embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
                embed.add_field(name="Quorum Status", value=quorum_status, inline=True)
                embed.add_field(name="Vote Breakdown", value=f"🔨 Ban: {ban_votes}\n🛡️ Keep: {total_votes - ban_votes}", inline=False)

                if total_votes > 0:
                    percentage = (ban_votes / total_votes) * 100
                    embed.add_field(name="Current Percentage", value=f"{percentage:.1f}% voting to ban", inline=False)

                await interaction.followup.send(embed=embed)
            else:
                # Show all active votes for this server
                server_votes = []
                for vid, vdata in votes.items():
                    if vdata['guild_id'] == interaction.guild.id:
                        guild = self.bot.get_guild(vdata['guild_id'])
                        target = guild.get_member(vdata['target_id']) if guild else None
                        target_name = target.display_name if target else "Unknown User"

                        start_time = datetime.fromisoformat(vdata['start_time'])
                        remaining = timedelta(hours=24) - (datetime.now() - start_time)

                        if remaining.total_seconds() <= 0:
                            remaining_str = "Voting has ended"
                        else:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            remaining_str = f"{hours}h {minutes}m"

                        total_votes = len(vdata['votes'])
                        ban_votes = sum(1 for v in vdata['votes'].values() if v == 'ban')

                        # Get quorum status
                        human_members = len([m for m in guild.members if not m.bot])
                        required_votes = max(1, int(human_members / 3))
                        quorum_status = f"{total_votes}/{required_votes} votes"

                        server_votes.append(f"**Vote {vid}:** {target_name}\n🔨 {ban_votes} vs 🛡️ {total_votes - ban_votes} ({remaining_str})\nQuorum: {quorum_status}\nBy: {vdata['starter_name']} - {vdata['reason']}")

                if server_votes:
                    for page in pagify("\n\n".join(server_votes), chars=2000):
                        embed = discord.Embed(
                            title="📊 Active Ban Votes",
                            description=page,
                            color=0x00BFFF
                        )
                        await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("No active ban votes in this server.")

    @app_commands.command(name='votebanclear', description='Clear an active ban vote or all votes (Admin only)')
    @app_commands.describe(vote_id='The vote ID to clear (optional, leave empty to clear all votes)')
    @checks.admin_or_permissions(administrator=True)
    async def votebanclear_slash(self, interaction: discord.Interaction, vote_id: str = None):
        """Clear an active ban vote or all votes (Admin only) using slash command"""
        async with self.config.active_votes() as votes:
            cleared_votes = []

            if vote_id:
                if vote_id in votes:
                    # Disable the buttons on the original message
                    vote_data = votes[vote_id]
                    cleared_votes.append(vote_id)

                    # Check if vote failed due to quorum to potentially remove cooldown
                    guild = interaction.guild
                    if guild:
                        human_members = len([m for m in guild.members if not m.bot])
                        required_votes = max(1, int(human_members / 3))
                        actual_votes = len(vote_data['votes'])

                        # If quorum likely not met, remove starter's cooldown
                        if actual_votes < required_votes:
                            async with self.config.cooldowns() as cooldowns:
                                if str(vote_data['starter_id']) in cooldowns:
                                    del cooldowns[str(vote_data['starter_id'])]

                    try:
                        channel = interaction.guild.get_channel(vote_data['channel_id'])
                        if channel and 'message_id' in vote_data:
                            message = await channel.fetch_message(vote_data['message_id'])
                            view = VotebanView(vote_id, self)
                            for child in view.children:
                                child.disabled = True
                            await message.edit(view=view)
                    except Exception as e:
                        print(f"Error disabling vote buttons: {e}")

                    del votes[vote_id]
                else:
                    await interaction.response.send_message("Invalid vote ID.")
                    return
            else:
                # Clear all votes for this server
                to_remove = []
                for vid, vdata in votes.items():
                    if vdata['guild_id'] == interaction.guild.id:
                        to_remove.append(vid)
                        cleared_votes.append(vid)

                        # Check if vote failed due to quorum to potentially remove cooldown
                        guild = interaction.guild
                        if guild:
                            human_members = len([m for m in guild.members if not m.bot])
                            required_votes = max(1, int(human_members / 3))
                            actual_votes = len(vdata['votes'])

                            # If quorum likely not met, remove starter's cooldown
                            if actual_votes < required_votes:
                                async with self.config.cooldowns() as cooldowns:
                                    if str(vdata['starter_id']) in cooldowns:
                                        del cooldowns[str(vdata['starter_id'])]

                        # Disable the buttons on the original messages
                        try:
                            channel = interaction.guild.get_channel(vdata['channel_id'])
                            if channel and 'message_id' in vdata:
                                message = await channel.fetch_message(vdata['message_id'])
                                view = VotebanView(vid, self)
                                for child in view.children:
                                    child.disabled = True
                                await message.edit(view=view)
                        except Exception as e:
                            print(f"Error disabling vote buttons: {e}")

                for vid in to_remove:
                    del votes[vid]

            await interaction.response.send_message(f"Cleared {len(cleared_votes)} active vote(s).")

    @app_commands.command(name='votebanimmune', description='Manually grant immunity to a user for 6 months (Admin only)')
    @app_commands.describe(target='The user to grant immunity to')
    @checks.admin_or_permissions(administrator=True)
    async def votebanimmune_slash(self, interaction: discord.Interaction, target: discord.Member):
        """Manually grant immunity to a user (Admin only) using slash command"""
        async with self.config.immunities() as immunities:
            immunity_end = (datetime.now() + timedelta(days=180)).isoformat()
            immunities[str(target.id)] = immunity_end

            embed = discord.Embed(
                title="🛡️ Immunity Granted",
                description=f"{target.mention} has been granted immunity for 6 months.",
                color=0x00FF00
            )

            await interaction.response.send_message(embed=embed)