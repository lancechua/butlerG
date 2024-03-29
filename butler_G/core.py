"""Core Functions for ButlerG"""
import functools
import json
import logging
import multiprocessing as mp
import os
import time

from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from . import credentials as creds
from . import constants as const
from . import db
from . import utils

# modules with DB interactions
from . import account_management as am
from . import log_expense
from . import log_gift

logger = logging.getLogger(__name__)

with open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), const.STATES_JSON), "r"
) as f:
    STATES = json.load(f)

_DB_CLIENTS = [log_expense.DB_CLIENT, log_gift.DB_CLIENT, am.DB_CLIENT]


def _setup():
    """Setup Database"""
    log_expense._setup()
    log_gift._setup()
    am._setup()


@am.check_sender()
def start(update, context):
    """Flavor entry point. Summons task menu"""
    user = update.message.from_user
    logger.info("[%s] Start", user.first_name)
    if STATES.get("vacation", False):
        reply_text = "Hello Master {}! Hope you're having fun!".format(user.first_name)
    else:
        reply_text = "Hello Master {}, what now?\n\n*shrug*".format(user.first_name)

    update.message.reply_text(text=reply_text)

    return task_menu(update, context)


@am.check_sender()
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


@am.check_sender()
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
    -----

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


def start_db_svc():
    """Function to start db service"""
    server = db.Server(const.DBSVC_URL)
    server.main(**creds.DB_CREDS)


def start_bot():
    """Main Routine"""
    logger.info("Initializing updater and dispatcher")
    updater = Updater(
        token=creds.TELEGRAM_API_TOKEN,
        use_context=True,
        request_kwargs={"read_timeout": 60, "connect_timeout": 60},
    )
    dispatcher = updater.dispatcher

    logger.info("Initializing conversation handler")
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", task_menu),
            MessageHandler(Filters.all, start),
        ],
        states={
            const.TASK: [
                MessageHandler(
                    Filters.regex("^{}$".format(const.LOG_EXPENSE)),
                    log_expense.get_category_log,
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.SPEND_MONTH)),
                    land_to_task_menu(log_expense.reply_month_spend),
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.LAST_TXNS)),
                    log_expense.get_category_showtx,
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.LOG_GIFT)), log_gift.get_recipient
                ),
                MessageHandler(
                    Filters.regex("^{}$".format(const.GIFT_SPEND)),
                    land_to_task_menu(log_gift.reply_month_gift_spend),
                ),
                MessageHandler(Filters.regex("^{}$".format(const.EXIT_STR)), cancel),
                MessageHandler(~Filters.command, confused),
            ],
            # expense logging states
            **{
                state: [MessageHandler(Filters.text & (~Filters.command), handler_fx)]
                for state, handler_fx in log_expense.STATES.items()
            },
            **{
                state: [
                    MessageHandler(
                        Filters.text & (~Filters.command), land_to_task_menu(handler_fx)
                    )
                ]
                for state, handler_fx in log_expense.TERM_STATES.items()
            },
            # gift logging states
            **{
                state: [MessageHandler(Filters.text & (~Filters.command), handler_fx)]
                for state, handler_fx in log_gift.STATES.items()
            },
            **{
                state: [
                    MessageHandler(
                        Filters.text & (~Filters.command), land_to_task_menu(handler_fx)
                    )
                ]
                for state, handler_fx in log_gift.TERM_STATES.items()
            },
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(~Filters.command, confused),
        ],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error)

    logger.info("Starting db service")
    db_proc = mp.Process(target=start_db_svc)
    db_proc.start()

    # need to handle network errors here
    while True:
        try:
            logger.info("Polling...")
            updater.start_polling()
            updater.idle()
            break

        except (KeyboardInterrupt, SystemExit):
            logging.info("Stopping")
            break

        except Exception as err:
            logger.error(repr(err))
            updater.stop()
            time.sleep(5)
            updater.start_polling()
            updater.idle()

    # cleanup
    updater.stop()
    db_proc.terminate()
    for dbc in _DB_CLIENTS:
        dbc.close()

    logging.info("Exited.")
