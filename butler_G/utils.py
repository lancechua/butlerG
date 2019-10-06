"""Utility Functions"""
import os
import time

import psycopg2
import psycopg2.extensions as ppg_ext
from telegram import ChatAction
from telegram.ext.dispatcher import run_async

import credentials as creds


def add_doc(value):
    """Decorator to add documentation to a function"""

    def _doc(func):
        func.__doc__ = value
        return func

    return _doc


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
def start_db_proxy():
    """Start database proxy"""
    with open("start_db_proxy.bat", "w") as f:
        f.write(
            'call "{}" -instances={}=tcp:{} -credential_file "{}"'.format(
                creds.DB_PROXY_EXE,
                creds.DB_CONN_NAME,
                creds.DB_PORT,
                creds.GCP_CREDS_FILE,
            )
        )
    os.system("start /B start cmd.exe @cmd /k start_db_proxy.bat")


@run_async
def execute_query(conn, query, query_data=None, commit=False, fetch=False):
    """Execute query"""

    if not conn.closed:
        status = conn.get_transaction_status()
        if status == ppg_ext.TRANSACTION_STATUS_UNKNOWN:
            # server connection lost
            conn.reset()
        elif status != ppg_ext.TRANSACTION_STATUS_IDLE:
            # connection in error or in transaction
            conn.rollback()
            conn.reset()

    cursor = conn.cursor()
    cursor.execute(query, query_data)
    data = cursor.fetchall() if fetch else None
    cursor.close()
    if commit:
        conn.commit()

    return data


def add_cursor_w_reset(conn):
    """Adds `cursor_w_reset` method to `psycopg2` `connection` object"""

    @add_doc(
        (
            "Similar to cursor, but checks first if connection is alive\n\n"
            "Docstring of `psycopg2` `cursor` for reference:\n\n{}"
        ).format(conn.cursor.__doc__)
    )
    def cursor_w_reset(self, *args, **kwargs):
        if not self.closed:
            status = self.get_transaction_status()
            if status == ppg_ext.TRANSACTION_STATUS_UNKNOWN:
                # server connection lost
                self.reset()
            elif status != ppg_ext.TRANSACTION_STATUS_IDLE:
                # connection in error or in transaction
                self.rollback()
                self.reset()

        return self.cursor(*args, **kwargs)

    setattr(conn, "cursor_w_reset", cursor_w_reset)
    return conn

