"""
Account Management Module

Has functions to deal with user registration etc.
"""
import functools
import logging

from telegram.ext import ConversationHandler

from . import credentials as creds
from . import utils


_CONN = utils.ConnWithRecon(**creds.DB_CREDS)


def _setup():
    """Set up `users` table in database"""
    with _CONN.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE users(
                id integer NOT NULL,
                gender text NOT NULL
            );
            """
        )
        _CONN.commit()


def register(update, context):
    # TODO (lance.chua): ask user for code
    raise NotImplementedError


def validate_id(id: int):
    """Check if id exists in `users` table"""
    with _CONN.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(id) > 0 FROM users
            WHERE id = %(id)s
            LIMIT 1;
            """,
            locals(),
        )
        res = cursor.fetchall()
        return res[0][0]


def _validate_code(update, context):
    # TODO (lance.chua): compare hmac(secret, id) vs code provided
    raise NotImplementedError


def _add_user(id: int, gender: str):
    """Add user to `users` table"""
    with _CONN.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (id, gender) " "VALUES (%(id)s, %(gender)s)", locals()
        )
        _CONN.commit()


def _remove_user(id: int):
    """Remove user from `users` table"""
    with _CONN.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %(id)s", locals())
        _CONN.commit()


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

