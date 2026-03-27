import os

from typing import Final
from dotenv import load_dotenv

load_dotenv(os.path.relpath("data.env"))

DISCORD_BOT_TOKEN: Final[str] = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_TEST_GUILD: Final[str] = os.getenv("DISCORD_TEST_GUILD")
DISCORD_OWNER_ID: Final[int] = int(os.getenv("DISCORD_OWNER_ID"))

SUBSONIC_SERVER: Final[str] = os.getenv("SUBSONIC_SERVER")
SUBSONIC_USER: Final[str] = os.getenv("SUBSONIC_USER")
SUBSONIC_PASSWORD: Final[str] = os.getenv("SUBSONIC_PASSWORD")
SUBSONIC_AUTH_MODE: Final[str] = os.getenv("SUBSONIC_AUTH_MODE")

BOT_STATUS: Final[str] = os.getenv("BOT_STATUS")
BOT_PREFIX: Final[str] = os.getenv("BOT_PREFIX")
BOT_SEARCH_SUGGESTION_COUNT: Final[int] = int(os.getenv("BOT_SEARCH_SUGGESTION_COUNT", 5))
