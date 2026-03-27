import asyncio
import signal
import discord
import logging
import os

logger = logging.getLogger(__name__)

from discord.ext import commands

import data

from util import env
from util import logs
from subsonic import close_session, ping_api

class DiscodromeClient(commands.Bot):
    ''' An instance of the Discodrome client '''

    test_guild: int

    def __init__(self, test_guild: int=None) -> None:
        self.test_guild = test_guild

        if env.BOT_PREFIX != None:
            if len(env.BOT_PREFIX) > 0:
                logger.info(f'Command prefix is {env.BOT_PREFIX}')
            else:
                logger.info(f'Command prefix is an empty string. ALL MESSAGES WILL BE INTERPRETED AS COMMANDS.')
        else:
            logger.info(f'Command prefix not set.')
        prefix = commands.when_mentioned if env.BOT_PREFIX == None else commands.when_mentioned_or(env.BOT_PREFIX)
        super().__init__(command_prefix=prefix, intents=discord.Intents.all())

    async def load_extensions(self) -> None:
        ''' Auto-loads all extensions present within the `./extensions` directory. '''

        for file in os.listdir("./extensions"):
            if file.endswith(".py"):
                ext_name = file[:-3]
                try:
                    await self.load_extension(f"extensions.{ext_name}")
                except commands.errors.ExtensionError as err:
                    if isinstance(err, commands.errors.ExtensionNotFound):
                        logger.warning("Failed to load extension '%s'. Extension was not found.", ext_name)
                    if isinstance(err, commands.errors.ExtensionAlreadyLoaded):
                        logger.warning("Failed to load extension '%s'. Extension was already loaded.", ext_name)
                    if isinstance(err, commands.errors.NoEntryPointError):
                        logger.error("Failed to load extension '%s'. No entry point was found in the file.", ext_name, exc_info=err)
                    if isinstance(err, commands.errors.ExtensionFailed):
                        logger.error("Failed to load extension '%s'. Extension setup failed.", ext_name, exc_info=err)
                else:
                    logger.info("Extension '%s' loaded successfully.", ext_name)

    async def sync_command_tree(self) -> None:
        ''' Synchronizes the command tree with the guild used for testing. '''

        guild = discord.Object(self.test_guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def setup_hook(self) -> None:
        ''' Setup done after login, prior to events being dispatched. '''

        await self.load_extensions()
        if await ping_api():
            logger.info("Subsonic API is online.")
        else:
            logger.error("Subsonic API is unreachable.")

        if self.test_guild:
            await self.sync_command_tree()

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(self._on_sigterm()))

    async def _on_sigterm(self) -> None:
        ''' Graceful shutdown on SIGTERM. '''
        logger.debug("Beginning graceful shutdown...")
        data.save_guild_properties_to_disk()
        await close_session()
        logger.info("Discodrome shutdown complete.")
        await self.close()

    async def on_ready(self) -> None:
        ''' Event called when the client is done preparing. '''

        activity = discord.Activity(type=discord.ActivityType.playing, name=env.BOT_STATUS)
        await self.change_presence(activity=activity)

        logger.info("Logged as: %s | Connected Guilds: %s | Loaded Extensions: %s", self.user, len(self.guilds), list(self.extensions))

if __name__ == "__main__":
    logs.setup_logging()
    logger = logging.getLogger(__name__)
    data.load_guild_properties_from_disk()
    client = DiscodromeClient(test_guild=env.DISCORD_TEST_GUILD)
    client.run(env.DISCORD_BOT_TOKEN, log_handler=None)

