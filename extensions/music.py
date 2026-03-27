from typing import List

import discord
import logging
import asyncio
from discord import app_commands, Interaction
from discord.ext import commands

from random import randint 
import data
import copy
import subsonic
import ui
from pagination import ListPaginator

from discodrome import DiscodromeClient
from util import env

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog):
    ''' A Cog containing music playback commands '''

    bot : DiscodromeClient

    def __init__(self, bot: DiscodromeClient):
        self.bot = bot

    async def get_voice_client(self, interaction: Interaction, *, should_connect: bool=False) -> discord.VoiceClient:
        ''' Returns a voice client instance for the current guild '''

        # Get the voice client for the guild
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        # Connect to a voice channel
        if voice_client is None and should_connect:
            try:
                # Check if user is in a voice channel
                if interaction.user.voice is None or interaction.user.voice.channel is None:
                    await ui.ErrMsg.user_not_in_voice_channel(interaction)
                    return None
                
                # Check if we have permission to join the voice channel
                permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
                if not permissions.connect or not permissions.speak:
                    logger.error("Missing permissions to connect or speak in voice channel")
                    await ui.ErrMsg.msg(interaction, "I don't have permission to join or speak in your voice channel.")
                    return None
                
                # Add a small delay before connecting to avoid potential race conditions
                await asyncio.sleep(1)
                
                # Connect with timeout and retry logic
                try:
                    voice_client = await interaction.user.voice.channel.connect(timeout=10.0, reconnect=True)
                    logger.info(f"Successfully connected to voice channel {interaction.user.voice.channel.id}")
                except asyncio.TimeoutError:
                    logger.error("Timeout while connecting to voice channel")
                    await ui.ErrMsg.msg(interaction, "Timed out while trying to connect to voice channel. Please try again.")
                    return None
                except discord.ClientException as e:
                    logger.error(f"Client exception when connecting to voice: {e}")
                    await ui.ErrMsg.msg(interaction, f"Error connecting to voice channel: {e}")
                    return None
                
            except AttributeError as e:
                logger.error(f"Attribute error when connecting to voice: {e}")
                await ui.ErrMsg.cannot_connect_to_voice_channel(interaction)
            except Exception as e:
                logger.error(f"Unexpected error when connecting to voice: {e}")
                await ui.ErrMsg.msg(interaction, f"An unexpected error occurred while connecting to voice: {e}")
                
        return voice_client



    @commands.command(name="p")
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        ''' Play a track matching the given query '''

        if ctx.author.voice is None:
            await ctx.send("You are not connected to a voice channel.")
            return

        player = data.guild_data(ctx.guild.id).player

        result = (await subsonic.search(query, artist_count=0, album_count=0, song_count=1))

        if not result.succeeded:
            await ctx.send(f"An error has occurred while searching for **{query}**. Code: {result.error_code}.")
            return

        songs = result.songs

        if len(songs) == 0:
            await ctx.send(f"No track found for **{query}**.")
            return

        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client is None:
            try:
                voice_client = await ctx.author.voice.channel.connect(timeout=10.0, reconnect=True)
            except Exception as e:
                await ctx.send(f"Failed to connect to voice channel: {e}")
                return

        player.channel = ctx.channel
        player.queue.append(songs[0])
        await ctx.send(f"Queued **{songs[0].title}** by {songs[0].artist}")
        await player.play_audio_queue(voice_client)


    
    @commands.command(name="n")
    async def play_next_prefix(self, ctx: commands.Context, *, query: str):
        ''' Search for a track and place it next in the queue - prefix version '''
        # This is a heinous duplication of efforts made above.
        # TODO: Please refactor.

        if ctx.author.voice is None:
            await ctx.send("You are not connected to a voice channel.")
            return

        player = data.guild_data(ctx.guild.id).player

        result = (await subsonic.search(query, artist_count=0, album_count=0, song_count=1))

        if not result.succeeded:
            await ctx.send(f"An error has occurred while searching for **{query}**. Code: {result.error_code}.")
            return

        songs = result.songs

        if len(songs) == 0:
            await ctx.send(f"No track found for **{query}**.")
            return

        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client is None:
            try:
                voice_client = await ctx.author.voice.channel.connect(timeout=10.0, reconnect=True)
            except Exception as e:
                await ctx.send(f"Failed to connect to voice channel: {e}")
                return

        player.channel = ctx.channel
        player.queue.insert(0, songs[0])
        await ctx.send(f"Queued **{songs[0].title}** by {songs[0].artist}")
        await player.play_audio_queue(voice_client)



    @commands.command(name="s")
    async def skip_prefix(self, ctx: commands.Context):
        ''' Skip the current track - prefix version '''

        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if voice_client is None:
            await ctx.send("I am not connected to a voice channel.")
            return

        if not voice_client.is_playing():
            await ctx.send("I am not currently playing anything.")
            return

        player = data.guild_data(ctx.guild.id).player
        player.channel = ctx.channel
        await player.skip_track(voice_client)
        await ctx.send(f"Track skipped - now playing **{player.current_song.title}** by {player.current_song.artist}")


    
    @commands.command(name="q")
    async def queue_prefix(self, ctx: commands.Context):
        ''' View the current queue - prefix version '''

        queue = data.guild_data(ctx.guild.id).player.queue

        output = ""

        if data.guild_data(ctx.guild.id).player.current_song is not None:
            song = data.guild_data(ctx.guild.id).player.current_song
            output += f"**Now Playing:**\n{song.title} - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"

        for i, song in enumerate(queue):
            strtoadd = f"{i+1}. **{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"
            if len(output+strtoadd) < 1990:
                output += strtoadd
            else:
                remaining = len(queue) - i
                output += f"**And {remaining} more...**"
                break

        if output == "":
            output = "Queue is empty!"

        await ctx.send(output)



    async def play_querytype_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> List[str]:
        options =  [
            "track",
            "album",
            "playlist"
        ]
        return [
            app_commands.Choice(name=option.capitalize(), value=option)
            for option in options if current.lower() in option.lower()
        ]
    
    async def play_query_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> List[str]:
        choices = []
        if 'querytype' not in interaction.namespace or interaction.namespace['querytype'] == "track":
            if current == "":
                songs = await subsonic.get_random_songs(size=env.BOT_SEARCH_SUGGESTION_COUNT)
            else:
                songs = (await subsonic.search(current, artist_count=0, album_count=0, song_count=env.BOT_SEARCH_SUGGESTION_COUNT)).songs
            choices = [
                app_commands.Choice(name=f"{song.artist} - {song.title}", value=f"{song.artist} {song.title}")
                for song in songs
            ]
        elif interaction.namespace['querytype'] == "album":
            if current == "":
                albums = await subsonic.list_albums("random", size=env.BOT_SEARCH_SUGGESTION_COUNT)
            else:
                albums = (await subsonic.search(current, artist_count=0, album_count=env.BOT_SEARCH_SUGGESTION_COUNT, song_count=0)).albums
            choices = [
                app_commands.Choice(name=f"{album.artist} - {album.name}", value=f"{album.artist} {album.name}")
                for album in albums
            ]
        elif interaction.namespace['querytype'] == "playlist":
            playlists = await subsonic.get_user_playlists()
            choices = [
                app_commands.Choice(name=playlist["name"], value=playlist["name"])
                for playlist in playlists if current.lower() in playlist["name"].lower()
            ]
            del choices[env.BOT_SEARCH_SUGGESTION_COUNT:]
        return choices

    @app_commands.command(name="play", description="Plays a specified track, album or playlist")
    @app_commands.describe(querytype="Whether what you're searching is a track, album or playlist", query="Enter a search query")
    @app_commands.autocomplete(querytype=play_querytype_autocomplete)
    @app_commands.autocomplete(query=play_query_autocomplete)
    async def play(self, interaction: Interaction, querytype: str=None, query: str=None) -> None:
        ''' Play a track matching the given title/artist query '''

        # Check if user is in voice channel
        if interaction.user.voice is None:
            await ui.ErrMsg.user_not_in_voice_channel(interaction)
            return

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(interaction, should_connect=True)

        if voice_client is None:
            return

        # Don't attempt playback if the bot is already playing
        if voice_client.is_playing() and query is None:
            await ui.ErrMsg.already_playing(interaction)
            return

        # Get the guild's player
        player = data.guild_data(interaction.guild_id).player
        player.channel = interaction.channel

        # Check queue if no query is provided
        if query is None:

            # Display error if queue is empty & autoplay is disabled
            if player.queue == [] and data.guild_properties(interaction.guild_id).autoplay_mode == data.AutoplayMode.NONE:
                await ui.ErrMsg.queue_is_empty(interaction)
                return

            # Begin playback of queue
            await ui.SysMsg.starting_queue_playback(interaction)
            await player.play_audio_queue(voice_client)
            return

        # Check if the query is a track or empty (default to track search if empty)
        if querytype == "track" or querytype == None:

            # Send our query to the subsonic API and retrieve a list of 1 song
            songs = (await subsonic.search(query, artist_count=0, album_count=0, song_count=1)).songs
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

            try:
                response = await subsonic.search(query, artist_count=0, album_count=1, song_count=0)
            except subsonic.APIError as e:
                logger.error(f"An API error has occurred while searching for an album, code {e.code}: {e.message}")
                await ui.ErrMsg.msg(interaction, "An API error has occurred and has been logged to console. Please contact an administrator.")
                return

            if len(response.albums) == 0:
                await ui.ErrMsg.msg(interaction, f"No album found for **{query}**.")
                return
            
            album = await subsonic.get_album(response.albums[0].id)

            for song in album.songs:
                player.queue.append(song)
            
            await ui.SysMsg.added_album_to_queue(interaction, album)

        elif querytype == "playlist":

            # Send query to subsonic API and retrieve a list of all playlists
            playlists = await subsonic.get_user_playlists()
            if playlists == None:
                await ui.ErrMsg.msg(interaction, f"No playlists found.")
                return
            
            # Check if the specific playlist exists and get it's contents
            playlist = None
            playlist_id = None
            for playlist in playlists:
                if playlist["name"] == query:
                    playlist_id = playlist["id"]
                    break
            if playlist_id == None:
                await ui.ErrMsg.msg(interaction, f"No playlist found for **{query}**.")
                return
            else:
                playlist = await subsonic.get_playlist(playlist_id)
            if playlist == None:
                # If we end up here then the following error message doesn't really cover it... It's more likely an error in this code
                await ui.ErrMsg.msg(interaction, f"No playlist found for **{query}**.")
                return
            
            # Add all songs from the playlist to the queue
            for song in playlist.songs:
                player.queue.append(song)
            
            await ui.SysMsg.added_playlist_to_queue(interaction, playlist)

        await player.play_audio_queue(voice_client)

    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred playing a track, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing a track: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")



    @app_commands.command(name="next", description="Searches for a track and places it next in the queue")
    @app_commands.describe(query="Enter a search query")
    async def play_next(self, interaction: Interaction, query: str) -> None:
        ''' Search for a track and place it next in the queue '''
        # This is a duplication of efforts made in the normal play function.
        # TODO: Fix it.

        voice_client = await self.get_voice_client(interaction, should_connect=True)
        player = data.guild_data(interaction.guild_id).player

        songs = (await subsonic.search(query, artist_count=0, album_count=0, song_count=1)).songs
        if songs == "Error":
            await ui.ErrMsg.msg(interaction, f"An api error has occurred and has been logged to console. Please contact an administrator.")
            return

        if len(songs) == 0:
            await ui.ErrMsg.msg(interaction, f"No track found for **{query}**.")
            return
  
        player.queue.insert(0,songs[0])
        await player.play_audio_queue(voice_client)

        await ui.SysMsg.added_to_queue(interaction, songs[0])



    @app_commands.command(name="stop", description="Stop playing the current track")
    async def stop(self, interaction: Interaction) -> None:
        ''' Disconnect from the active voice channel '''

        player = data.guild_data(interaction.guild_id).player

        if player.current_song is None:
            await ui.ErrMsg.not_playing(interaction)
            return

        # Get the voice client instance for the current guild
        voice_client = await self.get_voice_client(interaction)

        # Check if our voice client is connected
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Stop playback
        player.stop(voice_client)

        # Display disconnect confirmation
        await ui.SysMsg.stopping_queue_playback(interaction)

    @stop.error
    async def stop_error(self, ctx, error):
        logging.error(f"An error occurred while stopping playback: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")



    @app_commands.command(name="queue", description="View the current queue")
    async def show_queue(self, interaction: Interaction) -> None:
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
    async def clear_queue(self, interaction: Interaction) -> None:
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
    async def skip(self, interaction: Interaction) -> None:
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

        player = data.guild_data(interaction.guild_id).player
        player.channel = interaction.channel
        await player.skip_track(voice_client)

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
    async def autoplay(self, interaction: Interaction, mode: app_commands.Choice[str]) -> None:
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
            player.channel = interaction.channel

            logger.debug(f"Queue: {player.queue}")
            try:
                logger.debug(f"Current song: {player.current_song.title}")
            except AttributeError:
                logger.debug("No current song")
                
            logger.debug("Playing audio queue...")
            await player.play_audio_queue(voice_client)
        
    @autoplay.error
    async def autoplay_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while toggling autoplay, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while toggling autoplay: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")



    @app_commands.command(name="shuffle", description="Shuffles the current queue")
    async def shuffle(self, interaction: Interaction):
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



    async def disco_artist_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> List[str]:
        artists = (await subsonic.search(current, artist_count=env.BOT_SEARCH_SUGGESTION_COUNT, album_count=0, song_count=0)).artists
        return [
            app_commands.Choice(name=artist.name, value=artist.name)
            for artist in artists
        ]

    @app_commands.command(name="disco", description="Plays the artist's entire discography")
    @app_commands.describe(artist="The artist to play")
    @app_commands.autocomplete(artist=disco_artist_autocomplete)
    async def disco(self, interaction: Interaction, artist: str):
        ''' Play the artist's entire discography'''

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(interaction, should_connect=True)

        # Get the guild's player
        player = data.guild_data(interaction.guild_id).player
        player.channel = interaction.channel

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
        await player.play_audio_queue(voice_client)

    @disco.error
    async def disco_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while playing an artist's discography, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing an artist's discography: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")



    @app_commands.command(name="playlists", description="List all playlists")
    async def list_playlists(self, interaction):
        # Send query to subsonic API and retrieve a list of all playlists
        playlists = await subsonic.get_user_playlists()
        if playlists == None:
            await ui.ErrMsg.msg(interaction, f"No playlists found.")
            return

        # Create a string to store the output
        output = ""

        # Loop over the list of playlists, adding each one into our output string
        for i, playlist in enumerate(playlists):
            strtoadd = f"{i+1}. **{playlist['name']}** \n{playlist['songCount']} songs - {(playlist['duration'] // 60):02d}m {(playlist['duration'] % 60):02d}s\n\n"
            if len(output+strtoadd) < 4083:
                output += strtoadd
            else:
                remaining = len(playlists) - i
                output += f"**And {remaining} more...**"
                break

        # Check if our output string is empty & update it accordingly
        if output == "":
            output = "No playlists found."

        # Show the user the list
        await ui.SysMsg.msg(interaction, "Available playlists", output)

    @list_playlists.error
    async def playlists_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while fetching playlists, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while fetching playlists: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")



    async def list_playlist_query_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> List[str]:
        playlists = await subsonic.get_user_playlists()
        playlists = [
            app_commands.Choice(name=playlist["name"], value=playlist["name"])
            for playlist in playlists if current.lower() in playlist["name"].lower()
        ]
        del playlists[env.BOT_SEARCH_SUGGESTION_COUNT:]
        return playlists

    @app_commands.command(name="playlist", description="List tracks in the given playlist")
    @app_commands.describe(query="Enter the name of a playlist", page="The page to view")
    @app_commands.autocomplete(query=list_playlist_query_autocomplete)
    async def list_playlist(self, interaction, query: str=None, page: int=1):
        if query == None:
            await ui.ErrMsg.msg(interaction, f"Please provide the name of a playlist.")
            return

        # Send query to subsonic API and retrieve a list of all playlists
        playlists = await subsonic.get_user_playlists()
        if playlists == None:
            await ui.ErrMsg.msg(interaction, f"No playlists found.")
            return

        # Search for a playlist matching the given name
        found_playlist_id = None
        for playlist in playlists:
            if playlist["name"] == query:
                found_playlist_id = playlist["id"]
                break
        if found_playlist_id == None:
            await ui.ErrMsg.msg(interaction, "No playlist with that name was found.")
            return
        
        found_playlist = await subsonic.get_playlist(found_playlist_id)
        if len(found_playlist.songs) < 1:
            await ui.ErrMsg.msg(interaction, "Playlist is empty.")
            return
        
        # Paginate playlists
        paginated_tracks = ListPaginator(found_playlist.songs, 20)
        if len(paginated_tracks.pages) < page:
            await ui.ErrMsg.msg(interaction, "Page does not exist.")
            return
        
        # Assemble output
        output = f"{found_playlist.song_count} songs - {found_playlist.duration_printable}\n\n"
        for i, pag_item in enumerate(paginated_tracks.pages[page - 1]):
            song = pag_item["data"]
            song_number = pag_item["input_index"] + 1
            output += f"{song_number}. {song.artist} - **{song.title}** {(song.duration // 60):02d}m {(song.duration % 60):02d}s\n\n"
        output += f"Page {page} of {paginated_tracks.num_pages}"

        await ui.SysMsg.msg(interaction, "Playlist '"+found_playlist.name+"'", output)



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
            await asyncio.sleep(10)
            
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
