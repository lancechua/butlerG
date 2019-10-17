"""Utility Functions"""
import time

from telegram import ChatAction
from telegram.ext.dispatcher import run_async


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
@run_async
def execute_query(conn, query, query_data=None, commit=False, fetch=False):
    """Execute query.

    `fetch` and `commit` are assumed to be False by default.
    """

    cursor = conn.cursor()
    cursor.execute(query, query_data)
    data = cursor.fetchall() if fetch else None
    cursor.close()
    if commit:
        conn.commit()

    return data
