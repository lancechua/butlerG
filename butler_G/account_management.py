"""
Account Management Module

Has functions to deal with user registration etc.
"""
import functools
import logging

from telegram.ext import ConversationHandler

from . import constants as const
from . import credentials as creds
from . import utils
from . import db

DB_CLIENT = db.Client(const.DBSVC_URL)


def _setup():
    """Set up `users` table in database"""
    DB_CLIENT.send_query(
        """
        CREATE TABLE users(
            id integer NOT NULL,
            gender text NOT NULL
        );
        """,
        commit=True,
    )


def register(update, context):
    # TODO (lance.chua): ask user for code
    raise NotImplementedError


def validate_id(id: int):
    """Check if id exists in `users` table"""
    return DB_CLIENT.send_query(
        """
        SELECT COUNT(id) > 0 FROM users
        WHERE id = %(id)s
        LIMIT 1;
        """,
        query_data=locals(),
        fetch=True,
    )[0][0]


def _validate_code(update, context):
    # TODO (lance.chua): compare hmac(secret, id) vs code provided
    raise NotImplementedError


def _add_user(id: int, gender: str):
    """Add user to `users` table"""
    DB_CLIENT.send_query(
        "INSERT INTO users (id, gender) " "VALUES (%(id)s, %(gender)s)",
        query_data=locals(),
        commit=True,
    )


def _remove_user(id: int):
    """Remove user from `users` table"""
    DB_CLIENT.send_query(
        "DELETE FROM users WHERE id = %(id)s", query_data=locals(), commit=True
    )


def check_sender(report=True):
    """Decorator to check if update sender is valid."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(update, context, *args, **kwargs):
            if validate_id(update.effective_user.id):
                return func(update, context, *args, **kwargs)
            else:
                msg = '!!! ATTN: Access attempt !!!\n  name: "{}"\n  id: "{}"'.format(
                    update.effective_user.name, update.effective_user.id
                )

                logging.getLogger(__name__).critical(msg)
                update.message.reply_text(
                    "You do not have access to this bot. :(\n"
                    "Thank you and have a nice day! :)"
                )

                if report:
                    context.bot.send_message(creds.DEV_CHATID, msg)

                return ConversationHandler.END

        return wrapper

    return decorator
