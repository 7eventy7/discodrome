''' For interfacing with the Subsonic API '''

import logging
import os
import aiohttp
import hashlib
import secrets

from pathlib import Path

from util import env

logger = logging.getLogger(__name__)


def _get_auth_params() -> dict:
    """
    Generate authentication parameters based on SUBSONIC_AUTH_MODE.
    
    Supports two authentication modes:
    - plaintext: Uses password directly (API v1.15.0)
    - token: Uses MD5(password + salt) for enhanced security (API v1.16.0)
    
    Returns:
        dict: Authentication parameters including username, version, client name,
              format, and either password (plaintext mode) or token+salt (token mode)
    """
    auth_params = {
        "u": env.SUBSONIC_USER,
        "c": "discodrome",
        "f": "json"
    }
    
    if env.SUBSONIC_AUTH_MODE == "token":
        # Use token-based authentication with salt
        # Generate a new salt for each request for security
        salt = secrets.token_hex(16)
        # Note: MD5 is used here because it's required by the Subsonic API specification,
        # despite being cryptographically weak. This is a protocol requirement.
        token = hashlib.md5((env.SUBSONIC_PASSWORD + salt).encode()).hexdigest()
        auth_params["t"] = token
        auth_params["s"] = salt
        auth_params["v"] = "1.16.0"
    else:
        # Use plaintext authentication (default)
        auth_params["p"] = env.SUBSONIC_PASSWORD
        auth_params["v"] = "1.15.0"
    
    return auth_params

globalsession = None

async def get_session() -> aiohttp.ClientSession:
    ''' Get an aiohttp session '''
    global globalsession
    if globalsession is None:
        globalsession = aiohttp.ClientSession()
    return globalsession

async def close_session() -> None:
    ''' Close the aiohttp session '''
    global globalsession
    if globalsession is not None:
        globalsession.close()
        globalsession = None

class APIError(Exception):
    ''' Exception raised for errors in the Subsonic API '''
    def __init__(self, errorcode: int, message: str) -> None:
        self.errorcode = errorcode
        self.message = message
        super().__init__(self.message)

class Song():
    ''' Object representing a song returned from the Subsonic API '''
    def __init__(self, json_object: dict) -> None:
        #! Other properties exist in the initial json response but are currently unused by Discodrome and thus aren't supported here
        self._id: str = json_object["id"] if "id" in json_object else ""
        self._title: str = json_object["title"] if "title" in json_object else "Unknown Track"
        self._album: str = json_object["album"] if "album" in json_object else "Unknown Album"
        self._artist: str = json_object["artist"] if "artist" in json_object else "Unknown Artist"
        self._cover_id: str = json_object["coverArt"] if "coverArt" in json_object else ""
        self._duration: int = json_object["duration"] if "duration" in json_object else 0

    @property
    def song_id(self) -> str:
        ''' The song's id '''
        return self._id

    @property
    def title(self) -> str:
        ''' The song's title '''
        return self._title

    @property
    def album(self) -> str:
        ''' The album containing the song '''
        return self._album

    @property
    def artist(self) -> str:
        ''' The song's artist '''
        return self._artist

    @property
    def cover_id(self) -> str:
        ''' The id of the cover art used by the song '''
        return self._cover_id

    @property
    def duration(self) -> int:
        ''' The total duration of the song '''
        return self._duration

    @property
    def duration_printable(self) -> str:
        ''' The total duration of the song as a human readable string in the format `mm:ss` '''
        return f"{(self._duration // 60):02d}:{(self._duration % 60):02d}"

