"""
Log Expense Module

Contains various functions and handlers for the "Log Expense" task
"""
from datetime import datetime
import logging
import random

import psycopg2
from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler

import credentials as creds
import constants as const
import utils


_CONN = psycopg2.connect(**creds.DB_CREDS)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def get_category(update, context):
    """Handler that asks for Expense Category"""
    logger.info("Expense Category")
    reply_markup = ReplyKeyboardMarkup(
        utils.gen_keyboard(const.EXPENSE_CATEGORIES, columns=2),
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    update.message.reply_text("What did you spend on now?", reply_markup=reply_markup)
    return const.EXPENSE_AMOUNT


def get_amount(update, context):
    """Handler that asks for Expense Amount"""
    logger.info("Expense Amount")
    utils.send_typing(update, context).result()

    cat = update.message.text
    cat_spd = (
        utils.execute_query(
            _CONN,
            "SELECT SUM(amount) FROM spend_log "
            "WHERE category=%(category)s "
            "AND EXTRACT(DAY FROM localtimestamp - tx_timestamp) <= %(n_days)s",
            query_data={"category": cat, "n_days": const.N_DAYS},
            fetch=True,
        ).result()[0][0]
        or 0
    )
    cat_budget = const.EXPENSE_BUDGETS.get(cat, {}).get("max_budget", 1e9)

    context.user_data["category"] = cat
    context.user_data["_category_spend"] = cat_spd
    context.user_data["_category_budget"] = cat_budget

    if const.WARN_THRESH <= cat_spd / cat_budget <= 1:
        update.message.reply_text(
            (
                "Master, might I warn you that we are at {:.1%} of our {} budget. "
                "({:,.2f} of {:,.2f})"
            ).format(cat_spd / cat_budget, cat, cat_spd, cat_budget)
        )

    update.message.reply_text("How much did you spend?")
    return const.EXPENSE_NOTES


def get_notes(update, context):
    """Handler that asks for Expense Notes"""
    logger.info("Expense Notes")
    context.user_data["amount"] = update.message.text

    amt = float(context.user_data["amount"])

    if amt > const.EXPENSE_BUDGETS.get(context.user_data["category"], {}).get(
        "tx_amount", 1e9
    ):
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
            "Well of course there's something wrong... Let's try again shall we?"
        )
        return get_category(update, context)


def reply_30d_spend(update, context):
    """Reply with spend for the past 30 days"""
    utils.send_typing(update, context).result()
    data = fetch_spend_data(const.N_DAYS)
    spend_str = "\n".join(
        [
            "    - {}{} : {:,.2f}".format(
                cat,
                "*"
                if amt > const.EXPENSE_BUDGETS.get(cat, {}).get("max_budget", 1e9)
                else " ",
                amt,
            )
            for cat, amt in data
        ]
    )
    total_spend = sum(amt for _, amt in data)
    update.message.reply_text(
        (
            "Here is the running 30 day spend summary for both the sir and the madam\n\n"
            "Total: {:,.2f}\n{}"
        ).format(total_spend, spend_str)
    )
    return ConversationHandler.END


def fetch_spend_data(n_days: int):
    """Fetch Spend data for past `n_days` days"""
    query = """
        SELECT category, SUM(amount) as TotalSpend
        FROM spend_log
        WHERE EXTRACT(DAY FROM localtimestamp - tx_timestamp) <= {n_days}
        GROUP BY category
        ORDER BY SUM(amount) DESC;
    """.format(
        n_days=n_days
    )

    return utils.execute_query(_CONN, query, fetch=True).result()
