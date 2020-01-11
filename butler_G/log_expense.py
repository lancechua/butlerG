"""
Log Expense Module

Contains various functions and handlers for the "Log Expense" task
"""
import calendar
from datetime import datetime
import logging
import random

from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler

from . import credentials as creds
from . import constants as const
from . import utils


_CONN = utils.ConnWithRecon(**creds.DB_CREDS)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def _setup():
    """Set up `spend_log` and `monthly_budgets` table in database"""
    cursor = _CONN.cursor()
    cursor.execute(
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
    cursor.execute(
        """
        CREATE TABLE monthly_budgets(
            category text,
            max_budget real,
            max_tx_amount real
        );
        """
    )
    _CONN.commit()


def _update_budgets(**EXPENSE_BUDGETS):
    """Clears and Updates `monthly_budgets` table

    Parameters
    ----------
    category: dict
        * value should be as follows:
        ```{
            "max_budget": float,
            "max_tx_amount": float
        }```
        * categories without budget can be ommitted

    Notes
    -----
    * Accepts only keyword arguments
    * Each keyword represents a category
    """
    cursor = _CONN.cursor()
    for cat, val_dict in EXPENSE_BUDGETS.items():
        logging.info({**{"category": cat}, **val_dict})

        cursor.execute(
            """
            UPDATE monthly_budgets
            SET {}
            WHERE category LIKE %(category)s;
            """.format(
                ",".join(["{0} = %({0})s".format(col) for col in val_dict])
            ),
            vars={**{"category": cat}, **val_dict},
        )

    _CONN.commit()


def get_category_log(update, context):
    """Handler to get Expense Category for Log Expense"""
    logger.info("Expense Category - Log Expense")
    return _get_category(update, context, mode="log")


def get_category_showtx(update, context):
    """Handler to get Expense Category for Show Transactions"""
    logger.info("Expense Category - Show TX")
    return _get_category(update, context, mode="show_tx")


def _get_category(update, context, mode="log"):
    """Handler that asks for Expense Category"""
    if mode == "log":
        cats = const.EXPENSE_CATEGORIES
        question = "What did you spend on now?"
        ret_val = const.EXPENSE_AMOUNT

    elif mode == "show_tx":
        cats = ["ALL"] + list(const.EXPENSE_CATEGORIES)
        question = "May I ask for which category?"
        ret_val = const.GET_TXNS

    else:
        raise ValueError("Invalid `mode` provided.")

    reply_markup = ReplyKeyboardMarkup(
        utils.gen_keyboard(cats, columns=2),
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    update.message.reply_text(question, reply_markup=reply_markup)
    return ret_val


@utils.validator(
    valid_values=const.EXPENSE_CATEGORIES, prev_handler=get_category_log
)
def get_amount(update, context):
    """Handler that asks for Expense Amount with budget warning"""
    logger.info("Expense Amount")
    utils.send_typing(update, context).result()

    cat = update.message.text
    cat_spd = (
        utils.execute_query(
            _CONN,
            "SELECT SUM(amount) FROM spend_log "
            "WHERE category=%(category)s "
            "AND tx_timestamp >= date_trunc('month', localtimestamp);",
            query_data={"category": cat},
            fetch=True,
        ).result()[0][0]
        or 0
    )
    cat_budget, cat_tx = (
        utils.execute_query(
            _CONN,
            "SELECT max_budget, max_tx_amount FROM monthly_budgets WHERE category=%(category)s;",
            query_data={"category": cat},
            fetch=True,
        ).result()
        or [[1e9, 1e9]]
    )[0]
    cat_budget = cat_budget or 1e9
    cat_tx = cat_tx or 1e9

    context.user_data["category"] = cat
    context.user_data["_category_spend"] = cat_spd
    context.user_data["_category_budget"] = cat_budget
    context.user_data["_category_tx"] = cat_tx

    logger.debug(context.user_data)

    if const.WARN_THRESH <= cat_spd / cat_budget <= 1:
        update.message.reply_text(
            (
                "Master, might I warn you that we are at {:.1%} of our {} budget. "
                "({:,.2f} of {:,.2f})"
            ).format(cat_spd / cat_budget, cat, cat_spd, cat_budget)
        )

    return _get_amount(update, context)



def _get_amount(update, context):
    """Basic get amount handler"""
    update.message.reply_text("How much did you spend?")
    return const.EXPENSE_NOTES


def get_notes(update, context):
    """Handler that asks for Expense Notes"""
    logger.info("Expense Notes")
    context.user_data["amount"] = update.message.text

    try:
        amt = float(context.user_data["amount"])
    except ValueError:
        update.message.reply_text('Does "{}" seem like a number to you?'.format(update.message.text))
        return _get_amount(update, context)

    if amt > context.user_data["_category_tx"]:
        update.message.reply_text(random.choice(const.LINES_SHAME))

    if (amt + context.user_data["_category_spend"]) / context.user_data[
        "_category_budget"
    ] >= const.WARN_THRESH:
        update.message.reply_text(
            "By the way, this transaction puts us at {:.1%} of our allocated budget for {}".format(
                (amt + context.user_data["_category_spend"])
                / context.user_data["_category_budget"],
                context.user_data["category"],
            )
        )
        # emphasize message above
        utils.send_typing(update, context, sleep=2).result()

    update.message.reply_text(
        'Do you have anything else to say for yourself?\n(Enter "no comment" otherwise)'
    )
    return const.REVIEW_EXPENSE_UPLOAD


def review_expense_upload(update, context):
    """Handler that asks user to confirm data before upload"""
    logger.info("Review Expense Upload")
    context.user_data["notes"] = update.message.text
    reply_markup = ReplyKeyboardMarkup(
        utils.gen_keyboard([const.YES, const.NO], columns=2),
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    update.message.reply_text(
        "Is the data below correct?:\n\n{}".format(
            "\n".join(
                [
                    "    {}: {}".format(key, val)
                    for key, val in context.user_data.items()
                    if not key.startswith("_")
                ]
            )
        ),
        reply_markup=reply_markup,
    )

    return const.UPLOAD_EXPENSE

@utils.validator(
    valid_values={const.YES, const.NO},
    prev_handler=review_expense_upload,
)
def upload_expense(update, context):
    """Handler that submits data for upload"""
    logger.info("Upload Expense")
    if update.message.text == const.YES:
        user = update.message.from_user
        update.message.reply_text(
            "Very well. I will submit the data for upload. Have a good day."
        )
        data_upload = context.user_data.copy()
        data_upload["tx_timestamp"] = datetime.now()
        data_upload["username"] = user.username or user.id

        # upload data
        utils.send_typing(update, context).result()
        utils.execute_query(
            _CONN,
            "INSERT INTO spend_log (username, category, amount, notes, tx_timestamp) "
            "VALUES (%(username)s, %(category)s, %(amount)s, %(notes)s, %(tx_timestamp)s)",
            query_data=data_upload,
            commit=True,
        ).result()

        context.user_data.clear()

        return ConversationHandler.END

    else:
        update.message.reply_text(
            "Well of course there's something wrong... Let's try again shall we?\nYou may /cancel otherwise."
        )
        return get_category_log(update, context)


def reply_month_spend(update, context):
    """Reply with spend for the past month"""
    utils.send_typing(update, context).result()
    data = fetch_spend_data()
    spend_str = "\n".join(
        [
            "    - {}{} : {:,.2f} ({:.1%})".format(
                cat, "*" if amt > budget else " ", amt, amt / budget
            )
            for cat, amt, budget in data
        ]
    )
    total_spend = sum(row[1] for row in data)
    update.message.reply_text(
        (
            "Here is the running spend summary this month for both the sir and the madam\n\n"
            "Total: {:,.2f}\n{}"
        ).format(total_spend, spend_str)
    )

    # spend projections
    now = datetime.now()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    scaler = {
        cat: 1 if cat in const.ONETIME_CATEGORIES else (days_in_month / now.day)
        for cat in const.EXPENSE_CATEGORIES
    }
    projspend_str = "\n".join(
        [
            "    - {}{} : {:,.2f} ({:.1%})".format(
                cat,
                "*" if (amt * scaler[cat]) > budget else " ",
                (amt * scaler[cat]),
                (amt * scaler[cat]) / budget,
            )
            for cat, amt, budget in data
        ]
    )
    total_spend_p = sum(amt * scaler[cat] for cat, amt, budget in data)
    update.message.reply_text(
        "And here is your PROJECTED spend for the month\n\nTotal: {:,.2f}\n{}".format(
            total_spend_p, projspend_str
        )
    )

    return ConversationHandler.END


@utils.validator(
    valid_values={"ALL"} | set(const.EXPENSE_CATEGORIES),
    prev_handler=get_category_showtx,
)
def reply_txns(update, context):
    """Reply last few transactions"""
    if update.message.text.upper() == "ALL":
        cat = None
        row_base_str = "[{:%b-%d %H:%M}] SGD {:.1f}; {} - {}"
    else:
        cat = update.message.text
        row_base_str = "[{:%b-%d %H:%M}] SGD {:.1f}; {}"

    data = fetch_txns(cat)
    txn_str = "\n".join([row_base_str.format(*row) for row in data])
    update.message.reply_text(
        ("Recent transactions for {}\n\n{}").format(update.message.text, txn_str)
    )
    return ConversationHandler.END


def fetch_spend_data():
    """Fetch Spend data for the current month"""
    query = """
    SELECT month_spd.category, month_spd.TotalSpend, COALESCE(monthly_budgets.max_budget, 1e9)
    FROM (
        SELECT category, SUM(amount) as TotalSpend
        FROM spend_log
        WHERE tx_timestamp >= date_trunc('month', localtimestamp)
        GROUP BY category
        ORDER BY SUM(amount) DESC
    ) as month_spd
    LEFT JOIN monthly_budgets ON month_spd.category = monthly_budgets.category;
    """

    return utils.execute_query(_CONN, query, fetch=True).result()


def fetch_txns(cat=None, n_txn=8):
    """Fetch transactions data"""
    # TODO: refactor to accommodate sorting by amount, in addition to recency?
    query = """
    SELECT tx_timestamp, amount, {cat}notes
    FROM spend_log
    {where}
    ORDER BY tx_timestamp DESC
    LIMIT {n_txn};
    """.format(
        cat=("" if cat else "category, "),
        where=("WHERE category LIKE '{}'".format(cat) if cat else ""),
        n_txn=n_txn,
    )

    return utils.execute_query(_CONN, query, fetch=True).result()


STATES = {
    const.EXPENSE_CATEGORY_LOG: get_category_log,
    const.EXPENSE_CATEGORY_SHOWTX: get_category_showtx,
    const.EXPENSE_AMOUNT: get_amount,
    const.EXPENSE_NOTES: get_notes,
    const.REVIEW_EXPENSE_UPLOAD: review_expense_upload,
}

TERM_STATES = {const.UPLOAD_EXPENSE: upload_expense, const.GET_TXNS: reply_txns}
