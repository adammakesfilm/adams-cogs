import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import pagify
from datetime import datetime, timedelta
import asyncio
from discord import app_commands
from discord.ui import View, Button, button
import math
class VotebanView(View):
    """Button view for anonymous voting with persistent voting"""

    def __init__(self, vote_id, cog):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.cog = cog

        # Set custom IDs dynamically here
        self.ban_button.custom_id = f'voteban_ban_{vote_id}'
        self.keep_button.custom_id = f'voteban_keep_{vote_id}'
        self.status_button.custom_id = f'voteban_status_{vote_id}'

    @button(label='Vote to Ban', style=discord.ButtonStyle.danger, emoji='🔨')
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_vote_button(interaction, self.vote_id, 'ban')

    @button(label='Vote to Keep', style=discord.ButtonStyle.success, emoji='🛡️')
    async def keep_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_vote_button(interaction, self.vote_id, 'keep')

    @button(label='Check Status', style=discord.ButtonStyle.secondary, emoji='📊')
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_status_button(interaction, self.vote_id)

class Voteban(commands.Cog):
    """Anonymous voting system to ban users with slash commands and persistent buttons"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, 
            identifier=1234567890,  # Unique identifier for your cog
            force_registration=True
        )

        # Define config structure
        self.config.register_global(
            active_votes={},  # {vote_id: {target_id, starter_id, start_time, votes: {user_id: vote}, message_id}}
            immunities={},    # {user_id: immunity_end_time}
            cooldowns={},     # {user_id: cooldown_end_time}
            vote_counter=0    # To generate unique vote IDs
        )

        self.vote_check_task = self.bot.loop.create_task(self.check_votes())

    async def cog_load(self):
        """Called when the cog is loaded - register persistent views"""
        # Wait for bot to be ready before registering views
        await self.bot.wait_until_ready()
        async with self.config.active_votes() as votes:
            for vote_id in votes.keys():
                try:
                    view = VotebanView(vote_id, self)
                    self.bot.add_view(view)
                except Exception as e:
                    print(f"Error registering view for vote {vote_id}: {e}")

    def cog_unload(self):
        """Called when the cog is unloaded - cleanup tasks"""
        self.vote_check_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent views when bot is ready"""
        # Re-register all active vote views on bot restart
        await self.bot.wait_until_ready()
        async with self.config.active_votes() as votes:
            for vote_id in votes.keys():
                try:
                    view = VotebanView(vote_id, self)
                    self.bot.add_view(view)
                    print(f"Registered persistent view for vote {vote_id}")
                except Exception as e:
                    print(f"Error registering view for vote {vote_id}: {e}")

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

    async def calculate_quorum(self, guild):
        """Calculate quorum requirement (1/3 of server members)"""
        # Get total member count
        total_members = guild.member_count

        # Calculate quorum (at least 1/3 of members)
        quorum = math.ceil(total_members / 3)

        # Ensure minimum quorum of at least 3 members (to avoid edge cases)
        return max(quorum, 3)

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

        # Calculate quorum
        quorum = await self.calculate_quorum(guild)

        # Check if quorum was met
        if total_votes < quorum:
            # Quorum not met - vote fails, nothing happens
            await self.handle_quorum_failure(vote_id, vote_data, guild, total_votes, quorum)
            return

        # Quorum met - proceed with vote result
        ban_percentage = (ban_votes / total_votes) * 100

        async with self.config.immunities() as immunities:
            if ban_percentage > 50:
                # Ban the user
                try:
                    await guild.ban(target, reason=f"Ban vote passed: {ban_votes}/{total_votes} votes")
                    # Remove immunity if they had any
                    if str(target.id) in immunities:
                        del immunities[str(target.id)]
                    result = "banned"
                    color = 0xFFD700
                except discord.Forbidden:
                    result = "failed (bot lacks permission)"
                    color = 0xFF0000
            else:
                # Grant immunity for 6 months (includes 50% ties)
                immunity_end = (datetime.now() + timedelta(days=180)).isoformat()
                immunities[str(target.id)] = immunity_end
                result = "kept (6-month immunity granted)"
                color = 0x00FF00

        # Update the original message to show results
        await self.update_vote_completion_message(vote_id, vote_data, guild, target, ban_votes, total_votes, result, color)

    async def handle_quorum_failure(self, vote_id, vote_data, guild, total_votes, quorum):
        """Handle case where quorum was not met"""
        # Remove the starter's cooldown since vote didn't count
        async with self.config.cooldowns() as cooldowns:
            if str(vote_data['starter_id']) in cooldowns:
                del cooldowns[str(vote_data['starter_id'])]

        # Get target for message
        target = guild.get_member(vote_data['target_id'])
        target_name = target.display_name if target else "Unknown User"

        # Update the original message to show quorum failure
        if 'message_id' in vote_data:
            try:
                channel = guild.get_channel(vote_data['channel_id'])
                if channel:
                    message = await channel.fetch_message(vote_data['message_id'])

                    embed = discord.Embed(
                        title="Quorum Not Met - Vote Failed",
                        description=f"Vote against {target_name} did not reach required participation",
                        color=0xFF0000
                    )

                    embed.add_field(name="Result", value="VOTE FAILED - Insufficient participation", inline=False)
                    embed.add_field(name="Votes Cast", value=f"{total_votes}/{quorum} required", inline=False)
                    embed.add_field(name="Quorum Requirement", value=f"At least {quorum} members must vote (1/3 of server)", inline=False)
                    embed.add_field(name="Consequences", value="No cooldowns applied, no actions taken", inline=False)
                    embed.set_footer(text=f"Vote ID: {vote_id}")

                    view = VotebanView(vote_id, self)
                    for child in view.children:
                        child.disabled = True

                    await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Error updating quorum failure message: {e}")

    async def update_vote_completion_message(self, vote_id, vote_data, guild, target, 
                                            ban_votes, total_votes, result, color):
        """Update the vote completion message"""
        if 'message_id' in vote_data:
            try:
                channel = guild.get_channel(vote_data['channel_id'])
                if channel:
                    message = await channel.fetch_message(vote_data['message_id'])

                    embed = discord.Embed(
                        title="Ban Vote Completed",
                        description=f"Vote against {target.mention}",
                        color=color
                    )

                    embed.add_field(name="Result", value=f"{result.upper()}", inline=False)
                    embed.add_field(name="Votes", value=f"BAN: {ban_votes} | KEEP: {total_votes - ban_votes}", inline=False)
                    embed.add_field(name="Percentage", value=f"{(ban_votes/total_votes)*100:.1f}% voted to ban", inline=False)
                    embed.add_field(name="Quorum", value=f"Met ({total_votes} votes cast)", inline=False)
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
            end_time = start_time + timedelta(hours=24)
            unix_end_time = int(end_time.timestamp())

            total_votes = len(vote_data['votes'])
            ban_votes = sum(1 for v in vote_data['votes'].values() if v == 'ban')

            # Calculate quorum
            guild = interaction.guild
            quorum = await self.calculate_quorum(guild)
            remaining_for_quorum = max(0, quorum - total_votes)

            embed = discord.Embed(
                title="Vote Status",
                description=f"Current vote progress",
                color=0x00BFFF
            )

            embed.add_field(name="Target", value=f"<@{vote_data['target_id']}>", inline=False)
            embed.add_field(name="Time Remaining", value=f"<t:{unix_end_time}:R>", inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)

            # Quorum information
            if total_votes >= quorum:
                quorum_status = f"Met ({total_votes}/{quorum} required)"
            else:
                quorum_status = f"Not met ({total_votes}/{quorum} required, {remaining_for_quorum} more needed)"

            embed.add_field(name="Quorum Status", value=quorum_status, inline=False)
            embed.add_field(name="Vote Breakdown", value=f"BAN: {ban_votes} | KEEP: {total_votes - ban_votes}", inline=False)

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
            end_time = start_time + timedelta(hours=24)
            unix_end_time = int(end_time.timestamp())

            # Calculate quorum
            guild = interaction.guild
            quorum = await self.calculate_quorum(guild)

            embed = discord.Embed(
                title="Ban Vote Started",
                description=f"Vote to ban <@{vote_data['target_id']}> from the server",
                color=0xFF4500
            )

            embed.add_field(name="Time Remaining", value=f"<t:{unix_end_time}:R>", inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)

            # Quorum information
            if total_votes >= quorum:
                quorum_status = f"Met ({total_votes}/{quorum} required)"
            else:
                remaining_for_quorum = quorum - total_votes
                quorum_status = f"Not met ({total_votes}/{quorum}, need {remaining_for_quorum} more)"

            embed.add_field(name="Quorum Status", value=quorum_status, inline=False)
            embed.add_field(name="Current Results", value=f"BAN: {ban_votes} | KEEP: {total_votes - ban_votes}", inline=False)

            if total_votes > 0:
                percentage = (ban_votes / total_votes) * 100
                embed.add_field(name="Percentage", value=f"{percentage:.1f}% voting to ban", inline=False)

            embed.add_field(name="Requirements", value=f"At least {quorum} members must vote for the vote to count", inline=False)
            embed.add_field(name="Anonymous Voting", value="Your vote is completely anonymous. Press the buttons below to cast your vote.", inline=False)
            embed.set_footer(text=f"Vote ID: {vote_id}")

            view = VotebanView(vote_id, self)
            await message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Error updating vote message: {e}")

    @app_commands.command(name='voteban', description='Start an anonymous vote to ban a user')
    @app_commands.describe(target='The user to start a ban vote against')
    async def voteban_slash(self, interaction, target: discord.Member, reason: str):
        """Start an anonymous vote to ban a user using slash command"""

        # Check if target is server owner
        if target == interaction.guild.owner:
            await interaction.response.defer()
            await interaction.followup.send("You cannot start a ban vote against the server owner.")
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

            # Create new vote - FIXED CONFIG ISSUE
            counter = await self.config.vote_counter()
            vote_id = str(counter)
            await self.config.vote_counter.set(counter + 1)

            vote_data = {
                'guild_id': interaction.guild.id,
                'channel_id': interaction.channel.id,
                'target_id': target.id,
                'starter_id': interaction.user.id,
                'reason': reason,  # Save the reason
                'start_time': datetime.now().isoformat(),
                'votes': {str(interaction.user.id): 'ban'},
                'message_id': None
            }

            votes[vote_id] = vote_data

        # Set cooldown for the starter
        async with self.config.cooldowns() as cooldowns:
            cooldown_end = (datetime.now() + timedelta(days=180)).isoformat()
            cooldowns[str(interaction.user.id)] = cooldown_end

        # Calculate vote end time for Discord timestamp
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=24)
        unix_end_time = int(end_time.timestamp())

        # Calculate quorum
        quorum = await self.calculate_quorum(interaction.guild)

        # Create and send the embed with buttons
        embed = discord.Embed(
            title="Ban Vote Started",
            description=f"Vote to ban {target.mention} from the server",
            color=0xFF4500
        )

        embed.add_field(name="Time Remaining", value=f"<t:{unix_end_time}:R>", inline=True)
        embed.add_field(name="Total Votes", value="1", inline=True)
        embed.add_field(name="Quorum Status", value=f"Not met (1/{quorum} required, need {quorum-1} more)", inline=False)
        embed.add_field(name="Current Results", value="BAN: 1 | KEEP: 0", inline=False)
        embed.add_field(name="Requirements", value=f"At least {quorum} members (1/3 of server) must vote for the vote to count", inline=False)
        embed.add_field(name="Anonymous Voting", value="Your vote is completely anonymous. Use the buttons below to cast your vote.", inline=False)
        embed.set_footer(text=f"Vote ID: {vote_id}")

        view = VotebanView(vote_id, self)
        message = await interaction.followup.send(embed=embed, view=view)

        # Register the view for persistence
        self.bot.add_view(view)

        # Store the message ID for updating
        async with self.config.active_votes() as votes:
            votes[vote_id]['message_id'] = message.id

