"""Core Functions for ButlerG"""
import functools
import logging
import time

from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

import credentials as creds
import constants as const
import utils

import log_expense

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def start(update, context):
    """Flavor entry point. Summons task menu"""
    user = update.message.from_user
    logger.info("[%s] Start", user.first_name)
    update.message.reply_text(
        text="Hello Master {}, what now?\n\n*shrug*".format(user.first_name)
    )
    return task_menu(update, context)


def task_menu(update, context):
    """Services menu"""
    user = update.message.from_user
    logger.info("[%s] Menu", user.first_name)
    reply_markup = ReplyKeyboardMarkup(
        utils.gen_keyboard(const.TASKS) + [[const.EXIT_STR]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    update.message.reply_text(
        text='My Services:\nNote: You can type "/cancel" to stop at any time.',
        reply_markup=reply_markup,
    )
    return const.TASK


def confused(update, context):
    """Conversation fallback"""
    user = update.message.from_user
    logger.info("[%s] Confused", user.first_name)
    update.message.reply_text(
        "I didn't quite catch your mumbling. Here's what I can do for you."
    )
    return task_menu(update, context)


def cancel(update, context):
    """Cancel Handler"""
    user = update.message.from_user
    logger.info("[%s] Cancel.", user.first_name)

    update.message.reply_text(
        "Glad to be of service, Master {}.".format(user.first_name),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates.

    Notes
    =====

    In the `constants` module:
    * `DEV_CHATID` can be specified to send a message when an error is caught.
    * `DEV_NAME` and `ERROR_WEBP` can be specified for some added flavor
    """
    try:
        user = update.message.from_user
        logger.warning(
            '[%s] Update "%s" caused error "%s"', user.first_name, update, context.error
        )

        if hasattr(creds, "DEV_CHATID"):
            context.bot.send_message(
                creds.DEV_CHATID,
                "Error caught from update:\n{}\n\n{}".format(update, context.error),
            )

        update.message.reply_text(
            "Terribly sorry... I seem to be having problems...\n\nBlame {}...".format(
                getattr(creds, "DEV_NAME", "the developer")
            ),
            reply_markup=ReplyKeyboardRemove(),
        )

        if hasattr(creds, "ERROR_WEBP"):
            update.message.reply_sticker(creds.ERROR_WEBP)

        update.message.reply_text(
            "Anything else I can do you for?", reply_markup=ReplyKeyboardRemove()
        )

        return task_menu(update, context)

    except Exception as err:

        logger.error(repr(err))
        return ConversationHandler.END


# Utils
def land_to_task_menu(func):
    """Open `task_menu` instead of ending conversation. Otherwise, return func result."""

    @functools.wraps(func)
    def wrapper(update, context):
        res = func(update, context)
        if res == ConversationHandler.END:
            update.message.reply_text("Anything else I can do for you?")
            return task_menu(update, context)
        else:
            return res

    return wrapper


def start_bot():
    """Main Routine"""
    logger.info("Initializing updater and dispatcher")
    updater = Updater(token=creds.TELEGRAM_API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    logger.info("Initializing conversation handler")
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", task_menu),
            CommandHandler("log_expense", log_expense.get_category),
            MessageHandler(Filters.all, start),
        ],
        states={
            const.TASK: [
                MessageHandler(
                    Filters.regex("^{}$".format(const.LOG_EXPENSE)),
                    log_expense.get_category,
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.SPEND_MONTH)),
                    land_to_task_menu(log_expense.reply_month_spend),
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.LAST_TXNS)),
                    functools.partial(
                        log_expense.get_category, mode="show_tx"
                    ),
                ),
                MessageHandler(Filters.regex("^{}$".format(const.EXIT_STR)), cancel),
                MessageHandler(~Filters.command, confused),
            ],
            # expense logging states
            const.EXPENSE_CATEGORY: [
                MessageHandler(Filters.text, log_expense.get_category)
            ],
            const.EXPENSE_AMOUNT: [
                MessageHandler(Filters.text, log_expense.get_amount)
            ],
            const.EXPENSE_NOTES: [MessageHandler(Filters.text, log_expense.get_notes)],
            const.REVIEW_EXPENSE_UPLOAD: [
                MessageHandler(Filters.text, log_expense.review_expense_upload)
            ],
            const.UPLOAD_EXPENSE: [
                MessageHandler(
                    Filters.text, land_to_task_menu(log_expense.upload_expense)
                )
            ],
            const.GET_TXNS: [
                MessageHandler(Filters.text, land_to_task_menu(log_expense.reply_txns))
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(~Filters.command, confused),
        ],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error)

    # need to handle network errors here
    while True:
        try:
            logger.info("Polling...")
            updater.start_polling()
            updater.idle()
            break

        except Exception as err:
            logger.error(repr(err))
            updater.stop()
            time.sleep(5)
            updater.start_polling()
            updater.idle()


if __name__ == "__main__":
    start_bot()