class Album():
    ''' Object representing an album returned from subsonic API '''
    def __init__(self, json_object: dict) -> None:
        self._id: str = json_object["id"] if "id" in json_object else ""
        self._name: str = json_object["name"] if "name" in json_object else "Unknown Album"
        self._artist: str = json_object["artist"] if "artist" in json_object else "Unknown Artist"
        self._cover_id: str = json_object["coverArt"] if "coverArt" in json_object else ""
        self._song_count: int = json_object["songCount"] if "songCount" in json_object else 0
        self._duration: int = json_object["duration"] if "duration" in json_object else 0
        self._year: int = json_object["year"] if "year" in json_object else 0
        self._songs: list[Song] = []
        for song in json_object["song"]:
            self._songs.append(Song(song))
    
    @property
    def album_id(self) -> str:
        ''' The album's id '''
        return self._id
    
    @property
    def name(self) -> str:
        ''' The album's name '''
        return self._name
    
    @property
    def artist(self) -> str:
        ''' The album's artist '''
        return self._artist
    
    @property
    def cover_id(self) -> str:
        ''' The id of the cover art used by the album '''
        return self._cover_id
    
    @property
    def song_count(self) -> int:
        ''' The number of songs in the album '''
        return self._song_count
    
    @property
    def duration(self) -> int:
        ''' The total duration of the album '''
        return self._duration
    
    @property
    def duration_printable(self) -> str:
        ''' The total duration of the album as a human readable string in the format `mm:ss` '''
        return f"{(self._duration // 60):02d}:{(self._duration % 60):02d}"
    
    @property
    def year(self) -> int:
        ''' The year the album was released '''
        return self._year
    
    @property
    def songs(self) -> list[Song]:
        ''' The songs in the album '''
        return self._songs
    
class Playlist():
    ''' Object representing a playlist returned from subsonic API '''
    def __init__(self, json_object: dict) -> None:
        self._id: str = json_object["id"] if "id" in json_object else ""
        self._name: str = json_object["name"] if "name" in json_object else "Unknown Album"
        self._cover_id: str = json_object["coverArt"] if "coverArt" in json_object else ""
        self._song_count: int = json_object["songCount"] if "songCount" in json_object else 0
        self._duration: int = json_object["duration"] if "duration" in json_object else 0
        self._songs: list[Song] = []
        for song in json_object["entry"]:
            self._songs.append(Song(song))
    
    @property
    def playlist_id(self) -> str:
        ''' The playlist's id '''
        return self._id
    
    @property
    def name(self) -> str:
        ''' The playlist's name '''
        return self._name
    
    @property
    def cover_id(self) -> str:
        ''' The id of the cover art used by the playlist '''
        return self._cover_id
    
    @property
    def song_count(self) -> int:
        ''' The number of songs in the playlist '''
        return self._song_count
    
    @property
    def duration(self) -> int:
        ''' The total duration of the playlist '''
        return self._duration
    
    @property
    def duration_printable(self) -> str:
        ''' The total duration of the playlist as a human readable string in the format `mm:ss` '''
        return f"{(self._duration // 60):02d}:{(self._duration % 60):02d}"
    
    @property
    def songs(self) -> list[Song]:
        ''' The songs in the playlist '''
        return self._songs

async def ping_api() -> bool:
    ''' Send a ping request to the subsonic API '''

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/ping.view", params=_get_auth_params()) as response:
        response.raise_for_status()
        ping_data = await response.json()
        if await check_subsonic_error(ping_data):
            return False
        logger.debug("Ping Response: %s", ping_data)
    
    return True

async def check_subsonic_error(response: dict[str, any]) -> bool:
    ''' Checks and logs error codes returned by the subsonic API. Returns true if an error is present '''

    logging.debug("Checking for subsonic error...")
    if isinstance(response, aiohttp.ClientResponse):
        try:
            response = await response.json()
        except Exception as e:
            return False

    if response["subsonic-response"]["status"] == "ok":
        logging.debug("No error found.")
        return False
    
    err_code = response["subsonic-response"]["error"]["code"]
    match err_code:
        case 0:
            err_msg = "Generic Error."
            raise APIError(err_code, err_msg)
        case 10:
            err_msg = "Required Parameter Missing."
            raise APIError(err_code, err_msg)
        case 20:
            err_msg = "Incompatible Subsonic REST protocol version. Client must upgrade."
            raise APIError(err_code, err_msg)
        case 30:
            err_msg = "Incompatible Subsonic REST protocol version. Server must upgrade."
            raise APIError(err_code, err_msg)
        case 40:
            err_msg = "Wrong username or password."
            raise APIError(err_code, err_msg)
        case 41:
            err_msg = "Token authentication not supported for LDAP users."
            raise APIError(err_code, err_msg)
        case 50:
            err_msg = "User is not authorized for the given operation."
            raise APIError(err_code, err_msg)
        case 60:
            err_msg = "The trial period for the Subsonic server is over."
            raise APIError(err_code, err_msg)
        case 70:
            err_msg = "The requested data was not found."
        case _:
            err_msg = "Unknown Error Code."
            raise APIError(err_code, err_msg)

    logger.warning("Subsonic API request responded with error code %s: %s", err_code, err_msg)
    return True

