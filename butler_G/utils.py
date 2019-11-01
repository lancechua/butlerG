"""Utility Functions"""
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


class ConnWithRecon(object):
    def __init__(self, *args, **kwargs):
        """Postgres Connection with Reconnect using psycopg2

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

            elif status != psycopg2._ext.TRANSACTION_STATUS_IDLE:
                # connection in error or in transaction
                logger.info("connection in error or in transaction. Rolling back...")
                self.conn.rollback()

        return getattr(self.conn, attr)

    def commit(self):
        """commit, since it doesn't seem to work with __getattr__"""
        return self.conn.commit()

    def reconnect(self):
        """Reconnect using initialization parameters"""
        self.conn = psycopg2.connect(*self.init_args, **self.init_kwargs)


def setup_tables(conn, expense_budgets=None):
    """Create and setup tables required in SQL database

    Parameters
    ----------
    conn
    expense_budgets: dict, optional
        structure:
        ```python
        expense_budgets = {
            "category_1": {
                "max_budget" : None or float,
                "tx_amount" : None or float
            },
            ...
        }
        ```
        default=`None`

    Notes
    -----
    This function is provided primarily as a reference
    """
    expense_budgets = expense_budgets or {}

    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE spend_log(
            username text NOT NULL,
            category text NOT NULL,
            amount real NOT NULL,
            notes text,
            tx_timestamp TIMESTAMP NOT NULL
        );
        """
    )
    conn.commit()

    cur.execute(
        """
    CREATE TABLE monthly_budgets(
        category text,
        max_budget real,
        max_tx_amount real
    );
    """
    )
    for cat, val_dict in expense_budgets.items():
        cur.execute(
            "INSERT INTO monthly_budgets (category, max_budget, max_tx_amount) "
            "VALUES (%(category)s, %(max_budget)s, %(tx_amount)s);",
            {**{"category": cat, "max_budget": None, "tx_amount": None}, **val_dict},
        )

    conn.commit()


def update_budget(conn, category: str, **kwargs):
    """Update budget tables

    Parameters
    ----------
    conn
    category : str
    **kwargs
        Optional keyword arguments, specify if values need to be updated
        * max_budget : float
        * max_tx_amount : float
    """
    assert set(kwargs.keys()) <= {"max_budget", "max_tx_amount"}
    exec_kwargs = {**{"category": category}, **kwargs}

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE monthly_budgets
        SET {}
        WHERE category LIKE %(category)s;
        """.format(
            ",".join(["{0} = %({0})s".format(col) for col in kwargs.keys()])
        ),
        vars=exec_kwargs,
    )
    conn.commit()
