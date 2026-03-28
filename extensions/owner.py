'''An extention containing functionality exclusive to the bot owner'''

import logging
from discord import app_commands, Interaction
from discord.ext import commands
from discodrome import DiscodromeClient
from util import env

logger = logging.getLogger(__name__)

class OwnerCog(commands.Cog):
    ''' A Cog containing owner specific commands '''
    
    bot: DiscodromeClient
    
    def __init__(self, bot: DiscodromeClient):
        self.bot = bot
    
    async def interaction_check(self, interaction: Interaction):
        return interaction.user.id == env.DISCORD_OWNER_ID

    @app_commands.command(name="sync", description="Sync slash commands")
    async def sync(self, interaction: Interaction):
        await self.bot.sync_command_tree()
        if (interaction.message is not None):
            await interaction.message.reply("Commands synced")