async def search(query: str, *, artist_count: int=00, artist_offset: int=0, album_count: int=0, album_offset: int=0, song_count: int=1, song_offset: int=0) -> list[Song]:
    ''' Send a search request to the subsonic API '''

    # Sanitize special characters in the user's query
    #parsed_query = urlParse.quote(query, safe='')

    search_params = {
        "query": query, #todo: fix parsed query
        "artistCount": str(artist_count),
        "artistOffset": str(artist_offset),
        "albumCount": str(album_count),
        "albumOffset": str(album_offset),
        "songCount": str(song_count),
        "songOffset": str(song_offset)
    }

    params = _get_auth_params() | search_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/search3.view", params=params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return []
        logger.debug("Search Response: %s", search_data)            
    
    results: list[Song] = []

    try:
        for item in search_data["subsonic-response"]["searchResult3"]["song"]:
            results.append(Song(item))
    except KeyError:
        return []

    return results

async def search_album(query: str) -> list[Album]:
    ''' Send a search request to the subsonic API to return 1 album and all its songs '''

    # Sanitize special characters in the user's query
    #parsed_query = urlParse.quote(query, safe='')

    search_params = {
        "query": query,
        "artistCount": "0",
        "albumCount": "1",
        "albumOffset": "0",
        "songCount": "0",
        "songOffset": "0"
    }

    params = _get_auth_params() | search_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/search3.view", params=params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return None
        try:
            albumid = search_data["subsonic-response"]["searchResult3"]["album"][0]["id"]
        except Exception as e:
            return None
        logger.debug("Album ID: %s", albumid)
    
    album_params = {
        "id": albumid
    }

    album_params = _get_auth_params() | album_params

    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getAlbum.view", params=album_params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return None
        logger.debug("Search Response: %s", search_data)


    try:
        album = Album(search_data["subsonic-response"]["album"])
    except Exception as e:
        logger.error("Failed to parse album data: %s", e)
        return None
    
    return album

async def get_user_playlists() -> list[int]:
    ''' Retrive metadata of all playlists the Subsonic user is authorised to play '''

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getPlaylists.view", params=_get_auth_params()) as response:
        response.raise_for_status()
        query_data = await response.json()
        if await check_subsonic_error(query_data):
            return None
        logger.debug("Playlists query response: %s", query_data)

    playlists = query_data["subsonic-response"]["playlists"]["playlist"]

    return playlists

async def get_playlist(id: str) -> Playlist:
    ''' Retrive the contents of a specific playlist '''

    playlist_params = {
        "id": id
    }

    params = _get_auth_params() | playlist_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getPlaylist.view", params=params) as response:
        response.raise_for_status()
        playlist = await response.json()
        if await check_subsonic_error(playlist):
            return None
        logger.debug("Playlist query response: %s", playlist)

    try:
        playlist = Playlist(playlist["subsonic-response"]["playlist"])
    except Exception as e:
        logger.error("Failed to parse playlist data: %s", e)
        return None
    
    return playlist

async def get_artist_id(query: str) -> str:
    ''' Send a search request to the subsonic API to return the id of an artist '''

    search_params = {
        "query": query,
        "artistCount": "1",
        "albumCount": "0",
        "albumOffset": "0",
        "songCount": "0",
        "songOffset": "0"
    }

    params = _get_auth_params() | search_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/search3.view", params=params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return None
        artistid = search_data["subsonic-response"]["searchResult3"]["artist"][0]["id"]
        logger.debug("Artist ID: %s", artistid)
    
    return artistid

