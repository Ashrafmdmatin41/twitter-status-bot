#!/usr/bin/env python3
"""Methods for error handlers."""
import html
import logging
import time
import traceback
from typing import cast

from telegram import Update
from telegram.error import BadRequest, Forbidden, RetryAfter

from bot.constants import ADMIN_KEY
from bot.twitter import HyphenationError
from bot.userdata import CCT

logger = logging.getLogger(__name__)


async def hyphenation_error(update: object, context: CCT) -> None:
    """Handles hyphenation errors by informing the triggering user about them.

    Args:
        update: The Telegram update.
        context: The callback context as provided by the application.
    """
    if not isinstance(context.error, HyphenationError) or not isinstance(update, Update):
        return

    if update.inline_query:
        await update.inline_query.answer(
            results=[],
            switch_pm_text="Click me! 👆",
            switch_pm_parameter="hyphenation_error",
        )
        return
    if update.effective_message:
        await update.effective_message.reply_text(str(context.error))


async def error(update: object, context: CCT) -> None:
    """Informs the originator of the update that an error occurred and forwards the traceback to
    the admin.

    Args:
        update: The Telegram update.
        context: The callback context as provided by the application.
    """
    admin_id = cast(int, context.bot_data[ADMIN_KEY])

    if not isinstance(context.error, Exception):
        return

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if isinstance(context.error, HyphenationError):
        return

    if (
        isinstance(context.error, BadRequest) and "Query is too old" in str(context.error)
    ) or isinstance(context.error, Forbidden):
        return

    if isinstance(context.error, RetryAfter):
        time.sleep(int(context.error.retry_after) + 2)
        return

    # Inform sender of update, that something went wrong
    if isinstance(update, Update) and update.effective_message:
        text = "Something went wrong 😟. I informed the admin 🤓."
        await update.effective_message.reply_text(text)

    # Get traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    trace = "".join(tb_list)

    # Gather information from the update
    payload = ""
    if isinstance(update, Update):
        if update.effective_user:
            payload += f" with the user {update.effective_user.mention_html()}"
        if update.effective_chat and update.effective_chat.username:
            payload += f" (@{html.escape(update.effective_chat.username)})"
        if update.poll:
            payload += f" with the poll id {update.poll.id}."
    text = (
        f"Hey.\nThe error <code>{html.escape(str(context.error))}</code> happened"
        f"{payload}. The full traceback:\n\n<code>{html.escape(trace)}</code>"
    )

    # Send to admin
    await context.bot.send_message(admin_id, text)
