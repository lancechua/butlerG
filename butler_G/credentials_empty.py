"""Credentials
Modify credentials based on `constants.DEV_MODE`

NOTE: This is an EMPTY credentials file.
Please input your own credentials and rename as "credentials.py"
"""

from .constants import DEV_MODE


TELEGRAM_API_TOKEN = "YOUR_API_TOKEN"

# DATABASE INFO

## Please supply your own database credentials
DB_CREDS = {"user": "user", "password": "password", "host": "host", "port": "port"}


# ERRORS CHAT
## These parameters are optional, and are only for "flavor"

## Telegram Errors Chat ID, bot must be part of the group
DEV_CHATID = ...

## Person to be blamed for bugs
DEV_NAME = "Some poor sap..."

## Flavor GIF response
ERROR_WEBP = "http://giphygifs.s3.amazonaws.com/media/Rhhr8D5mKSX7O/giphy.gif"