async def get_artist_discography(query: str) -> Album:
    ''' Send a search request to the subsonic API to return all albums by an artist '''

    artistid = await get_artist_id(query)
    
    artist_params = {
        "id": artistid
    }

    artist_params = _get_auth_params() | artist_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getArtist.view", params=artist_params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return None
        logger.debug("Search Response: %s", search_data)
        albums = search_data["subsonic-response"]["artist"]["album"]
    
    album_list : list[Album] = []

    for albuminfo in albums:
        albumid = albuminfo["id"]
        album_params = {
            "id": albumid
        }
        album_params = _get_auth_params() | album_params
        async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getAlbum.view", params=album_params) as response:
            response.raise_for_status()
            album = await response.json()
            if await check_subsonic_error(album):
                return None
            logger.debug("Search Response: %s", album)
            album = Album(album["subsonic-response"]["album"])
            album_list.append(album)

    return album_list


async def get_album_art_file(cover_id: str, size: int=300) -> str:
    ''' Request album art from the subsonic API '''
    target_path = f"cache/{cover_id}.jpg"

    # Check if the cover art is already cached (TODO: Check for last-modified date?)
    if os.path.exists(target_path):
        return target_path

    cover_params = {
        "id": cover_id,
        "size": str(size)
    }

    params = _get_auth_params() | cover_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getCoverArt", params=params) as response:
        logging.debug("Response: %s", response.content)
        if await check_subsonic_error(response) or response.status != 200:
            return "resources/cover_not_found.jpg"

        file = Path(target_path)
        file.parent.mkdir(exist_ok=True, parents=True)
        file.write_bytes(await response.read())
        
    return target_path

async def get_random_songs(size: int=None, genre: str=None, from_year: int=None, to_year: int=None, music_folder_id: str=None) -> list[Song]:
    ''' Request random songs from the subsonic API '''
    logger.debug("Requesting random song...")
    search_params: dict[str, any] = {}

    # Handle Optional params
    if size is not None:
        search_params["size"] = size

    if genre is not None:
        search_params["genre"] = genre

    if from_year is not None:
        search_params["fromYear"] = from_year

    if to_year is not None:
        search_params["toYear"] = to_year

    if music_folder_id is not None:
        search_params["musicFolderId"] = music_folder_id


    params = _get_auth_params() | search_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getRandomSongs.view", params=params) as response:
        response.raise_for_status()
        search_data = await response.json()
        if await check_subsonic_error(search_data):
            return []
        logger.debug("Search Response: %s", search_data)

    results: list[Song] = []
    for item in search_data["subsonic-response"]["randomSongs"]["song"]:
        results.append(Song(item))

    return results

async def get_similar_songs(song_id: str, count: int=1) -> list[Song]:
    ''' Request similar songs from the subsonic API '''

    logger.debug("Requesting similar song...")
    logger.debug("Song id: %s", song_id)

    if song_id is None:
        return []

    search_params = {
        "id": song_id,
        "count": count
    }

    params = _get_auth_params() | search_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/getSimilarSongs.view", params=params) as response:
        response.raise_for_status()
        search_data = await response.json()
        logging.debug("Json Response: %s", search_data)
        subsonic_error = await check_subsonic_error(search_data)
        logger.debug("Subsonic error: %s", subsonic_error)
        if subsonic_error:
            logger.debug("Subsonic error. Returning empty list.")
            return []

    results: list[Song] = []
    
    if search_data["subsonic-response"]["similarSongs"] == {}:
        logging.debug("No similar songs found. Returning empty list.")
        return []
    
    logger.debug("Similar songs: %s", search_data["subsonic-response"]["similarSongs"]["song"])
    for item in search_data["subsonic-response"]["similarSongs"]["song"]:
        results.append(Song(item))

    logger.debug("Similar songs: %s", results)
    return results

async def stream(stream_id: str):
    ''' Send a stream request to the subsonic API '''

    stream_params = {
        "id": stream_id
        # TODO: handle other params
    }

    params = _get_auth_params() | stream_params

    session = await get_session()
    async with await session.get(f"{env.SUBSONIC_SERVER}/rest/stream.view", params=params, timeout=20) as response:
        response.raise_for_status()
        if response.content_type == "text/xml":
            logger.error("Failed to stream song: %s", await response.text())
            return None
        return str(response.url)