@app_commands.command(name='votestatus', description='Check the status of a ban vote')
@app_commands.describe(vote_id='The vote ID to check')
async def votestatus_slash(self, interaction: "discord.Interaction", vote_id: str = None):
    await interaction.response.defer(ephemeral=True)

    async with self.config.active_votes() as votes:
        if vote_id:
            if vote_id not in votes:
                await interaction.followup.send("Invalid vote ID.")
                return

            vote_data = votes[vote_id]
            start_time = datetime.fromisoformat(vote_data['start_time'])
            end_time = start_time + timedelta(hours=24)
            unix_end_time = int(end_time.timestamp())
            total_votes = len(vote_data['votes'])
            ban_votes = sum(1 for v in vote_data['votes'].values() if v == 'ban')
            quorum = await self.calculate_quorum(interaction.guild)

            # Re-styled embed to match your image
            embed = discord.Embed(title="📊 Vote Status", color=0x00BFFF)
            embed.description = f"Status for vote {vote_id}"
            embed.add_field(name="Target", value=f"<@{vote_data['target_id']}>", inline=False)

            starter = interaction.guild.get_member(vote_data['starter_id'])
            embed.add_field(name="Starter", value=starter.display_name if starter else "Unknown", inline=True)
            embed.add_field(name="Reason", value=vote_data.get('reason', 'No reason provided'), inline=True)
            embed.add_field(name="Time Remaining", value=f"<t:{unix_end_time}:R>", inline=True)

            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
            embed.add_field(name="Quorum Status", value=f"{total_votes}/{quorum} votes needed", inline=True)

            embed.add_field(name="Vote Breakdown", value=f"🔨 Ban: {ban_votes}\n🛡️ Keep: {total_votes - ban_votes}", inline=False)

            if total_votes > 0:
                percentage = (ban_votes / total_votes) * 100
                embed.add_field(name="Current Percentage", value=f"{percentage:.1f}% voting to ban", inline=False)

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("No active ban votes in this server.")

    @app_commands.command(name='votebanclear', description='Clear an active ban vote or all votes (Admin only)')
    @app_commands.describe(vote_id='The vote ID to clear (optional, leave empty to clear all votes)')
    @checks.admin_or_permissions(administrator=True)
    async def votebanclear_slash(self, interaction, vote_id: str = None):
        """Clear an active ban vote or all votes (Admin only) using slash command"""
        async with self.config.active_votes() as votes:
            if vote_id:
                if vote_id in votes:
                    # Disable the buttons on the original message
                    vote_data = votes[vote_id]
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
                    await interaction.response.send_message(f"Vote {vote_id} has been cleared.")
                else:
                    await interaction.response.send_message("Invalid vote ID.")
            else:
                # Clear all votes for this server
                to_remove = []
                for vid, vdata in votes.items():
                    if vdata['guild_id'] == interaction.guild.id:
                        to_remove.append(vid)
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

                await interaction.response.send_message(f"Cleared {len(to_remove)} active votes.")

    @app_commands.command(name='votebanimmune', description='Manually grant immunity to a user for 6 months (Admin only)')
    @app_commands.describe(target='The user to grant immunity to')
    @checks.admin_or_permissions(administrator=True)
    async def votebanimmune_slash(self, interaction, target: discord.Member):
        """Manually grant immunity to a user (Admin only) using slash command"""
        async with self.config.immunities() as immunities:
            immunity_end = (datetime.now() + timedelta(days=180)).isoformat()
            immunities[str(target.id)] = immunity_end

            embed = discord.Embed(
                title="Immunity Granted",
                description=f"{target.mention} has been granted immunity for 6 months.",
                color=0x00FF00
            )

            await interaction.response.send_message(embed=embed)
