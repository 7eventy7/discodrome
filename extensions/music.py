import discord
import logging
from discord import app_commands
from discord.ext import commands

from random import randint 
import data
import copy
import subsonic
import ui
from asyncio import sleep

from discodrome import DiscodromeClient

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog):
    ''' A Cog containing music playback commands '''

    bot : DiscodromeClient

    def __init__(self, bot: DiscodromeClient):
        self.bot = bot

    async def get_voice_client(self, interaction: discord.Interaction, *, should_connect: bool=False) -> discord.VoiceClient:
        ''' Returns a voice client instance for the current guild '''

        # Get the voice client for the guild
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        # Connect to a voice channel
        if voice_client is None and should_connect:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except AttributeError:
                await ui.ErrMsg.cannot_connect_to_voice_channel(interaction)

        return voice_client

    @app_commands.command(name="play", description="Plays a specified track")
    @app_commands.describe(querytype="Whether what you're searching is a track or album", query="Enter a search query")
    @app_commands.choices(querytype=[
        app_commands.Choice(name="Track", value="track"),
        app_commands.Choice(name="Album", value="album"),
    ])
    async def play(self, interaction: discord.Interaction, querytype: str=None, query: str=None) -> None:
        ''' Play a track matching the given title/artist query '''

        # Check if user is in voice channel
        if interaction.user.voice is None:
            return await ui.ErrMsg.user_not_in_voice_channel(interaction)

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(interaction, should_connect=True)

        # Don't attempt playback if the bot is already playing
        if voice_client.is_playing() and query is None:
            return await ui.ErrMsg.already_playing(interaction)

        # Get the guild's player
        player = data.guild_data(interaction.guild_id).player

        # Check queue if no query is provided
        if query is None:

            # Display error if queue is empty & autoplay is disabled
            if player.queue == [] and data.guild_properties(interaction.guild_id).autoplay_mode == data.AutoplayMode.NONE:
                return await ui.ErrMsg.queue_is_empty(interaction)

            # Begin playback of queue
            await ui.SysMsg.starting_queue_playback(interaction)
            await player.play_audio_queue(interaction, voice_client)
            return

        # Check querytype is not blank
        if querytype is None:
            return await ui.ErrMsg.msg(interaction, "Please provide a query type.")

        # Check if the query is a track
        if querytype == "track":

            # Send our query to the subsonic API and retrieve a list of 1 song
            songs = await subsonic.search(query, artist_count=0, album_count=0, song_count=1)
            if songs == "Error":
                await ui.ErrMsg.msg(interaction, f"An api error has occurred and has been logged to console. Please contact an administrator.")
                return

            # Display an error if the query returned no results
            if len(songs) == 0:
                await ui.ErrMsg.msg(interaction, f"No track found for **{query}**.")
                return
            
            # Add the first result to the queue and handle queue playback
            player.queue.append(songs[0])

            await ui.SysMsg.added_to_queue(interaction, songs[0])

        elif querytype == "album":

            # Send query to subsonic API and retrieve a list of 1 album
            album = await subsonic.search_album(query)
            if album == None:
                await ui.ErrMsg.msg(interaction, f"No album found for **{query}**.")
                return
            
            # Add all songs from the album to the queue
            for song in album.songs:
                player.queue.append(song)
            
            await ui.SysMsg.added_album_to_queue(interaction, album)

        await player.play_audio_queue(interaction, voice_client)

    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred playing a track, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing a track: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @app_commands.command(name="stop", description="Stop playing the current track")
    async def stop(self, interaction: discord.Interaction) -> None:
        ''' Disconnect from the active voice channel '''

        player = data.guild_data(interaction.guild_id).player

        if player.current_song is None:
            ui.ErrMsg.not_playing(interaction)

        # Get the voice client instance for the current guild
        voice_client = await self.get_voice_client(interaction)

        # Check if our voice client is connected
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Stop playback
        voice_client.stop()

        # Add current song back to the queue if exists
        player.queue.insert(0, player.current_song)
        player.current_song = None

        # Display disconnect confirmation
        await ui.SysMsg.stopping_queue_playback(interaction)

    @stop.error
    async def stop_error(self, ctx, error):
        logging.error(f"An error occurred while stopping playback: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    @app_commands.command(name="queue", description="View the current queue")
    async def show_queue(self, interaction: discord.Interaction) -> None:
        ''' Show the current queue '''

        # Get the audio queue for the current guild
        queue = data.guild_data(interaction.guild_id).player.queue

        # Create a string to store the output of our queue
        output = ""

        # Add currently playing song to output if available
        if data.guild_data(interaction.guild_id).player.current_song is not None:
            song = data.guild_data(interaction.guild_id).player.current_song
            output += f"**Now Playing:**\n{song.title} - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"

        # Loop over our queue, adding each song into our output string
        for i, song in enumerate(queue):
            strtoadd = f"{i+1}. **{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"
            if len(output+strtoadd) < 4083:
                output += strtoadd
            else:
                remaining = len(queue) - i
                output += f"**And {remaining} more...**"
                break

        # Check if our output string is empty & update it accordingly
        if output == "":
            output = "Queue is empty!"

        # Show the user their queue
        await ui.SysMsg.msg(interaction, "Queue", output)

    @show_queue.error
    async def show_queue_error(self, ctx, error):
        logging.error(f"An error occurred while displaying the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    @app_commands.command(name="clear", description="Clear the current queue")
    async def clear_queue(self, interaction: discord.Interaction) -> None:
        '''Clear the queue'''
        queue = data.guild_data(interaction.guild_id).player.queue
        queue.clear()

        # Let the user know that the queue has been cleared
        await ui.SysMsg.queue_cleared(interaction)

    @clear_queue.error
    async def clear_queue_error(self, ctx, error):
        logging.error(f"An error occurred while clearing the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction) -> None:
        ''' Skip the current track '''

        # Get the voice client instance
        voice_client = await self.get_voice_client(interaction)

        # Check if the bot is connected to a voice channel
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Check if the bot is playing music
        if not voice_client.is_playing():
            await ui.ErrMsg.not_playing(interaction)
            return

        await data.guild_data(interaction.guild_id).player.skip_track(interaction, voice_client)

    @skip.error
    async def skip_error(self, ctx, error):
        logging.error(f"An error occurred while skipping a track: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    @app_commands.command(name="autoplay", description="Toggles autoplay")
    @app_commands.describe(mode="Determines the method to use when autoplaying")
    @app_commands.choices(mode=[
        app_commands.Choice(name="None", value="none"),
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="Similar", value="similar"),
    ])
    async def autoplay(self, interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        ''' Toggles autoplay '''

        logger.debug(f"Autoplay mode: {mode.value}")
        # Update the autoplay properties
        match mode.value:
            case "none":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.NONE
            case "random":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.RANDOM
            case "similar":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.SIMILAR

        # Display message indicating new status of autoplay
        if mode.value == "none":
            await ui.SysMsg.msg(interaction, f"Autoplay disabled by {interaction.user.display_name}")
        else:
            await ui.SysMsg.msg(interaction, f"Autoplay enabled by {interaction.user.display_name}", f"Autoplay mode: **{mode.name}**")


        # If the bot is connected to a voice channel and autoplay is enabled, start queue playback
        voice_client = await self.get_voice_client(interaction)
        logger.debug(f"Voice client: {voice_client}")
        if voice_client:
            logger.debug(f"Is playing: {voice_client.is_playing()}")
        if voice_client is not None and not voice_client.is_playing():        
            player = data.guild_data(interaction.guild_id).player

            logger.debug(f"Queue: {player.queue}")
            logger.debug(f"Current song: {player.current_song}")
            # If queue is already empty and no song is playing, handle autoplay
            if player.queue == [] and player.current_song is None:
                logging.debug("Handling autoplay...")
                await player.handle_autoplay(interaction)
                
            logger.debug("Playing audio queue...")
            await player.play_audio_queue(interaction, voice_client)
        
    @autoplay.error
    async def autoplay_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while toggling autoplay, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while toggling autoplay: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    @app_commands.command(name="shuffle", description="Shuffles the current queue")
    async def shuffle(self, interaction: discord.Interaction):
        ''' Randomize current queue using Fisher-Yates algorithm '''
        temporaryqueue = copy.deepcopy(data.guild_data(interaction.guild_id).player.queue)
        shuffledqueue = []
        while len(temporaryqueue) > 0:
            randomindex = randint(0, len(temporaryqueue) - 1)
            shuffledqueue.append(temporaryqueue.pop(randomindex))
        
        data.guild_data(interaction.guild_id).player.queue = shuffledqueue
        await ui.SysMsg.msg(interaction, "Queue shuffled!")

    @shuffle.error
    async def shuffle_error(self, ctx, error):
        logging.error(f"An error occurred while shuffling the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    @app_commands.command(name="disco", description="Plays the artist's entire discography")
    @app_commands.describe(artist="The artist to play")
    async def disco(self, interaction: discord.Interaction, artist: str):
        ''' Play the artist's entire discography'''

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(interaction, should_connect=True)

        # Get the guild's player
        player = data.guild_data(interaction.guild_id).player

        # Send our query to the subsonic API and retrieve list of albums in artist's discography
        albums = await subsonic.get_artist_discography(artist)
        if albums == None:
            await ui.ErrMsg.msg(interaction, f"No discography found for **{artist}**.")
            return
        
        # Add all songs from the artist's discography to the queue
        for album in albums:
            for song in album.songs:
                player.queue.append(song)
        
        # Display a message that discography was added to the queue
        await ui.SysMsg.added_discography_to_queue(interaction, artist, albums)

        # Begin playback of queue
        await player.play_audio_queue(interaction, voice_client)

        

    @disco.error
    async def disco_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while playing an artist's discography, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing an artist's discography: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")    

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        ''' Event called when a user's voice state changes '''

        # Check if the bot is connected to a voice channel
        voice_client = discord.utils.get(self.bot.voice_clients, guild=member.guild)

        # Check if the bot is connected to a voice channel
        if voice_client is None:
            return

        # Check if the bot is alone in the voice channel
        if len(voice_client.channel.members) == 1:
            logger.debug("Bot is alone in voice channel, waiting 10 seconds before disconnecting...")
            # Wait for 10 seconds
            await sleep(10)
            
            # Check again if there are still no users in the voice channel
            if len(voice_client.channel.members) == 1:
                # Disconnect the bot and clear the queue
                await voice_client.disconnect()
                player = data.guild_data(member.guild.id).player
                player.queue.clear()
                player.current_song = None
                logger.info("The bot has disconnected and cleared the queue as there are no users in the voice channel.")
            else:
                logger.debug("Bot is no longer alone in voice channel, aborting disconnect...")

async def setup(bot: DiscodromeClient):
    ''' Setup function for the music.py cog '''

    await bot.add_cog(MusicCog(bot))
