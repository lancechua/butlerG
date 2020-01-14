"""Utility Functions"""
import functools
import logging
import time

import psycopg2
from telegram import ChatAction
from telegram.ext.dispatcher import run_async


def add_doc(value):
    """Decorator to add documentation to a function"""

    def _doc(func):
        func.__doc__ = value
        return func

    return _doc


def validator(valid_values, prev_handler):
    """Decorator to validate user reply for handlers

    Parameters
    ----------
    val_dict: callable or collection
        if callable, should return True if value is valid
        collection of valid responses (ideally a set)
    prev_handler: callable
        entry handler representing the "Question" state

    Returns
    ----------
    state
        if reply is valid, func return value, otherwise func's entry state

    Notes
    ----------
    Decorate at function handling the reponse
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(update, context, *args, **kwargs):
            check_pass = (
                valid_values(update.message.text)
                if callable(valid_values)
                else (update.message.text in valid_values)
            )
            if check_pass:
                return func(update, context, *args, **kwargs)
            else:
                update.message.reply_text(
                    'Does "{}" seem to answer my question?\nLet me ask again...'.format(
                        update.message.text
                    )
                )
                return prev_handler(update, context, *args, **kwargs)

        return wrapper

    return decorator


# Telegram utils
def gen_keyboard(items, columns=None, max_char_len=None):
    """Generate keyboard with shape based on columns and character length

    Parameters
    ==========
    items : list
    columns: int , optional
        number of columns for keyboard;
        if `columns` and `max_char_len` are not specified, defaults to 1
    max_char_len : int, optional

    Returns
    =======
    list of list of str

    Notes
    =====
    Both `columns` and max_char_len` are unspecified, generates keyboard with 1 columns
    Otherwise, the more restrictive of the two parameters is applied to the row
    """
    columns = 1 if (columns is None) and (max_char_len is None) else (columns or 99999)
    max_char_len = max_char_len or 99999

    keyboard = []
    cur_row = []
    for item in items:
        if (len(cur_row) >= columns) or (
            sum(map(len, cur_row + [item])) >= max_char_len
        ):
            keyboard.append(cur_row)
            cur_row = [item]
        else:
            cur_row.append(item)

    if cur_row:
        keyboard.append(cur_row)

    return keyboard


@run_async
def send_typing(update, context, sleep=0):
    """Send Typing action, with sleep feature"""
    res = context.bot.send_chat_action(
        chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
    )
    time.sleep(sleep)
    return res


# DB utils
@run_async
def execute_query(conn, query, query_data=None, commit=False, fetch=False):
    """Execute SQL query

    Parameters
    ----------
    conn
    query: str
        passed as first argument to `cursor.execute()`
    query_data
        passed as second argument to `cursor.execute()`; defaults to None
    commit: bool
        flag whether to run `conn.commit()`; defaults to `False`
    fetch: bool
        flag whether to run `cursor.fetchall()`; defaults to `False`

    Returns
    ----------
    query result if `fetch` is True

    Notes
    ----------
    Meant to be used when the bot is running as it is decorated with `@run_async`
    Would NOT recommend for functions ran "outside" the bot (e.g. database setup functions)
    """

    cursor = conn.cursor()
    cursor.execute(query, query_data)
    data = cursor.fetchall() if fetch else None
    cursor.close()
    if commit:
        conn.commit()

    return data


class ConnWithRecon(object):
    """Postgres Connection with Reconnect using psycopg2"""

    def __init__(self, *args, **kwargs):
        """
        Parameters
        ----------
        *args, **kwargs
            arguments passed to psycopg2.connect

        Notes
        -----
        Catch Errors using `psycopg2.OperationalError`
        """
        self.conn = psycopg2.connect(*args, **kwargs)
        self.init_args = args
        self.init_kwargs = kwargs

    def __getattr__(self, attr):
        logger = logging.getLogger()
        if self.conn.closed:
            self.reconnect()
        else:
            status = self.conn.get_transaction_status()
            if status == psycopg2._ext.TRANSACTION_STATUS_UNKNOWN:
                logger.info("connection tx status unknown. Restarting...")
                # server connection lost
                self.conn.close()
                self.reconnect()

            elif status >= psycopg2._ext.TRANSACTION_STATUS_INTRANS:
                # connection in error
                logger.info("connection in error. Rolling back...")
                self.conn.rollback()

        return getattr(self.conn, attr)

    def commit(self):
        """commit, since it doesn't seem to work with __getattr__"""
        return self.conn.commit()

    def reconnect(self):
        """Reconnect using initialization parameters"""
        self.conn = psycopg2.connect(*self.init_args, **self.init_kwargs)
