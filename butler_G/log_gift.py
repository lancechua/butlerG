"""
Log Gift Module

Contains various functions and handlers for the "Log Gift" task
"""
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
    """Set up `gift_log` table in database"""
    cursor = _CONN.cursor()
    cursor.execute(
        """
        CREATE TABLE gift_log(
            username text NOT NULL,
            recipient text NOT NULL,
            item text NOT NULL,
            amount real NOT NULL,
            notes text,
            tx_timestamp TIMESTAMP NOT NULL
        );
        """
    )
    _CONN.commit()


def get_recipient(update, context):
    """Handler that asks for Gift Recipient"""
    logger.info("Gift Recipient")

    update.message.reply_text(random.choice(const.LINES_ENTHUSIASM))
    update.message.reply_text("Might I ask to whom this gift is for?")

    return const.GIFT_ITEM


def get_item(update, context):
    """Handler that asks for Gift Item"""
    logger.info("Gift Item")

    context.user_data["recipient"] = update.message.text
    update.message.reply_text("Aw... and what did you get?")

    return const.GIFT_AMOUNT


def get_amount(update, context):
    """Handler that asks for Gift Item"""
    logger.info("Gift Amount")

    context.user_data["item"] = update.message.text
    update.message.reply_text("And for how much?")

    return const.GIFT_NOTE


def get_note(update, context):
    """Handler that asks for Gift Note"""
    logger.info("Gift Note")

    context.user_data["amount"] = update.message.text
    update.message.reply_text(
        'Do you wish to add any comments?\n(Enter "no comment" otherwise)'
    )

    return const.GIFT_REVIEW


def review_gift_upload(update, context):
    """Handler to review Gift data before upload"""
    logger.info("Review Gift Upload")
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

    return const.GIFT_UPLOAD


def upload_gift(update, context):
    """Handler that submits gift data for upload"""
    logger.info("Upload Gift")
    if update.message.text == const.YES:
        user = update.message.from_user
        data_upload = context.user_data.copy()
        data_upload["tx_timestamp"] = datetime.now()
        data_upload["username"] = user.username or user.id

        # upload data
        utils.send_typing(update, context).result()
        utils.execute_query(
            _CONN,
            "INSERT INTO gift_log (username, recipient, item, amount, notes, tx_timestamp) "
            "VALUES (%(username)s, %(recipient)s, %(item)s, %(amount)s, %(notes)s, %(tx_timestamp)s)",
            query_data=data_upload,
            commit=True,
        ).result()

        context.user_data.clear()
        update.message.reply_text(
            "Alright. I shall add them to my records. Have a pleasant day."
        )

        return ConversationHandler.END

    else:
        update.message.reply_text("Let's try again shall we?")
        return get_recipient(update, context)


def reply_month_gift_spend(update, context):
    """Reply with gift spend for the past month"""
    utils.send_typing(update, context).result()
    data = fetch_gift_spend_data()
    update.message.reply_text(
        "Total spent on gifts this month:\n\tSGD {:,.2f}".format(data[0][0] or 0)
    )

    return ConversationHandler.END


def fetch_gift_spend_data():
    """Fetch Spend data for the current month"""
    query = """
    SELECT SUM(amount) as TotalSpend
    FROM gift_log
    WHERE tx_timestamp >= date_trunc('month', localtimestamp)
    """

    return utils.execute_query(_CONN, query, fetch=True).result()


STATES = {
    const.GIFT_RECIPIENT: get_recipient,
    const.GIFT_ITEM: get_item,
    const.GIFT_AMOUNT: get_amount,
    const.GIFT_NOTE: get_note,
    const.GIFT_REVIEW: review_gift_upload,
}

TERM_STATES = {const.GIFT_UPLOAD: upload_gift}
