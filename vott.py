#!/usr/bin/env python3
import logging
import random
import string
import json
import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest

# ================= CONFIG ================= #
TOKEN = "8790948835:AAGCJToYVs_w-QemtOFs283skbdqGk3-TKk"
BOT_USERNAME = "votesarena_bot"
OWNER_ID = 7638053663

# ================= AUTO BACKUP CONFIG ================= #
BACKUP_CHANNEL_ID = -1004492262212   # jaha auto DB jayega (bot yaha admin hona chahiye)
AUTO_BACKUP_MINUTES = 30             # har kitne minute me DB bheje
KEEP_LAST_BACKUPS = 1                # channel me kitne latest backup rakhne hai, baaki delete
BACKUP_IDS_FILE = "backup_msgs.json" # purane backup message id yaha store hote hai

# Log channel — same as backup channel, alag chahiye to change karo
LOG_CHANNEL_ID = BACKUP_CHANNEL_ID

# Warning system config
MAX_WARNINGS = 3

# ================= PREMIUM EMOJIS ================= #
EMOJI_VOTE = "5267095979097610740"
EMOJI_JOIN = "6237668294896131350"
EMOJI_CANCEL = "6240245571626475799"
EMOJI_MAIN_MENU = "6240245571626475799"
EMOJI_BACK = "6217402478825049695"
EMOJI_CREATE = "5208891329626521299"
EMOJI_CONNECT = "5244710862953941180"
EMOJI_MANAGE = "6237621548472081271"
EMOJI_ADD_VOTES = "6240003971126139705"
EMOJI_REMOVE_VOTES = "6240003971126139705"
EMOJI_LEADERBOARD = "6240027791014765668"
EMOJI_END_GIVEAWAY = "6240085923397114865"
EMOJI_ADMIN = "6237595159329113605"
EMOJI_BROADCAST = "6237668294896131350"
EMOJI_STATS = "6239790794719370356"
EMOJI_SETTINGS = "6237621548472081271"
EMOJI_USERS = "6237867138997034625"
EMOJI_BACKUP = "6237900592497302202"
EMOJI_CLEAR = "6240152061598504832"
EMOJI_CHANNEL = "6237510794150419802"
EMOJI_NOTIFICATION = "6240073270423462835"
EMOJI_CONFIRM = "6239815031219820750"
EMOJI_REFRESH = "6240085923397114865"
EMOJI_WELCOME = "6332080283176672910"
EMOJI_FIRE = "6334449730734529256"
EMOJI_ARROW = "6332591195306334733"
EMOJI_CHART = "6332186798365612896"
EMOJI_HEART = "6237558987978447573"
EMOJI_ROCKET = "5188481279963715781"
EMOJI_CROWN = "6332246180583447893"
EMOJI_ERROR = "6334723470475139278"
EMOJI_ENDED = "6237572882197650867"
EMOJI_STAR = "6239815031219820750"
EMOJI_ID = "6237547619200014867"
EMOJI_GIFT = "6239894475229895983"
EMOJI_WINE = "6237510794150419802"
EMOJI_SMILE = "6237867138997034625"
EMOJI_LOVE = "6334437167955188087"
EMOJI_LIGHTNING = "6240073270423462835"
EMOJI_POINTER = "6237732706520668707"
EMOJI_ALERT = "6240152061598504832"
EMOJI_CLOWN = "6237900592497302202"
EMOJI_SEARCH = "6239790794719370356"
EMOJI_SPEAKER = "5217968773071401144"
EMOJI_LINK = "5289511602393984968"
EMOJI_CONFETTI = "6240085923397114865"
EMOJI_LOCATION = "6240101054566897479"
EMOJI_RIGHT = "6240295371772271503"
EMOJI_DIAMOND = "6240003971126139705"
EMOJI_CALENDAR = "6240027791014765668"
EMOJI_WINNER = "6332435498446888848"
EMOJI_MONEY_BAG = "6332246180583447893"
EMOJI_CELEBRATE = "6237621707385871360"
EMOJI_INBOX = "6237973405077871246"
EMOJI_LOCK = "6332490478323243268"
EMOJI_SHIELD = "6237595159329113605"

# ================= COLOR STYLES ================= #
BUTTON_STYLE_PRIMARY = "primary"
BUTTON_STYLE_SUCCESS = "success"
BUTTON_STYLE_DANGER = "danger"

# ================= LOGGING ================= #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= JSON DATABASE ================= #
DATA_FILE = "bot_data.json"

def _normalize_giveaway_data(raw_giveaways):
    """Normalize JSON-loaded giveaway keys/sets for reliable voting after restart."""
    normalized = {}
    for gid, g in (raw_giveaways or {}).items():
        g = dict(g or {})
        users = {int(k): v for k, v in (g.get("users", {}) or {}).items()}
        vote_counts = {int(k): int(v) for k, v in (g.get("vote_counts", {}) or {}).items()}
        voted_users = {}
        for uid, voters in (g.get("voted_users", {}) or {}).items():
            try:
                target_id = int(uid)
            except Exception:
                target_id = uid
            voted_users[target_id] = set(int(v) for v in (voters or []))
        voter_votes = {}
        for voter, target in (g.get("voter_votes", {}) or {}).items():
            try:
                voter_votes[int(voter)] = int(target)
            except Exception:
                pass
        g["users"] = users
        g["vote_counts"] = vote_counts
        g["voted_users"] = voted_users
        g["voter_votes"] = voter_votes
        g.setdefault("force_sub_channels", [])
        normalized[gid] = g
    return normalized


def _json_safe(value):
    """Convert sets/tuple/nested values to JSON-safe values."""
    if isinstance(value, set):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def load_data():
    global giveaways, all_users, channel_history, vote_messages, backup_msg_ids
    global banned_users, BANNED_WORDS, warnings_db

    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            giveaways = _normalize_giveaway_data(data.get("giveaways", {}))
            all_users = data.get("all_users", data.get("users", {}))
            channel_history = data.get("channel_history", {})
            backup_msg_ids = [int(i) for i in data.get("backup_msg_ids", [])]
            banned_users = data.get("banned_users", {})
            warnings_db = data.get("warnings_db", {})
            BANNED_WORDS.clear()
            BANNED_WORDS.extend(data.get("banned_words", []))

            vote_messages = {}
            vm_raw = data.get("vote_messages", {})
            for gid, users in vm_raw.items():
                vote_messages[gid] = {}
                for uid, mid in users.items():
                    try:
                        vote_messages[gid][int(uid)] = mid
                    except Exception:
                        vote_messages[gid][uid] = mid

            logger.info(f"Loaded: {len(giveaways)} giveaways, {len(all_users)} users, {len(banned_users)} banned")
        else:
            giveaways = {}
            all_users = {}
            channel_history = {}
            vote_messages = {}
    except Exception as e:
        logger.error(f"Error loading: {e}")
        try:
            os.replace(DATA_FILE, DATA_FILE + ".corrupt")
            logger.warning(f"Corrupt DB ko {DATA_FILE}.corrupt me save kar diya")
        except Exception:
            pass
        giveaways = {}
        all_users = {}
        channel_history = {}
        vote_messages = {}

def save_data(force=False):
    try:
        if not force and not giveaways and not all_users and os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    old = json.load(f)
                if old.get("giveaways") or old.get("all_users") or old.get("users"):
                    logger.warning("Empty data save BLOCKED - purani DB safe rakhi gayi")
                    return
            except Exception:
                pass

        vm_serializable = {
            gid: {str(uid): mid for uid, mid in users.items()}
            for gid, users in vote_messages.items()
        }
        data = {
            "giveaways": _json_safe(giveaways),
            "all_users": _json_safe(all_users),
            "channel_history": _json_safe(channel_history),
            "vote_messages": vm_serializable,
            "backup_msg_ids": backup_msg_ids,
            "banned_users": _json_safe(banned_users),
            "banned_words": BANNED_WORDS,
            "warnings_db": _json_safe(warnings_db),
            "last_saved": datetime.now().isoformat()
        }
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, DATA_FILE)
    except Exception as e:
        logger.error(f"Error saving: {e}")

def save_user(user_id, username, first_name, last_name=None, source=None):
    if str(user_id) not in all_users:
        all_users[str(user_id)] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "joined_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "source": source or "unknown",
            "total_votes_given": 0,
            "total_giveaways_joined": 0
        }
        save_data()
    else:
        all_users[str(user_id)]["last_active"] = datetime.now().isoformat()
        if username:
            all_users[str(user_id)]["username"] = username
        save_data()
    return True

def update_user_stats(user_id, action):
    user_id_str = str(user_id)
    if user_id_str in all_users:
        if action == "vote":
            all_users[user_id_str]["total_votes_given"] = all_users[user_id_str].get("total_votes_given", 0) + 1
        elif action == "join":
            all_users[user_id_str]["total_giveaways_joined"] = all_users[user_id_str].get("total_giveaways_joined", 0) + 1
        save_data()

def update_channel_history(channel_identifier, channel_display, channel_id, user_id, user_name, action, giveaway_id=None):
    channel_key = str(channel_identifier)
    if channel_key not in channel_history:
        channel_history[channel_key] = {
            "channel_identifier": channel_identifier,
            "channel_display": channel_display,
            "channel_id": channel_id,
            "type": "private" if str(channel_id).startswith('-100') or str(channel_id).startswith('-') else "public",
            "total_giveaways": 0,
            "giveaways": [],
            "created_by": user_id,
            "created_by_name": user_name,
            "first_created": datetime.now().isoformat()
        }
    if action == "create":
        channel_history[channel_key]["total_giveaways"] += 1
        channel_history[channel_key]["giveaways"].append({
            "giveaway_id": giveaway_id,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "participants": 0
        })
        channel_history[channel_key]["last_giveaway"] = datetime.now().isoformat()
    elif action == "end" and giveaway_id:
        for g in channel_history[channel_key]["giveaways"]:
            if g.get("giveaway_id") == giveaway_id:
                g["status"] = "ended"
                g["ended_at"] = datetime.now().isoformat()
                break
    save_data()

# ================= INITIALIZE ================= #
giveaways = {}
all_users = {}
user_sessions = {}
admin_sessions = {}
channel_history = {}
vote_messages = {}
backup_msg_ids = []
banned_users = {}
warnings_db = {}
BANNED_WORDS = []

load_data()

request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)

def premium_button(text, callback_data=None, url=None, emoji_id=None, style=None):
    if url:
        return InlineKeyboardButton(text=text, url=url, icon_custom_emoji_id=emoji_id, style=style)
    return InlineKeyboardButton(text=text, callback_data=callback_data, icon_custom_emoji_id=emoji_id, style=style)

def is_owner(user_id):
    return user_id == OWNER_ID

async def send_notification_to_owner(context, title, message):
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"<b>{title}</b>\n\n{message}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send: {e}")

# ================= VOTE MESSAGES REBUILD ================= #
async def rebuild_vote_messages(app):
    # PTB me get_chat_history nahi hai — vote_messages DB se already load hote hain
    # Restart ke baad bhi DB se restore hoga, isliye yeh skip karna safe hai
    logger.info("vote_messages loaded from DB (no channel scan needed in PTB).")
    save_data()

async def update_vote_button_in_channel(context, giveaway_id, user_id, new_votes):
    try:
        giveaway = giveaways.get(giveaway_id)
        if not giveaway:
            return False
        if giveaway_id in vote_messages and user_id in vote_messages[giveaway_id]:
            message_id = vote_messages[giveaway_id][user_id]
            try:
                new_keyboard = [[
                    premium_button(f"Vote - {new_votes}", callback_data=f"vote_{giveaway_id}_{user_id}", emoji_id=EMOJI_VOTE, style=BUTTON_STYLE_SUCCESS)
                ]]
                await context.bot.edit_message_reply_markup(
                    chat_id=giveaway['channel_id'],
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup(new_keyboard)
                )
                return True
            except Exception as e:
                logger.error(f"Failed to edit: {e}")
                return False
        return False
    except Exception as e:
        logger.error(f"Error updating: {e}")
        return False

# ================= START COMMAND ================= #
def get_banned_msg():
    line = "━" * 22
    return (
        f"🚫 <b>ACCESS DENIED</b>\n"
        f"<code>{line}</code>\n\n"
        f"🛡️ <b>You have been permanently banned using banned words</b>\n"
        f"<b>by the owner</b> <a href='https://t.me/sahilxalone'>@sahilxalone</a>\n\n"
        f"⚡ <i>If you think this is a mistake,</i>\n"
        f"<i>contact</i> <a href='https://t.me/sahilxalone'>@sahilxalone</a>\n\n"
        f"<code>{line}</code>"
    )

BANNED_MSG = get_banned_msg()

async def _send_banned_response(update: Update):
    """Banned message bhejo — message ya callback_query dono handle karo."""
    try:
        if update.message:
            await update.message.reply_text(
                get_banned_msg(), parse_mode="HTML", disable_web_page_preview=True)
        elif update.callback_query:
            # Callback me full message send nahi kar sakte, sirf alert
            await update.callback_query.answer(
                "🚫 You are permanently banned. Contact @sahilxalone", show_alert=True)
    except Exception:
        pass


async def is_banned_user(update: Update, context=None) -> bool:
    """
    PERMANENT BAN CHECK — 3 layers:
    1. DB me banned_users me hai?
    2. Naam/username me banned word hai? (auto-ban)
    3. Owner? — skip

    Agar banned → response bhejo aur True return karo.
    Caller sirf 'return' karta hai — koi aur action nahi.
    """
    if not update.effective_user:
        return False

    user = update.effective_user
    if user.id == OWNER_ID:
        return False

    uid_str = str(user.id)

    # Layer 1: Already permanently banned
    if uid_str in banned_users:
        await _send_banned_response(update)
        logger.info(f"Banned user {user.id} tried to interact — blocked.")
        return True

    # Layer 2: Name/username contains banned word — auto-ban NOW
    matched_name = user_has_banned_word(user)
    if matched_name and context:
        # Kisi bhi known channel me ban karo
        for ch_data in channel_history.values():
            ch_id = ch_data.get("channel_id")
            if ch_id:
                try:
                    await context.bot.ban_chat_member(
                        chat_id=ch_id, user_id=user.id, revoke_messages=True)
                except Exception:
                    pass
        # DB me store
        banned_users[uid_str] = {
            "user_id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "banned_at": datetime.now().isoformat(),
            "reason": f"Name/username contains banned word: '{matched_name}'",
            "chat_id": None,
            "type": "auto_name"
        }
        if uid_str in all_users:
            all_users[uid_str]["is_banned"] = True
            all_users[uid_str]["ban_reason"] = f"Banned name: '{matched_name}'"
        save_data()
        # Log
        try:
            uname = f"@{user.username}" if user.username else "N/A"
            full = f"{user.first_name or ''} {user.last_name or ''}".strip()
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=(
                    f"<b>🚨 AUTO BAN — NAME DETECTION</b>\n\n"
                    f"<b>👤 Name:</b> {full}\n"
                    f"<b>🆔 ID:</b> <code>{user.id}</code>\n"
                    f"<b>📛 Username:</b> {uname}\n"
                    f"<b>🔤 Word:</b> <code>{matched_name}</code>\n"
                    f"<b>🕒 Time:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n\n"
                    f"<b>Unban:</b> <code>/unban {user.id}</code>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await _send_banned_response(update)
        return True

    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await is_banned_user(update, context):
        return
    save_user(user.id, user.username, user.first_name, user.last_name, source="/start")
    if context.args and len(context.args) > 0:
        start_param = context.args[0]
        # Vote verification flow: channel Vote button opens the bot privately.
        if start_param.startswith("vote_"):
            parts = start_param.split("_")
            if len(parts) == 3:
                try:
                    await show_vote_verification(update, context, parts[1], int(parts[2]))
                except ValueError:
                    await update.message.reply_text("❌ Invalid vote link.")
                return
        giveaway_id = start_param
        await handle_giveaway_link(update, giveaway_id, context)
        return
    keyboard = []
    if is_owner(user.id):
        keyboard = [
            [premium_button("CONNECT", url=f"https://t.me/{BOT_USERNAME}?startchannel=true&admin=post_messages", emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_SUCCESS)],
            [premium_button("CREATE", callback_data="create_giveaway", emoji_id=EMOJI_CREATE, style=BUTTON_STYLE_PRIMARY),
             premium_button("MANAGE", callback_data="my_giveaways", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY)]
        ]
    welcome_text = (
        f"<b><tg-emoji emoji-id='{EMOJI_WELCOME}'>🙂</tg-emoji> WELCOME TO PRIME VOTE GIVEAWAY BOT</b>\n\n"
        f"<i><tg-emoji emoji-id='{EMOJI_FIRE}'>☄️</tg-emoji> Create Powerful Vote Giveaways</i>\n"
        f"<i><tg-emoji emoji-id='{EMOJI_ARROW}'>🔜</tg-emoji> Real Time Vote System</i>\n"
        f"<i><tg-emoji emoji-id='{EMOJI_CHART}'>📈</tg-emoji> Advanced Management Tools</i>\n"
        f"<i><tg-emoji emoji-id='{EMOJI_HEART}'>❤️‍🔥</tg-emoji> Leaderboard & Analytics</i>\n\n"
        f"<b><tg-emoji emoji-id='{EMOJI_ROCKET}'>🚀</tg-emoji> START CREATING NOW!</b>"
    )
    await update.message.reply_text(text=welcome_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_giveaway_link(update: Update, giveaway_id: str, context=None):
    user = update.effective_user

    # ── LAYER 1: Already banned user ──
    uid_str = str(user.id)
    if uid_str in banned_users and user.id != OWNER_ID:
        await update.message.reply_text(
            get_banned_msg(), parse_mode="HTML", disable_web_page_preview=True)
        return

    # ── LAYER 2: Name/username contains banned word ──
    matched_name = user_has_banned_word(user)
    if matched_name:
        giveaway_ch = giveaways.get(giveaway_id, {}).get("channel_id")
        # No context here so use bot from update
        if giveaway_ch and context:
            await auto_ban_user(
                bot=context.bot,
                chat_id=giveaway_ch,
                user=user,
                message_id=None,
                matched_word=matched_name,
                reason_prefix="Banned name/username"
            )
        await update.message.reply_text(
            get_banned_msg(), parse_mode="HTML", disable_web_page_preview=True)
        return

    if giveaway_id not in giveaways:
        await update.message.reply_text(
            f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> <b>INVALID LINK</b>", parse_mode="HTML")
        return
    giveaway = giveaways[giveaway_id]
    user_id = user.id
    if giveaway.get("ended", False):
        await update.message.reply_text(
            f"<tg-emoji emoji-id='{EMOJI_ENDED}'>❌</tg-emoji> <b>GIVEAWAY ENDED</b>", parse_mode="HTML")
        return
    if user_id in giveaway.get("users", {}):
        await update.message.reply_text(
            f"<tg-emoji emoji-id='{EMOJI_STAR}'>🌟</tg-emoji> <b>ALREADY PARTICIPATED!</b>\n\n"
            f"<tg-emoji emoji-id='{EMOJI_ID}'>💌</tg-emoji> <b>Your ID:</b> <code>{user_id}</code>",
            parse_mode="HTML")
        return
    keyboard = [[premium_button("JOIN GIVEAWAY", callback_data=f"join_{giveaway_id}", emoji_id=EMOJI_JOIN, style=BUTTON_STYLE_SUCCESS)]]
    channel_display = giveaway.get("channel_display", giveaway.get("channel", "Channel"))
    await update.message.reply_text(
        f"<tg-emoji emoji-id='{EMOJI_GIFT}'>🎁</tg-emoji> <b>EXCLUSIVE GIVEAWAY</b>\n\n"
        f"<tg-emoji emoji-id='{EMOJI_WINE}'>🍷</tg-emoji> <b>Hosted By:</b> {channel_display}\n"
        f"<tg-emoji emoji-id='{EMOJI_SMILE}'>😎</tg-emoji> <b>Participants:</b> {len(giveaway['users'])}",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= CREATE GIVEAWAY ================= #
async def create_giveaway_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.answer("🔒 Only the bot owner can create giveaways.", show_alert=True)
        return
    await query.answer()
    user_sessions[user_id] = {"step": "waiting_channel"}
    keyboard = [[premium_button("CANCEL", callback_data="cancel_creation", emoji_id=EMOJI_CANCEL, style=BUTTON_STYLE_DANGER)]]
    await query.edit_message_text(
        text=f"<b><tg-emoji emoji-id='{EMOJI_LIGHTNING}'>⚡</tg-emoji> CREATE GIVEAWAY</b>\n\n"
             f"<i><tg-emoji emoji-id='{EMOJI_POINTER}'>👈</tg-emoji> Send your channel information:</i>\n\n"
             f"<b>Public:</b> <code>@username</code>\n<b>Private:</b> <code>-1001234567890</code>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    keyboard = [
        [premium_button("CONNECT", url=f"https://t.me/{BOT_USERNAME}?startchannel=true&admin=post_messages", emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_SUCCESS)],
        [premium_button("CREATE", callback_data="create_giveaway", emoji_id=EMOJI_CREATE, style=BUTTON_STYLE_PRIMARY),
         premium_button("MANAGE", callback_data="my_giveaways", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY)]
    ]
    await query.edit_message_text(text="✅ <b>Cancelled!</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def process_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        user_sessions.pop(user_id, None)
        await update.message.reply_text("🔒 Only the bot owner can create giveaways.", parse_mode="HTML")
        return
    user_name = update.effective_user.first_name
    if user_id not in user_sessions or user_sessions[user_id].get("step") != "waiting_channel":
        return
    channel_input = update.message.text.strip()
    loading_msg = await update.message.reply_text(
        f"<tg-emoji emoji-id='{EMOJI_LIGHTNING}'>⚡</tg-emoji> <b>Verifying...</b>", parse_mode="HTML")
    try:
        if channel_input.startswith('@'):
            chat = await context.bot.get_chat(chat_id=channel_input)
            channel_info = {"identifier": channel_input, "display_name": channel_input, "chat_id": chat.id, "type": "public"}
        else:
            chat = await context.bot.get_chat(chat_id=int(channel_input))
            channel_info = {"identifier": str(channel_input), "display_name": chat.title or f"Channel {channel_input}", "chat_id": chat.id, "type": "private"}
    except Exception as e:
        await loading_msg.delete()
        error = str(e).lower()
        if "bot is not a member" in error or "not enough rights" in error:
            await update.message.reply_text(f"🤖 <b>Bot is not admin!</b>\n\nPlease add @{BOT_USERNAME} as an admin in the channel first.", parse_mode="HTML")
        else:
            await update.message.reply_text(f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> <b>Invalid channel!</b>", parse_mode="HTML")
        del user_sessions[user_id]
        return

    if user_id != OWNER_ID:
        try:
            member = await context.bot.get_chat_member(chat_id=channel_info["chat_id"], user_id=user_id)
            if member.status not in ['administrator', 'creator']:
                await loading_msg.delete()
                await update.message.reply_text(
                    f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> <b>ACCESS DENIED!</b>\n\n"
                    f"only <b>Admin</b> or <b>Owner</b> can host\n"
                    f"make sure you admin in channel/gc nigga",
                    parse_mode="HTML"
                )
                del user_sessions[user_id]
                return
        except Exception as e:
            await loading_msg.delete()
            await update.message.reply_text(
                f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> <b>Verification failed!</b>\n"
                f"Make sure you are a member/admin of the channel.",
                parse_mode="HTML"
            )
            del user_sessions[user_id]
            return

    for gid, gdata in giveaways.items():
        if gdata.get("channel") == channel_info["identifier"] and not gdata.get("ended", False):
            await loading_msg.delete()
            existing_link = f"https://t.me/{BOT_USERNAME}?start={gid}"
            await update.message.reply_text(
                f"<tg-emoji emoji-id='{EMOJI_ALERT}'>🚨</tg-emoji> <b>GIVEAWAY ALREADY ACTIVE!</b>\n\n"
                f"<b>Channel:</b> {channel_info['display_name']}\n\n"
                f"<b>Active Link:</b>\n<code>{existing_link}</code>", parse_mode="HTML")
            del user_sessions[user_id]
            return
    try:
        test_msg = await context.bot.send_message(chat_id=channel_info["chat_id"], text="✅ Bot connected!")
        await test_msg.delete()
    except:
        await loading_msg.delete()
        await update.message.reply_text(f"🤖 <b>Bot is not admin!</b>\n\nPlease add @{BOT_USERNAME} as an admin in the channel first.", parse_mode="HTML")
        del user_sessions[user_id]
        return
    giveaway_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    link = f"https://t.me/{BOT_USERNAME}?start={giveaway_id}"
    giveaways[giveaway_id] = {
        "channel": channel_info["identifier"], "channel_display": channel_info["display_name"],
        "channel_id": channel_info["chat_id"], "users": {}, "vote_counts": {}, "voted_users": {},
        "voter_votes": {}, "force_sub_channels": [],
        "creator": user_id, "creator_name": user_name, "ended": False, "created_at": datetime.now().isoformat()
    }
    update_channel_history(
        channel_identifier=channel_info["identifier"], channel_display=channel_info["display_name"],
        channel_id=channel_info["chat_id"], user_id=user_id, user_name=user_name,
        action="create", giveaway_id=giveaway_id)
    vote_messages[giveaway_id] = {}
    save_data()
    if user_id != OWNER_ID:
        await send_notification_to_owner(context, "🔔 NEW GIVEAWAY CREATED!",
            f"👤 {user_name}\n🆔 <code>{user_id}</code>\n📢 {channel_info['display_name']}\n🔗 <code>{link}</code>")
    try:
        await context.bot.send_message(
            chat_id=channel_info["chat_id"],
            text=f"<b><tg-emoji emoji-id='{EMOJI_CONFETTI}'>🎉</tg-emoji> NEW GIVEAWAY STARTED!</b>\n\n"
                 f"<b><tg-emoji emoji-id='{EMOJI_RIGHT}'>➡️</tg-emoji> JOIN HERE:</b>\n{link}",
            parse_mode="HTML", disable_web_page_preview=True)
    except: pass
    await loading_msg.delete()
    success_text = (
        f"<b><tg-emoji emoji-id='{EMOJI_CLOWN}'>✅</tg-emoji> GIVEAWAY CREATED!</b>\n\n"
        f"<b><tg-emoji emoji-id='{EMOJI_SEARCH}'>🔍</tg-emoji> ID:</b> <code>{giveaway_id}</code>\n"
        f"<b><tg-emoji emoji-id='{EMOJI_SPEAKER}'>📢</tg-emoji> Channel:</b> {channel_info['display_name']}\n\n"
        f"<b><tg-emoji emoji-id='{EMOJI_LINK}'>🔗</tg-emoji> LINK:</b>\n<code>{link}</code>"
    )
    keyboard = [[
        premium_button("MANAGE", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY),
        premium_button("MAIN MENU", callback_data="main_menu", emoji_id=EMOJI_MAIN_MENU, style=BUTTON_STYLE_PRIMARY)
    ]]
    await update.message.reply_text(success_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    del user_sessions[user_id]

# ================= MANAGE ================= #
async def my_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.answer("🔒 Only the bot owner can manage giveaways.", show_alert=True)
        return
    await query.answer()
    text = f"<b><tg-emoji emoji-id='{EMOJI_CROWN}'>💰</tg-emoji> YOUR GIVEAWAYS</b>\n\n"
    keyboard = []
    found = False
    for gid, gdata in giveaways.items():
        if gdata.get("creator") == user_id and not gdata.get("ended", False):
            found = True
            keyboard.append([premium_button(
                text=f"📢 {gdata.get('channel_display', gdata.get('channel'))}",
                callback_data=f"manage_{gid}", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY)])
    if not found:
        text = f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> <b>No active giveaways!</b>"
        keyboard.append([premium_button("CREATE NEW", callback_data="create_giveaway", emoji_id=EMOJI_CREATE, style=BUTTON_STYLE_PRIMARY)])
    keyboard.append([premium_button("MAIN MENU", callback_data="main_menu", emoji_id=EMOJI_MAIN_MENU, style=BUTTON_STYLE_PRIMARY)])
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def manage_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(query.from_user.id):
        await query.answer("🔒 Only the bot owner can manage giveaways.", show_alert=True)
        return
    await query.answer()
    giveaway_id = query.data.split("_")[1]
    if giveaway_id not in giveaways:
        await query.edit_message_text(f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> Not found!", parse_mode="HTML")
        return
    giveaway = giveaways[giveaway_id]
    status = "🟢 ACTIVE" if not giveaway.get("ended") else "🔴 ENDED"
    keyboard = [
        [premium_button("ADD VOTES", callback_data=f"addvotes_{giveaway_id}", emoji_id=EMOJI_ADD_VOTES, style=BUTTON_STYLE_PRIMARY),
         premium_button("REMOVE VOTES", callback_data=f"removevotes_{giveaway_id}", emoji_id=EMOJI_REMOVE_VOTES, style=BUTTON_STYLE_DANGER)],
        [premium_button("LEADERBOARD", callback_data=f"leaderboard_{giveaway_id}", emoji_id=EMOJI_LEADERBOARD, style=BUTTON_STYLE_PRIMARY)],
        [premium_button(f"FORCE SUB ({len(giveaway.get('force_sub_channels', []))}/2)", callback_data=f"forcesub_{giveaway_id}", emoji_id=EMOJI_SHIELD, style=BUTTON_STYLE_PRIMARY)],
        [premium_button("END GIVEAWAY", callback_data=f"endgiveaway_{giveaway_id}", emoji_id=EMOJI_END_GIVEAWAY, style=BUTTON_STYLE_DANGER)],
        [premium_button("BACK", callback_data="my_giveaways", emoji_id=EMOJI_BACK, style=BUTTON_STYLE_PRIMARY)]
    ]
    await query.edit_message_text(
        text=f"<b><tg-emoji emoji-id='{EMOJI_ARROW}'>➡️</tg-emoji> MANAGEMENT PANEL</b>\n\n"
             f"<b>Status:</b> {status}\n"
             f"<b>Channel:</b> {giveaway.get('channel_display', giveaway.get('channel'))}\n"
             f"<b>Joined:</b> {len(giveaway.get('users', {}))}",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= VOTE MANAGEMENT ================= #
async def add_votes_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giveaway_id = query.data.split("_")[1]
    context.user_data["vote_giveaway"] = giveaway_id
    context.user_data["vote_action"] = "add"
    await query.edit_message_text(
        text=f"<b><tg-emoji emoji-id='{EMOJI_DIAMOND}'>💎</tg-emoji> ADD VOTES</b>\n\nSend: <code>USER_ID VOTES</code>\nExample: <code>12345678 10</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[premium_button("BACK", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_BACK, style=BUTTON_STYLE_PRIMARY)]]))

async def remove_votes_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giveaway_id = query.data.split("_")[1]
    context.user_data["vote_giveaway"] = giveaway_id
    context.user_data["vote_action"] = "remove"
    await query.edit_message_text(
        text=f"<b><tg-emoji emoji-id='{EMOJI_DIAMOND}'>💎</tg-emoji> REMOVE VOTES</b>\n\nSend: <code>USER_ID VOTES</code>\nExample: <code>12345678 5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[premium_button("BACK", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_BACK, style=BUTTON_STYLE_PRIMARY)]]))

async def process_vote_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    giveaway_id = context.user_data.get("vote_giveaway")
    action = context.user_data.get("vote_action")
    if not giveaway_id or giveaway_id not in giveaways:
        return
    try:
        parts = update.message.text.strip().split()
        target_uid = int(parts[0])
        votes = int(parts[1])
    except:
        await update.message.reply_text(f"<tg-emoji emoji-id='{EMOJI_ALERT}'>🚨</tg-emoji> Invalid! Send <code>USER_ID VOTES</code>.", parse_mode="HTML")
        return
    giveaway = giveaways[giveaway_id]
    if target_uid not in giveaway['users']:
        await update.message.reply_text(f"<tg-emoji emoji-id='{EMOJI_ERROR}'>❌</tg-emoji> User not found!", parse_mode="HTML")
        return
    old_votes = giveaway['vote_counts'].get(target_uid, 0)
    if action == "add":
        giveaway['vote_counts'][target_uid] = old_votes + votes
        msg = f"<tg-emoji emoji-id='{EMOJI_DIAMOND}'>💎</tg-emoji> Added +{votes} votes!"
    else:
        giveaway['vote_counts'][target_uid] = max(0, old_votes - votes)
        msg = f"<tg-emoji emoji-id='{EMOJI_DIAMOND}'>💎</tg-emoji> Removed {votes} votes!"
    new_votes = giveaway['vote_counts'][target_uid]
    save_data()
    await update_vote_button_in_channel(context, giveaway_id, target_uid, new_votes)
    await update.message.reply_text(
        f"{msg}\n<b>New Total:</b> {new_votes} votes", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[premium_button("BACK", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_BACK, style=BUTTON_STYLE_PRIMARY)]]))
    del context.user_data["vote_giveaway"]
    del context.user_data["vote_action"]

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giveaway_id = query.data.split("_")[1]
    giveaway = giveaways[giveaway_id]
    sorted_users = sorted(giveaway['vote_counts'].items(), key=lambda x: x[1], reverse=True)[:10]
    text = f"<b><tg-emoji emoji-id='{EMOJI_CALENDAR}'>🗓</tg-emoji> LEADERBOARD</b>\n\n"
    if not sorted_users:
        text += "<i>No votes yet.</i>"
    else:
        for idx, (uid, votes) in enumerate(sorted_users, 1):
            name = giveaway['users'].get(uid, f"User {uid}")
            text += f"<b>{idx}.</b> {name} - <b>{votes} votes</b>\n"
    await query.edit_message_text(
        text=text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[premium_button("BACK", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_BACK, style=BUTTON_STYLE_PRIMARY)]]))

async def end_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giveaway_id = query.data.split("_")[1]
    await query.edit_message_text(
        text=f"<b><tg-emoji emoji-id='{EMOJI_LOCK}'>⚠️</tg-emoji> End this giveaway?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [premium_button("CONFIRM", callback_data=f"confirm_end_{giveaway_id}", emoji_id=EMOJI_CONFIRM, style=BUTTON_STYLE_DANGER)],
            [premium_button("CANCEL", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_CANCEL, style=BUTTON_STYLE_PRIMARY)]
        ]))

async def confirm_end_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    giveaway_id = query.data.split("_")[2]
    giveaway = giveaways[giveaway_id]
    giveaway["ended"] = True
    sorted_users = sorted(giveaway['vote_counts'].items(), key=lambda x: x[1], reverse=True)
    winner_text = "No participants."
    if sorted_users:
        w_uid, w_votes = sorted_users[0]
        winner_text = f"🏆 <b>WINNER:</b> {giveaway['users'][w_uid]} with {w_votes} votes!"
    update_channel_history(
        channel_identifier=giveaway.get("channel"), channel_display=giveaway.get("channel_display"),
        channel_id=giveaway.get("channel_id"), user_id=giveaway.get("creator"),
        user_name=giveaway.get("creator_name", "Unknown"), action="end", giveaway_id=giveaway_id)
    save_data()
    if giveaway_id in vote_messages:
        del vote_messages[giveaway_id]
    try:
        await context.bot.send_message(
            chat_id=giveaway['channel_id'],
            text=f"💰 <b>GIVEAWAY ENDED!</b>\n\n{winner_text}", parse_mode="HTML")
    except: pass
    await query.edit_message_text(text=f"✅ <b>Giveaway ended!</b>\n\n{winner_text}", parse_mode="HTML")

# ================= FORCE SUB + VOTE SECURITY ================= #
ACTIVE_MEMBER_STATUSES = {"member", "administrator", "creator"}

async def is_member_of_chat(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ACTIVE_MEMBER_STATUSES:
            return True
        if member.status == "restricted" and getattr(member, "is_member", False):
            return True
    except Exception as e:
        logger.warning(f"Membership check failed in {chat_id}: {e}")
    return False


def force_sub_join_url(channel):
    return channel.get("join_url") or (f"https://t.me/{channel['username']}" if channel.get("username") else None)


async def verify_force_sub(bot, giveaway, user_id):
    channels = giveaway.get("force_sub_channels", []) or []
    if not channels:
        return True, []
    missing = []
    for ch in channels[:2]:
        if not await is_member_of_chat(bot, ch.get("chat_id"), user_id):
            missing.append(ch)
    return not missing, missing


async def force_sub_prompt(query, giveaway, missing, giveaway_id):
    rows = []
    for ch in missing:
        url = force_sub_join_url(ch)
        if url:
            rows.append([premium_button(f"JOIN {ch.get('title', 'CHANNEL')[:24]}", url=url, emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_PRIMARY)])
    rows.append([premium_button("✅ VERIFY", callback_data=f"verify_{giveaway_id}", emoji_id=EMOJI_CONFIRM, style=BUTTON_STYLE_SUCCESS)])
    await query.edit_message_text(
        "🔒 <b>FORCE SUBSCRIBE REQUIRED</b>\n\n"
        "Join all required channels below, then press <b>VERIFY</b>.\n\n"
        "After verification, the <b>VOTE NOW</b> button will appear here.\n"
        "Nothing will be posted in the giveaway channel.",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
    )


async def get_giveaway_channel_join_url(bot, giveaway):
    chat_id = giveaway.get("channel_id")
    if not chat_id:
        return None
    try:
        chat = await bot.get_chat(chat_id)
        username = getattr(chat, "username", None)
        if username:
            return f"https://t.me/{username}"
        invite = await bot.create_chat_invite_link(chat_id, name="Giveaway Vote")
        return invite.invite_link
    except Exception as e:
        logger.warning(f"Giveaway join link failed: {e}")
        return None


async def show_vote_verification(update, context, giveaway_id, target_user_id):
    user = update.effective_user
    if await is_banned_user(update, context):
        return
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        await update.message.reply_text("❌ This giveaway is not active anymore.")
        return
    if target_user_id not in giveaway.get("users", {}):
        await update.message.reply_text("❌ Participant not found.")
        return

    # Always verify the giveaway channel in the bot, so the channel stays clean.
    missing = []
    if not await is_member_of_chat(context.bot, giveaway.get("channel_id"), user.id):
        join_url = await get_giveaway_channel_join_url(context.bot, giveaway)
        missing.append({
            "chat_id": giveaway.get("channel_id"),
            "title": giveaway.get("channel_display", "GIVEAWAY CHANNEL"),
            "join_url": join_url,
        })

    verified_force, force_missing = await verify_force_sub(context.bot, giveaway, user.id)
    missing.extend(force_missing)

    if missing:
        rows = []
        for ch in missing:
            url = force_sub_join_url(ch)
            if url:
                rows.append([premium_button(f"JOIN {ch.get('title', 'CHANNEL')[:24]}", url=url, emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_PRIMARY)])
        rows.append([premium_button("🔄 VERIFY", callback_data=f"verifyvote_{giveaway_id}_{target_user_id}", emoji_id=EMOJI_CONFIRM, style=BUTTON_STYLE_SUCCESS)])
        await update.message.reply_text(
            "🔒 <b>VOTE VERIFICATION</b>\n\n"
            "Join the required channel(s) below.\n"
            "Then press <b>VERIFY</b>.\n\n"
            "The verification happens here in the bot — the giveaway channel will not receive any extra message.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    await send_vote_confirmation(update, context, giveaway_id, target_user_id)


async def send_vote_confirmation(update, context, giveaway_id, target_user_id):
    giveaway = giveaways[giveaway_id]
    name = giveaway.get("users", {}).get(target_user_id, f"User {target_user_id}")
    await update.message.reply_text(
        f"✅ <b>VERIFIED</b>\n\n"
        f"You can vote for <b>{name}</b>.\n\n"
        f"<i>One user can have only one active vote in this giveaway.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            premium_button("🗳 VOTE NOW", callback_data=f"castvote_{giveaway_id}_{target_user_id}", emoji_id=EMOJI_VOTE, style=BUTTON_STYLE_SUCCESS)
        ]])
    )


async def configure_force_sub(update, context, giveaway_id):
    query = update.callback_query
    await query.answer()
    if not is_owner(query.from_user.id) and giveaways.get(giveaway_id, {}).get("creator") != query.from_user.id:
        return
    if giveaway_id not in giveaways:
        await query.edit_message_text("❌ Giveaway not found!")
        return
    context.user_data["force_sub_giveaway"] = giveaway_id
    await query.edit_message_text(
        "<b>🔒 FORCE SUBSCRIBE</b>\n\n"
        "Send up to <b>2 channels</b>, one per line.\n"
        "Example:\n<code>@channelone\n@channeltwo</code>\n\n"
        "Send <code>OFF</code> to disable force-sub.",
        parse_mode="HTML"
    )


async def process_force_sub(update, context):
    giveaway_id = context.user_data.get("force_sub_giveaway")
    if not giveaway_id or giveaway_id not in giveaways:
        return False
    text = (update.message.text or "").strip()
    if text.upper() == "OFF":
        giveaways[giveaway_id]["force_sub_channels"] = []
        save_data()
        del context.user_data["force_sub_giveaway"]
        await update.message.reply_text("✅ <b>Force Subscribe disabled.</b>", parse_mode="HTML")
        return True

    raw_channels = [x.strip() for x in text.splitlines() if x.strip()]
    if len(raw_channels) > 2:
        await update.message.reply_text("❌ Maximum <b>2 channels</b> only.", parse_mode="HTML")
        return True
    if not raw_channels:
        await update.message.reply_text("❌ Send at least one channel or OFF.", parse_mode="HTML")
        return True

    configured = []
    for raw in raw_channels:
        try:
            lookup = raw
            if raw.startswith("https://t.me/"):
                lookup = "@" + raw.rstrip("/").split("/")[-1].lstrip("+")
            chat = await context.bot.get_chat(lookup if raw.startswith("@") or raw.startswith("https://t.me/") else int(raw))
            member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if member.status not in {"administrator", "creator"}:
                raise RuntimeError("Bot must be an administrator in the channel")

            username = getattr(chat, "username", None)
            join_url = f"https://t.me/{username}" if username else None
            if not join_url:
                try:
                    invite = await context.bot.create_chat_invite_link(chat.id, name="Giveaway Force Sub")
                    join_url = invite.invite_link
                except Exception:
                    pass

            configured.append({
                "chat_id": chat.id,
                "title": chat.title or str(raw),
                "username": username,
                "join_url": join_url,
            })
        except Exception as e:
            await update.message.reply_text(
                f"❌ Could not configure <code>{raw}</code>.\n"
                f"Make sure the bot is an <b>administrator</b> there.\n\n<code>{e}</code>",
                parse_mode="HTML"
            )
            return True

    giveaways[giveaway_id]["force_sub_channels"] = configured[:2]
    save_data()
    del context.user_data["force_sub_giveaway"]
    names = "\n".join(f"• {c['title']}" for c in configured)
    await update.message.reply_text(
        f"✅ <b>Force Subscribe enabled</b> for {len(configured)} channel(s).\n\n{names}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[premium_button("MANAGE", callback_data=f"manage_{giveaway_id}", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY)]])
    )
    return True


async def remove_voter_vote(context, giveaway_id, voter_id, reason="left channel"):
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        return False
    voter_votes = giveaway.setdefault("voter_votes", {})
    target_id = voter_votes.pop(voter_id, None)
    if target_id is None:
        return False
    target_id = int(target_id)
    voters = giveaway.setdefault("voted_users", {}).setdefault(target_id, set())
    voters.discard(voter_id)
    giveaway["vote_counts"][target_id] = max(0, giveaway.get("vote_counts", {}).get(target_id, 0) - 1)
    new_votes = giveaway["vote_counts"][target_id]
    save_data()
    await update_vote_button_in_channel(context, giveaway_id, target_id, new_votes)
    logger.info(f"Removed vote: voter={voter_id}, target={target_id}, giveaway={giveaway_id}, reason={reason}")
    return True


async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    if not cm:
        return
    old_status = cm.old_chat_member.status
    new_status = cm.new_chat_member.status
    if new_status not in {"left", "kicked"} or old_status in {"left", "kicked"}:
        return
    chat_id = cm.chat.id
    user_id = cm.new_chat_member.user.id
    for gid, giveaway in giveaways.items():
        tracked_ids = [giveaway.get("channel_id")] + [c.get("chat_id") for c in giveaway.get("force_sub_channels", [])]
        if chat_id in tracked_ids:
            await remove_voter_vote(context, gid, user_id, reason=f"left {chat_id}")


# ================= JOIN HANDLER ================= #
async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_banned_user(update, context):
        return
    giveaway_id = query.data.split("_")[1]
    user = query.from_user

    # ── NAME/USERNAME BAN DETECTION (join se pehle) ──
    matched_in_name = user_has_banned_word(user)
    if matched_in_name:
        # Giveaway channel ID nikalo
        giveaway_ch = giveaways.get(giveaway_id, {}).get("channel_id")
        if giveaway_ch:
            await auto_ban_user(
                bot=context.bot,
                chat_id=giveaway_ch,
                user=user,
                message_id=None,
                matched_word=matched_in_name,
                reason_prefix="Banned name/username"
            )
        await query.answer(
            "🚫 Your name/username contains a banned word. You have been banned.",
            show_alert=True
        )
        return

    save_user(user.id, user.username, user.first_name, user.last_name, source="join")
    update_user_stats(user.id, "join")
    if giveaway_id not in giveaways:
        await query.answer("Giveaway not found!", show_alert=True)
        return
    giveaway = giveaways[giveaway_id]
    if giveaway.get("ended"):
        await query.answer("❌ This giveaway has already ended!", show_alert=True)
        return
    if user.id in giveaway["users"]:
        await query.answer("⚠️ Already Joined!", show_alert=True)
        return
    giveaway["users"][user.id] = user.full_name or user.first_name
    giveaway["vote_counts"][user.id] = 0
    giveaway["voted_users"][user.id] = set()
    save_data()
    await query.answer("✅ Registration Successful!", show_alert=True)
    channel_text = (
        f"<tg-emoji emoji-id='{EMOJI_SMILE}'>😎</tg-emoji> <b>Name:</b> {user.full_name or user.first_name}\n"
        f"<tg-emoji emoji-id='{EMOJI_ID}'>💌</tg-emoji> <b>ID:</b> <code>{user.id}</code>"
    )
    vote_keyboard = [[premium_button(f"Vote - 0", callback_data=f"vote_{giveaway_id}_{user.id}", emoji_id=EMOJI_VOTE, style=BUTTON_STYLE_SUCCESS)]]
    try:
        sent_msg = await context.bot.send_message(
            chat_id=giveaway['channel_id'], text=channel_text,
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(vote_keyboard))
        if giveaway_id not in vote_messages:
            vote_messages[giveaway_id] = {}
        vote_messages[giveaway_id][user.id] = sent_msg.message_id
        save_data()
    except Exception as e:
        logger.error(f"Error: {e}")
    await query.edit_message_text(
        text=f"✅ <b>Registration Successful!</b>\n\n"
             f"😎 {user.full_name or user.first_name}\n"
             f"💌 <code>{user.id}</code>\n\n"
             f"📥 Profile shared in channel!", parse_mode="HTML")

# ================= VOTE HANDLER ================= #
async def record_vote(context, giveaway_id, target_user_id, voter_id, voter):
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        return False, "❌ Giveaway not active!"
    if target_user_id not in giveaway.get("users", {}):
        return False, "❌ Participant not found!"

    # The voter must be a member of the giveaway channel.
    if not await is_member_of_chat(context.bot, giveaway.get("channel_id"), voter_id):
        return False, "⚠️ Join the giveaway channel first."

    verified, missing = await verify_force_sub(context.bot, giveaway, voter_id)
    if not verified:
        return False, "🔒 Please complete the required channel verification first."

    # One voter -> one active participant per giveaway.
    voter_votes = giveaway.setdefault("voter_votes", {})
    existing_target = voter_votes.get(voter_id)
    if existing_target is not None:
        if int(existing_target) == target_user_id:
            return False, "⚠️ You have already voted for this user!"
        name = giveaway.get("users", {}).get(int(existing_target), f"User {existing_target}")
        return False, f"⚠️ You already voted for {name}."

    giveaway.setdefault("voted_users", {}).setdefault(target_user_id, set()).add(voter_id)
    voter_votes[voter_id] = target_user_id
    giveaway["vote_counts"][target_user_id] = giveaway["vote_counts"].get(target_user_id, 0) + 1
    new_votes = giveaway["vote_counts"][target_user_id]
    save_user(voter_id, voter.username, voter.first_name, voter.last_name, source="vote")
    update_user_stats(voter_id, "vote")
    save_data()
    await update_vote_button_in_channel(context, giveaway_id, target_user_id, new_votes)
    return True, "🎉 Vote recorded!"


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    giveaway_id = parts[1]
    target_user_id = int(parts[2])
    voter_id = query.from_user.id

    if await is_banned_user(update, context):
        return
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        await query.answer("❌ Giveaway not active!", show_alert=True)
        return
    if target_user_id not in giveaway.get("users", {}):
        await query.answer("❌ Participant not found!", show_alert=True)
        return

    # Force-sub verification is handled privately in the bot.
    if giveaway.get("force_sub_channels"):
        deep_link = f"https://t.me/{BOT_USERNAME}?start=vote_{giveaway_id}_{target_user_id}"
        await query.answer("🔒 Open the bot to verify and vote.", url=deep_link)
        return

    ok, message = await record_vote(context, giveaway_id, target_user_id, voter_id, query.from_user)
    await query.answer(message, show_alert=not ok)


async def cast_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    giveaway_id = parts[1]
    target_user_id = int(parts[2])
    voter = query.from_user

    if await is_banned_user(update, context):
        return
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        await query.answer("❌ Giveaway not active!", show_alert=True)
        return

    ok, message = await record_vote(context, giveaway_id, target_user_id, voter.id, voter)
    if ok:
        await query.edit_message_text(
            f"✅ <b>VOTE RECORDED!</b>\n\n"
            f"Your vote for <b>{giveaway['users'].get(target_user_id, target_user_id)}</b> has been counted.\n\n"
            f"You cannot vote for another participant in this giveaway unless your current vote is removed.",
            parse_mode="HTML"
        )
        await query.answer("🎉 Vote recorded!")
    else:
        await query.answer(message, show_alert=True)


async def verify_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    giveaway_id = parts[1]
    target_user_id = int(parts[2])
    user = query.from_user

    if await is_banned_user(update, context):
        return
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("ended"):
        await query.answer("❌ Giveaway not active!", show_alert=True)
        return

    missing = []
    if not await is_member_of_chat(context.bot, giveaway.get("channel_id"), user.id):
        join_url = await get_giveaway_channel_join_url(context.bot, giveaway)
        missing.append({
            "chat_id": giveaway.get("channel_id"),
            "title": giveaway.get("channel_display", "GIVEAWAY CHANNEL"),
            "join_url": join_url,
        })
    _, force_missing = await verify_force_sub(context.bot, giveaway, user.id)
    missing.extend(force_missing)

    if missing:
        rows = []
        for ch in missing:
            url = force_sub_join_url(ch)
            if url:
                rows.append([premium_button(f"JOIN {ch.get('title', 'CHANNEL')[:24]}", url=url, emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_PRIMARY)])
        rows.append([premium_button("🔄 VERIFY", callback_data=f"verifyvote_{giveaway_id}_{target_user_id}", emoji_id=EMOJI_CONFIRM, style=BUTTON_STYLE_SUCCESS)])
        await query.answer("❌ You have not joined all required channels.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(rows))
        return

    await query.answer("✅ Verified!")
    await query.edit_message_text(
        "✅ <b>VERIFIED</b>\n\nYou have joined all required channels.\n\nPress <b>VOTE NOW</b> to cast your vote.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            premium_button("🗳 VOTE NOW", callback_data=f"castvote_{giveaway_id}_{target_user_id}", emoji_id=EMOJI_VOTE, style=BUTTON_STYLE_SUCCESS)
        ]])
    )


async def verify_force_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Backwards-compatible verification button for any older force-sub message.
    query = update.callback_query
    giveaway_id = query.data.split("_")[1]
    if giveaway_id not in giveaways:
        await query.answer("❌ Giveaway not found!", show_alert=True)
        return
    await query.answer("ℹ️ Please open the vote link from the giveaway channel to verify and vote here.", show_alert=True)


# ================= SILENT ADD VOTES (OWNER ONLY) ================= #
async def add_votes_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: <code>/add @channel userid votes</code>\nExample: <code>/add @mychannel 123456789 10</code>",
            parse_mode="HTML")
        return

    channel_input = args[0]
    try:
        target_uid = int(args[1])
        votes_to_add = int(args[2])
    except ValueError:
        await update.message.reply_text("❌ Invalid userid or votes.", parse_mode="HTML")
        return

    matched_giveaway_id = None
    for gid, gdata in giveaways.items():
        if gdata.get("ended", False):
            continue
        ch = gdata.get("channel", "")
        ch_id = str(gdata.get("channel_id", ""))
        if (ch == channel_input or ch_id == channel_input or
                ch_id == channel_input.lstrip('-') or ch == channel_input.lower()):
            matched_giveaway_id = gid
            break

    if not matched_giveaway_id:
        await update.message.reply_text("❌ No active giveaway found for this channel.", parse_mode="HTML")
        return

    giveaway = giveaways[matched_giveaway_id]

    if target_uid not in giveaway["users"]:
        await update.message.reply_text("❌ User not found in this giveaway.", parse_mode="HTML")
        return

    old_votes = giveaway["vote_counts"].get(target_uid, 0)
    giveaway["vote_counts"][target_uid] = old_votes + votes_to_add
    new_votes = giveaway["vote_counts"][target_uid]
    save_data()

    updated = await update_vote_button_in_channel(context, matched_giveaway_id, target_uid, new_votes)

    status = "✅ Button updated" if updated else "⚠️ Button not found in cache (votes saved)"
    await update.message.reply_text(
        f"✅ Done\n"
        f"👤 <code>{target_uid}</code>\n"
        f"📊 {old_votes} → <b>{new_votes} votes</b>\n"
        f"{status}",
        parse_mode="HTML")

# ================= WORD BAN SYSTEM ================= #

import unicodedata
import re

# Unicode lookalike map — fancy/bold/italic letters ko normal me convert karta hai
_UNICODE_MAP = {}
for _base, _variants in [
    ('a', 'ａÀÁÂÃÄÅàáâãäåĀāĂăĄą𝐚𝑎𝒂𝒶𝓪𝔞𝕒𝖆𝖺𝗮𝘢𝙖𝚊'),
    ('b', 'ｂ𝐛𝑏𝒃𝒷𝓫𝔟𝕓𝖇𝖻𝗯𝘣𝙗𝚋'),
    ('c', 'ｃÇçĆćĈĉĊċČč𝐜𝑐𝒄𝒸𝓬𝔠𝕔𝖈𝖼𝗰𝘤𝙘𝚌'),
    ('d', 'ｄĎďĐđ𝐝𝑑𝒅𝒹𝓭𝔡𝕕𝖉𝖽𝗱𝘥𝙙𝚍'),
    ('e', 'ｅÈÉÊËèéêëĒēĔĕĖėĘęĚě𝐞𝑒𝒆𝓮𝔢𝕖𝖊𝖾𝗲𝘦𝙚𝚎'),
    ('f', 'ｆ𝐟𝑓𝒇𝒻𝓯𝔣𝕗𝖋𝖿𝗳𝘧𝙛𝚏'),
    ('g', 'ｇĜĝĞğĠġĢģ𝐠𝑔𝒈𝓰𝔤𝕘𝖌𝗀𝗴𝘨𝙜𝚐'),
    ('h', 'ｈĤĥĦħ𝐡𝒉𝒽𝓱𝔥𝕙𝖍𝗁𝗵𝘩𝙝𝚑'),
    ('i', 'ｉÌÍÎÏìíîïĨĩĪīĬĭĮįİı𝐢𝑖𝒊𝒾𝓲𝔦𝕚𝖎𝗂𝗶𝘪𝙞𝚒'),
    ('j', 'ｊĴĵ𝐣𝑗𝒋𝒿𝓳𝔧𝕛𝖏𝗃𝗷𝘫𝙟𝚓'),
    ('k', 'ｋĶķĸ𝐤𝑘𝒌𝓀𝓴𝔨𝕜𝖐𝗄𝗸𝘬𝙠𝚔'),
    ('l', 'ｌĹĺĻļĽľĿŀŁł𝐥𝑙𝒍𝓁𝓵𝔩𝕝𝖑𝗅𝗹𝘭𝙡𝚕'),
    ('m', 'ｍ𝐦𝑚𝒎𝓂𝓶𝔪𝕞𝖒𝗆𝗺𝘮𝙢𝚖'),
    ('n', 'ｎÑñŃńŅņŇňŉŊŋ𝐧𝑛𝒏𝓃𝓷𝔫𝕟𝖓𝗇𝗻𝘯𝙣𝚗'),
    ('o', 'ｏÒÓÔÕÖØòóôõöøŌōŎŏŐőΟοОо0𝐨𝑜𝒐𝓸𝔬𝕠𝖔𝗈𝗼𝘰𝙤𝚘'),
    ('p', 'ｐ𝐩𝑝𝒑𝓅𝓹𝔭𝕡𝖕𝗉𝗽𝘱𝙥𝚙'),
    ('q', 'ｑ𝐪𝑞𝒒𝓆𝓺𝔮𝕢𝖖𝗊𝗾𝘲𝙦𝚚'),
    ('r', 'ｒŔŕŖŗŘř𝐫𝑟𝒓𝓇𝓻𝔯𝕣𝖗𝗋𝗿𝘳𝙧𝚛'),
    ('s', 'ｓŚśŜŝŞşŠš𝐬𝑠𝒔𝓈𝓼𝔰𝕤𝖘𝗌𝘀𝘴𝙨𝚜$5'),
    ('t', 'ｔŢţŤťŦŧ𝐭𝑡𝒕𝓉𝓽𝔱𝕥𝖙𝗍𝘁𝘵𝙩𝚝'),
    ('u', 'ｕÙÚÛÜùúûüŨũŪūŬŭŮůŰűŲų𝐮𝑢𝒖𝓊𝓾𝔲𝕦𝖚𝗎𝘂𝘶𝙪𝚞'),
    ('v', 'ｖ𝐯𝑣𝒗𝓋𝓿𝔳𝕧𝖛𝗏𝘃𝘷𝙫𝚟'),
    ('w', 'ｗŴŵ𝐰𝑤𝒘𝓌𝔀𝔴𝕨𝖜𝗐𝘄𝘸𝙬𝚠'),
    ('x', 'ｘ×𝐱𝑥𝒙𝓍𝔁𝔵𝕩𝖝𝗑𝘅𝘹𝙭𝚡'),
    ('y', 'ｙÝýÿŶŷŸ𝐲𝑦𝒚𝓎𝔂𝔶𝕪𝖞𝗒𝘆𝘺𝙮𝚢'),
    ('z', 'ｚŹźŻżŽž𝐳𝑧𝒛𝓏𝔃𝔷𝕫𝖟𝗓𝘇𝘻𝙯𝚣'),
]:
    for _ch in _variants:
        _UNICODE_MAP[_ch] = _base
        _UNICODE_MAP[_ch.upper()] = _base


def normalize_text(text: str) -> str:
    """
    Text ko aggressively normalize karo:
    - Unicode NFKD decompose
    - Fancy/bold/italic/fullwidth letters → plain ASCII
    - Uppercase → lowercase
    - Spaces, dots, dashes, underscores (l33t separators) → remove
    - Digits jo letters ki tarah dikhte hain → letter
    """
    if not text:
        return ""
    # NFKD Unicode normalization pehle
    text = unicodedata.normalize('NFKD', text)
    result = []
    for ch in text:
        # Unicode lookalike map
        if ch in _UNICODE_MAP:
            result.append(_UNICODE_MAP[ch])
        elif ch.isalpha():
            result.append(ch.lower())
        elif ch.isdigit():
            result.append(ch)
        # Separators (space dot dash underscore) — skip karo (l33t bypass block)
        # Baaki sab bhi skip — sirf letters aur digits rakho
    return "".join(result)


def contains_banned_word(text: str):
    """
    Banned word check — capital, small, unicode tricks, spaces sab bypass proof.
    Returns matched banned word or None.
    """
    if not text or not BANNED_WORDS:
        return None
    normalized = normalize_text(text)
    for word in BANNED_WORDS:
        norm_word = normalize_text(word)
        if norm_word and norm_word in normalized:
            return word
    return None


def user_has_banned_word(user) -> str | None:
    """
    User ke SAARE fields check karo — first_name, last_name, username, full_name.
    Returns matched banned word or None.
    """
    if not BANNED_WORDS:
        return None
    fields = [
        user.first_name or "",
        user.last_name or "",
        user.username or "",
        user.full_name if hasattr(user, 'full_name') and user.full_name else "",
    ]
    combined = " ".join(fields)
    return contains_banned_word(combined)

async def delete_all_user_messages(bot, chat_id: int, user_id: int):
    """
    Ban ke baad us user ke saare tracked messages delete karo.
    Telegram API me 'delete all messages from user' sirf supergroup me available hai
    via ban_chat_member revoke_messages=True — yahi best approach hai PTB me.
    Vote messages (jo DB me hain) bhi alag se delete karte hain.
    """
    # 1. Telegram native: ban + revoke_messages=True (deletes all msgs in supergroup)
    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            revoke_messages=True   # <-- yeh sab messages delete kar deta hai
        )
    except Exception as e:
        logger.warning(f"ban+revoke fail: {e}")
        # Fallback: sirf ban karo bina revoke ke
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        except Exception as e2:
            logger.warning(f"ban fallback fail: {e2}")

    # 2. Vote messages jo DB me tracked hain — unhe bhi delete karo
    deleted_vote = 0
    for gid, gdata in giveaways.items():
        if user_id in gdata.get("users", {}):
            if gid in vote_messages and user_id in vote_messages[gid]:
                mid = vote_messages[gid][user_id]
                g_channel = gdata.get("channel_id")
                if g_channel:
                    try:
                        await bot.delete_message(chat_id=g_channel, message_id=mid)
                        deleted_vote += 1
                    except Exception:
                        pass
    if deleted_vote:
        logger.info(f"Deleted {deleted_vote} vote messages for user {user_id}")


async def auto_ban_user(bot, chat_id: int, user, message_id, matched_word: str, reason_prefix: str = "Banned word"):
    """
    Ban + all msgs delete + log.
    message_id = None allowed (naam/username se detect hone pe koi triggering message nahi hota).
    reason_prefix = 'Banned word' ya 'Banned name/username' etc.
    """
    user_id = user.id
    uid_str = str(user_id)

    # Triggering message delete (agar hai)
    if message_id is not None and chat_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.warning(f"Trigger message delete fail: {e}")

    # Ban + revoke all messages
    if chat_id:
        await delete_all_user_messages(bot, chat_id, user_id)

    # Determine ban reason
    if reason_prefix == "Banned name/username":
        reason_str = f"Name/username contains banned word: '{matched_word}'"
        ban_type = "auto_name"
    else:
        reason_str = f"Banned word used: '{matched_word}'"
        ban_type = "auto_word"

    banned_users[uid_str] = {
        "user_id": user_id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "banned_at": datetime.now().isoformat(),
        "reason": reason_str,
        "chat_id": chat_id,
        "type": ban_type
    }
    if uid_str in all_users:
        all_users[uid_str]["is_banned"] = True
        all_users[uid_str]["ban_reason"] = reason_str
    save_data()

    uname = f"@{user.username}" if user.username else "N/A"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    trigger_label = "Name/Username" if ban_type == "auto_name" else "Message Word"
    log_text = (
        f"<b>🚨 AUTO BAN — {trigger_label.upper()}</b>\n\n"
        f"<b>👤 Name:</b> {full_name}\n"
        f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
        f"<b>📛 Username:</b> {uname}\n"
        f"<b>🔤 Word:</b> <code>{matched_word}</code>\n"
        f"<b>📌 Trigger:</b> {trigger_label}\n"
        f"<b>💬 Chat ID:</b> <code>{chat_id}</code>\n"
        f"<b>🕒 Time:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n\n"
        f"<b>Unban:</b> <code>/unban {user_id}</code>"
    )
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Log channel send fail: {e}")

async def addwords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /addwords word1 word2 word3"""
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        current = ", ".join(BANNED_WORDS) if BANNED_WORDS else "Koi nahi"
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id='{EMOJI_SHIELD}'>🛡️</tg-emoji> BANNED WORDS</b>\n\n"
            f"<b>Current:</b> <code>{current}</code>\n\n"
            f"<b>Usage:</b> <code>/addwords word1 word2</code>",
            parse_mode="HTML"
        )
        return
    new_words = [w.lower().strip() for w in context.args if w.strip()]
    added = []
    for w in new_words:
        if w not in BANNED_WORDS:
            BANNED_WORDS.append(w)
            added.append(w)
    save_data()
    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_CONFIRM}'>✅</tg-emoji> Words Added</b>\n\n"
        f"<b>Added:</b> <code>{', '.join(added) if added else 'Already existed'}</code>\n"
        f"<b>Total Banned Words:</b> <code>{len(BANNED_WORDS)}</code>",
        parse_mode="HTML"
    )

async def removewords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /removewords word1 word2"""
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: <code>/removewords word1 word2</code>", parse_mode="HTML")
        return
    removed = []
    for w in context.args:
        w = w.lower().strip()
        if w in BANNED_WORDS:
            BANNED_WORDS.remove(w)
            removed.append(w)
    save_data()
    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_ALERT}'>🗑️</tg-emoji> Words Removed</b>\n\n"
        f"<b>Removed:</b> <code>{', '.join(removed) if removed else 'Not found'}</code>",
        parse_mode="HTML"
    )

# ================= BAN / UNBAN ================= #

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage:
      /ban USER_ID reason
      /ban (reply to a message) reason
    """
    if not is_owner(update.effective_user.id):
        return

    target_id = None
    reason = "Manual ban by owner"

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if context.args:
            reason = " ".join(context.args)
    elif context.args:
        try:
            target_id = int(context.args[0])
            if len(context.args) > 1:
                reason = " ".join(context.args[1:])
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID.", parse_mode="HTML")
            return
    else:
        await update.message.reply_text(
            f"<b>Usage:</b>\n"
            f"<code>/ban USER_ID reason</code>\n"
            f"<code>/ban</code> (reply to msg)\n",
            parse_mode="HTML"
        )
        return

    if target_id == OWNER_ID:
        await update.message.reply_text("❌ Khud ko ban nahi kar sakte bhai.", parse_mode="HTML")
        return

    uid_str = str(target_id)
    banned_in = []
    for ch_data in channel_history.values():
        ch_id = ch_data.get("channel_id")
        if not ch_id:
            continue
        try:
            # revoke_messages=True — sab messages usi channel se delete ho jaate hain
            await context.bot.ban_chat_member(
                chat_id=ch_id,
                user_id=target_id,
                revoke_messages=True
            )
            banned_in.append(str(ch_id))
        except Exception as e:
            logger.warning(f"Ban+revoke fail in {ch_id}: {e}")
            try:
                await context.bot.ban_chat_member(chat_id=ch_id, user_id=target_id)
                if str(ch_id) not in banned_in:
                    banned_in.append(str(ch_id))
            except Exception:
                pass

    # Vote messages jo DB me tracked hain — manually delete karo
    for gid, gdata in giveaways.items():
        if target_id in gdata.get("users", {}):
            if gid in vote_messages and target_id in vote_messages[gid]:
                mid = vote_messages[gid][target_id]
                g_channel = gdata.get("channel_id")
                if g_channel:
                    try:
                        await context.bot.delete_message(chat_id=g_channel, message_id=mid)
                    except Exception:
                        pass

    banned_users[uid_str] = {
        "user_id": target_id,
        "username": "",
        "first_name": f"User {target_id}",
        "last_name": "",
        "banned_at": datetime.now().isoformat(),
        "reason": reason,
        "chat_id": banned_in[0] if banned_in else None,
        "banned_in_all": banned_in,
        "type": "manual"
    }
    if uid_str in all_users:
        all_users[uid_str]["is_banned"] = True
        all_users[uid_str]["ban_reason"] = reason
    save_data()

    log_text = (
        f"<b><tg-emoji emoji-id='{EMOJI_SHIELD}'>🛡️</tg-emoji> MANUAL BAN</b>\n\n"
        f"<b>🆔 User ID:</b> <code>{target_id}</code>\n"
        f"<b>📝 Reason:</b> {reason}\n"
        f"<b>💬 Banned in:</b> <code>{len(banned_in)}</code> chats\n"
        f"<b>🕒 Time:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n\n"
        f"<b>Unban:</b> <code>/unban {target_id}</code>"
    )
    try:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Log fail: {e}")

    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_CONFIRM}'>✅</tg-emoji> BANNED</b>\n\n"
        f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
        f"<b>📝 Reason:</b> {reason}\n"
        f"<b>💬 Chats:</b> <code>{len(banned_in)}</code>",
        parse_mode="HTML"
    )

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /unban USER_ID"""
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            f"<b>Usage:</b> <code>/unban USER_ID</code>\n"
            f"<b>Example:</b> <code>/unban 123456789</code>",
            parse_mode="HTML"
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID.", parse_mode="HTML")
        return

    uid_str = str(target_id)
    user_data = banned_users.get(uid_str)

    # Collect all chats to unban from
    chats_to_unban = []
    if user_data:
        if user_data.get("banned_in_all"):
            chats_to_unban = [int(c) for c in user_data["banned_in_all"]]
        elif user_data.get("chat_id"):
            chats_to_unban = [int(user_data["chat_id"])]

    unban_count = 0
    for ch_id in chats_to_unban:
        try:
            await context.bot.unban_chat_member(chat_id=ch_id, user_id=target_id, only_if_banned=True)
            unban_count += 1
        except Exception as e:
            logger.warning(f"Telegram unban fail in {ch_id}: {e}")

    if uid_str in banned_users:
        del banned_users[uid_str]
    if uid_str in all_users:
        all_users[uid_str].pop("is_banned", None)
        all_users[uid_str].pop("ban_reason", None)
    save_data()

    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_CONFIRM}'>✅</tg-emoji> USER UNBANNED</b>\n\n"
        f"<b>🆔 User ID:</b> <code>{target_id}</code>\n"
        f"<b>💬 Unbanned from:</b> <code>{unban_count}</code> chats",
        parse_mode="HTML"
    )

async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not banned_users:
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id='{EMOJI_SHIELD}'>🛡️</tg-emoji> Ban List</b>\n\n<i>Koi bhi ban nahi hai.</i>",
            parse_mode="HTML"
        )
        return

    text = f"<b><tg-emoji emoji-id='{EMOJI_SHIELD}'>🛡️</tg-emoji> BANNED USERS ({len(banned_users)})</b>\n<code>{'─'*28}</code>\n\n"
    for uid_str, info in list(banned_users.items())[-20:]:
        name = info.get("first_name", "Unknown")
        uname = f"@{info['username']}" if info.get("username") else "N/A"
        reason = info.get("reason", "N/A")
        btype = info.get("type", "auto")
        icon = "🤖" if "auto" in btype else "👑"
        text += (
            f"{icon} <b>{name}</b> ({uname})\n"
            f"   🆔 <code>{uid_str}</code>\n"
            f"   📝 {reason[:50]}\n\n"
        )
    await update.message.reply_text(text, parse_mode="HTML")

# ================= WARN SYSTEM ================= #

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /warn USER_ID reason  OR  reply to message"""
    if not is_owner(update.effective_user.id):
        return

    target_id = None
    reason = "No reason given"

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if context.args:
            reason = " ".join(context.args)
    elif context.args:
        try:
            target_id = int(context.args[0])
            if len(context.args) > 1:
                reason = " ".join(context.args[1:])
        except ValueError:
            await update.message.reply_text("❌ Invalid ID.", parse_mode="HTML")
            return
    else:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/warn USER_ID reason</code>", parse_mode="HTML"
        )
        return

    if target_id == OWNER_ID:
        await update.message.reply_text("❌ Owner ko warn nahi kar sakte.", parse_mode="HTML")
        return

    uid_str = str(target_id)
    if uid_str not in warnings_db:
        warnings_db[uid_str] = {"count": 0, "reasons": []}

    warnings_db[uid_str]["count"] += 1
    warnings_db[uid_str]["reasons"].append({
        "reason": reason,
        "at": datetime.now().isoformat()
    })
    current_warns = warnings_db[uid_str]["count"]
    save_data()

    if current_warns >= MAX_WARNINGS:
        # Auto ban on 3 warnings
        for ch_data in channel_history.values():
            ch_id = ch_data.get("channel_id")
            if ch_id:
                try:
                    await context.bot.ban_chat_member(chat_id=ch_id, user_id=target_id)
                except Exception:
                    pass

        banned_users[uid_str] = {
            "user_id": target_id, "username": "", "first_name": f"User {target_id}",
            "last_name": "", "banned_at": datetime.now().isoformat(),
            "reason": f"3 warnings reached. Last: {reason}",
            "chat_id": None, "type": "auto_warn"
        }
        save_data()

        log_text = (
            f"<b><tg-emoji emoji-id='{EMOJI_ALERT}'>🚨</tg-emoji> AUTO BAN (3 WARNINGS)</b>\n\n"
            f"<b>🆔 User ID:</b> <code>{target_id}</code>\n"
            f"<b>📝 Last Reason:</b> {reason}\n"
            f"<b>🕒 Time:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n\n"
            f"<b>Unban:</b> <code>/unban {target_id}</code>"
        )
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
        except Exception:
            pass

        await update.message.reply_text(
            f"<b><tg-emoji emoji-id='{EMOJI_ALERT}'>🚨</tg-emoji> 3 WARNINGS HIT — AUTO BANNED</b>\n\n"
            f"<b>🆔 ID:</b> <code>{target_id}</code>",
            parse_mode="HTML"
        )
        return

    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_ALERT}'>⚠️</tg-emoji> WARNING ISSUED</b>\n\n"
        f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
        f"<b>📝 Reason:</b> {reason}\n"
        f"<b>⚠️ Warnings:</b> <code>{current_warns}/{MAX_WARNINGS}</code>",
        parse_mode="HTML"
    )

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /unwarn USER_ID"""
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("<b>Usage:</b> <code>/unwarn USER_ID</code>", parse_mode="HTML")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode="HTML")
        return

    uid_str = str(target_id)
    if uid_str in warnings_db:
        del warnings_db[uid_str]
        save_data()
    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_CONFIRM}'>✅</tg-emoji> Warnings cleared</b>\n\n"
        f"<b>🆔 ID:</b> <code>{target_id}</code>",
        parse_mode="HTML"
    )

# ================= USER INFO ================= #

async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /userinfo USER_ID  OR  reply to message"""
    if not is_owner(update.effective_user.id):
        return

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid ID.", parse_mode="HTML")
            return
    else:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/userinfo USER_ID</code>", parse_mode="HTML"
        )
        return

    uid_str = str(target_id)
    udata = all_users.get(uid_str)
    is_banned = uid_str in banned_users
    ban_info = banned_users.get(uid_str, {})
    warn_info = warnings_db.get(uid_str, {})

    if not udata:
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id='{EMOJI_SEARCH}'>🔍</tg-emoji> User Info</b>\n\n"
            f"🆔 <code>{target_id}</code>\n"
            f"<i>Bot me registered nahi hai.</i>\n"
            f"🚫 Banned: <b>{'Yes' if is_banned else 'No'}</b>",
            parse_mode="HTML"
        )
        return

    uname = f"@{udata['username']}" if udata.get("username") else "N/A"
    full_name = f"{udata.get('first_name','')} {udata.get('last_name','')}".strip()
    joined = udata.get("joined_at", "N/A")[:10]
    last_active = udata.get("last_active", "N/A")[:10]
    votes_given = udata.get("total_votes_given", 0)
    ga_joined = udata.get("total_giveaways_joined", 0)

    participating_in = []
    for gid, gdata in giveaways.items():
        if target_id in gdata.get("users", {}):
            status = "🔴 Ended" if gdata.get("ended") else "🟢 Active"
            participating_in.append(f"{gid[:6]}... {status}")

    ga_text = "\n".join([f"   • {x}" for x in participating_in]) if participating_in else "   None"

    ban_section = ""
    if is_banned:
        ban_section = (
            f"\n<b>🚫 BAN INFO</b>\n"
            f"├ Reason: {ban_info.get('reason', 'N/A')}\n"
            f"└ Banned at: {ban_info.get('banned_at', 'N/A')[:10]}\n"
        )

    warn_section = ""
    if warn_info.get("count", 0) > 0:
        warn_section = (
            f"\n<b>⚠️ WARNINGS</b>\n"
            f"└ Count: <code>{warn_info['count']}/{MAX_WARNINGS}</code>\n"
        )

    text = (
        f"<b><tg-emoji emoji-id='{EMOJI_SEARCH}'>🔍</tg-emoji> USER INFO</b>\n"
        f"<code>{'─'*28}</code>\n\n"
        f"<b>👤 Name:</b> {full_name}\n"
        f"<b>📛 Username:</b> {uname}\n"
        f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
        f"<b>📅 Joined:</b> <code>{joined}</code>\n"
        f"<b>⏱ Last Active:</b> <code>{last_active}</code>\n"
        f"<b>🗳️ Votes Given:</b> <code>{votes_given}</code>\n"
        f"<b>🎁 Giveaways Joined:</b> <code>{ga_joined}</code>\n"
        f"<b>🚫 Banned:</b> <b>{'✅ Yes' if is_banned else '❌ No'}</b>\n"
        f"{ban_section}{warn_section}\n"
        f"<b>🎯 Active In:</b>\n{ga_text}"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ================= ADMIN COMMANDS ================= #

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    active_g = sum(1 for g in giveaways.values() if not g.get("ended", False))
    total_votes = sum(sum(g.get("vote_counts", {}).values()) for g in giveaways.values())
    banned_count = len(banned_users)
    words_list = ", ".join(BANNED_WORDS) if BANNED_WORDS else "None"
    total_warns = sum(1 for w in warnings_db.values() if w.get("count", 0) > 0)

    # Split into 2 messages to avoid Telegram message length / entity limits
    stats_text = (
        f"<b>👑 ADMIN CONTROL PANEL</b>\n"
        f"<code>{'═' * 28}</code>\n\n"
        f"<b>📊 BOT STATS</b>\n"
        f"├ 👥 Users: <code>{len(all_users)}</code>\n"
        f"├ 🎁 Giveaways: <code>{len(giveaways)}</code>  (Active: <code>{active_g}</code>)\n"
        f"├ 📺 Channels: <code>{len(channel_history)}</code>\n"
        f"└ 🗳️ Total Votes: <code>{total_votes}</code>\n\n"
        f"<b>🛡️ SECURITY</b>\n"
        f"├ 🚫 Banned Users: <code>{banned_count}</code>\n"
        f"├ ⚠️ Warned Users: <code>{total_warns}</code>\n"
        f"└ 🔤 Banned Words: <code>{words_list}</code>"
    )

    cmds_text = (
        f"<b>🚀 ALL COMMANDS</b>\n"
        f"<code>{'─' * 28}</code>\n"
        f"📢 /broadcast — Message all users\n"
        f"📊 /stats — Bot statistics\n"
        f"👥 /users — Recent users list\n"
        f"📺 /channels — Channel list\n"
        f"💾 /backup — Download DB\n"
        f"📁 /db — Current DB file\n"
        f"🔄 /autobackup — Force backup now\n"
        f"📥 /restore — Restore DB from file\n"
        f"⚙️ /settings — Bot config\n"
        f"🔔 /testnotify — Test alert\n"
        f"🗑️ /clear — Clear all data\n"
        f"💎 /add — Add votes silent\n"
        f"<code>{'─' * 28}</code>\n"
        f"🛡️ /addwords — Add banned words\n"
        f"🗑️ /removewords — Remove banned words\n"
        f"🚫 /ban ID reason — Manual ban\n"
        f"✅ /unban ID — Unban user\n"
        f"📋 /banlist — List banned users\n"
        f"⚠️ /warn ID reason — Issue warning\n"
        f"✅ /unwarn ID — Clear warnings\n"
        f"🔍 /userinfo ID — Full user details"
    )

    await update.message.reply_text(stats_text, parse_mode="HTML")
    await update.message.reply_text(cmds_text, parse_mode="HTML")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    admin_sessions[OWNER_ID] = {"step": "waiting_broadcast"}
    await update.message.reply_text(
        "<b>📢 BROADCAST SYSTEM</b>\n\n"
        "Send your message (Text, Photo, Video, File, etc.) below.\n\n"
        f"<b>Total Users:</b> <code>{len(all_users)}</code>\n"
        f"<b>Total Channels:</b> <code>{len(channel_history)}</code>\n\n"
        "Send /cancel to abort.", parse_mode="HTML")

async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID or admin_sessions.get(OWNER_ID, {}).get("step") != "waiting_broadcast":
        return
    if update.message.text == "/cancel":
        del admin_sessions[OWNER_ID]
        await update.message.reply_text("❌ Broadcast cancelled!")
        return

    status_msg = await update.message.reply_text(
        "⚡ <b>Broadcasting message to all users & channels...</b>", parse_mode="HTML"
    )

    targets = set()
    for uid in all_users.keys():
        targets.add(int(uid))
    for ch_data in channel_history.values():
        if ch_data.get("channel_id"):
            targets.add(int(ch_data.get("channel_id")))

    success = 0
    fail = 0

    for target_id in targets:
        try:
            await update.message.copy(chat_id=target_id)
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)

    del admin_sessions[OWNER_ID]
    await status_msg.edit_text(
        "🎉 <b>BROADCAST COMPLETED!</b>\n\n"
        f"✅ <b>Sent Successfully:</b> <code>{success}</code>\n"
        f"❌ <b>Failed/Blocked:</b> <code>{fail}</code>",
        parse_mode="HTML"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    active = sum(1 for g in giveaways.values() if not g.get("ended", False))
    participants = sum(len(g.get("users", {})) for g in giveaways.values())
    votes = sum(sum(g.get("vote_counts", {}).values()) for g in giveaways.values())
    text = (
        f"<b><tg-emoji emoji-id='{EMOJI_STATS}'>📊</tg-emoji> BOT STATISTICS</b>\n\n"
        f"<b>👥 Users:</b> <code>{len(all_users)}</code>\n"
        f"<b>🎁 Giveaways:</b> <code>{len(giveaways)}</code>\n"
        f"<b>🟢 Active:</b> <code>{active}</code>\n"
        f"<b>📺 Channels:</b> <code>{len(channel_history)}</code>\n"
        f"<b>👤 Participants:</b> <code>{participants}</code>\n"
        f"<b>🗳️ Votes:</b> <code>{votes}</code>\n"
        f"<b>🚫 Banned:</b> <code>{len(banned_users)}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    users_list = list(all_users.values())[-15:]
    users_list.reverse()
    text = f"<b><tg-emoji emoji-id='{EMOJI_USERS}'>👥</tg-emoji> RECENT USERS</b>\n\n"
    for u in users_list:
        text += f"<b>👤 {u.get('first_name', 'Unknown')}</b>\n   🆔 <code>{u.get('user_id')}</code>\n   📝 @{u.get('username', 'no')}\n   📍 {u.get('source', '?')}\n\n"
    text += f"\n<b>Total Users:</b> <code>{len(all_users)}</code>"
    await update.message.reply_text(text, parse_mode="HTML")

async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    text = f"<b><tg-emoji emoji-id='{EMOJI_CHANNEL}'>📺</tg-emoji> CHANNEL GIVEAWAY HISTORY</b>\n\n"
    text += "<b>🟢 ACTIVE GIVEAWAYS</b>\n<code>─────────────────</code>\n"
    active_found = False
    for ch_key, ch_data in channel_history.items():
        active_giveaways = [g for g in ch_data.get("giveaways", []) if g.get("status") == "active"]
        if active_giveaways:
            active_found = True
            text += f"\n<b>📢 {ch_data.get('channel_display', 'Unknown')}</b>\n"
            text += f"   🔍 Type: <code>{ch_data.get('type', 'unknown').upper()}</code>\n"
            text += f"   🆔 ID: <code>{ch_data.get('channel_id', 'N/A')}</code>\n"
            text += f"   👤 Owner: {ch_data.get('created_by_name', 'Unknown')}\n"
            for g in active_giveaways:
                text += f"      • ID: <code>{g.get('giveaway_id', 'N/A')}</code>\n"
                text += f"        📅 Created: {g.get('created_at', '')[:10]}\n"
    if not active_found:
        text += "<i>No active giveaways</i>\n"
    text += "\n<b>🔴 GIVEAWAY HISTORY</b>\n<code>─────────────────</code>\n"
    ended_found = False
    for ch_key, ch_data in list(channel_history.items())[-10:]:
        ended_giveaways = [g for g in ch_data.get("giveaways", []) if g.get("status") == "ended"]
        if ended_giveaways:
            ended_found = True
            text += f"\n<b>📢 {ch_data.get('channel_display', 'Unknown')}</b>\n"
            text += f"   🔍 Type: <code>{ch_data.get('type', 'unknown').upper()}</code>\n"
            text += f"   🆔 ID: <code>{ch_data.get('channel_id', 'N/A')}</code>\n"
            text += f"   👤 Owner: {ch_data.get('created_by_name', 'Unknown')}\n"
            text += f"   🎁 Total: <code>{ch_data.get('total_giveaways', 0)}</code> giveaways\n"
    if not ended_found:
        text += "<i>No giveaway history yet</i>\n"
    await update.message.reply_text(text, parse_mode="HTML")

# ================= BACKUP, DB & RESTORE COMMANDS ================= #
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    save_data()
    if os.path.exists(DATA_FILE):
        await update.message.reply_document(
            document=open(DATA_FILE, 'rb'),
            caption=f"<b><tg-emoji emoji-id='{EMOJI_BACKUP}'>💾</tg-emoji> DATABASE BACKUP</b>\n\n"
                    f"<b>👥 Users:</b> <code>{len(all_users)}</code>\n"
                    f"<b>🎁 Giveaways:</b> <code>{len(giveaways)}</code>\n"
                    f"<b>📺 Channels:</b> <code>{len(channel_history)}</code>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Backup file not found!", parse_mode="HTML")

async def db_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    save_data()
    if os.path.exists(DATA_FILE):
        await update.message.reply_document(
            document=open(DATA_FILE, 'rb'),
            caption=f"<b><tg-emoji emoji-id='{EMOJI_BACKUP}'>📁</tg-emoji> CURRENT DATABASE FILE</b>\n\n"
                    f"<b>File:</b> <code>{DATA_FILE}</code>\n"
                    f"<b>Last Updated:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Database file does not exist yet.", parse_mode="HTML")

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    admin_sessions[OWNER_ID] = {"step": "waiting_db_restore"}
    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_BACKUP}'>📥</tg-emoji> DATABASE RESTORE SYSTEM</b>\n\n"
        f"Apni saved <code>bot_data.json</code> file ko yahan <b>File / Document</b> ke roop me bhejein.\n\n"
        f"Send /cancel to abort.",
        parse_mode="HTML"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return

    if admin_sessions.get(OWNER_ID, {}).get("step") == "waiting_db_restore":
        document = update.message.document
        if not document.file_name.endswith('.json'):
            await update.message.reply_text("❌ Kripya sirf valid <code>.json</code> database file send karein!", parse_mode="HTML")
            return

        status_msg = await update.message.reply_text("⚡ <b>Database file restoring...</b>", parse_mode="HTML")
        try:
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()
            data = json.loads(file_bytes.decode('utf-8'))

            global giveaways, all_users, channel_history, vote_messages, banned_users, warnings_db
            giveaways = _normalize_giveaway_data(data.get("giveaways", {}))
            all_users = data.get("all_users", data.get("users", {}))
            channel_history = data.get("channel_history", {})
            banned_users = data.get("banned_users", {})
            warnings_db = data.get("warnings_db", {})
            BANNED_WORDS.clear()
            BANNED_WORDS.extend(data.get("banned_words", []))

            vote_messages = {}
            if "vote_messages" in data:
                vm_raw = data["vote_messages"]
                for gid, users in vm_raw.items():
                    vote_messages[gid] = {}
                    for uid, mid in users.items():
                        try:
                            vote_messages[gid][int(uid)] = mid
                        except:
                            vote_messages[gid][uid] = mid

            save_data()
            del admin_sessions[OWNER_ID]

            await status_msg.edit_text(
                f"<b><tg-emoji emoji-id='{EMOJI_CONFETTI}'>🎉</tg-emoji> DATABASE RESTORED SUCCESSFULLY!</b>\n\n"
                f"<b>👥 Restored Users:</b> <code>{len(all_users)}</code>\n"
                f"<b>🎁 Restored Giveaways:</b> <code>{len(giveaways)}</code>\n"
                f"<b>📺 Restored Channels:</b> <code>{len(channel_history)}</code>\n"
                f"<b>🚫 Restored Bans:</b> <code>{len(banned_users)}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error restoring DB: {e}")
            await status_msg.edit_text(f"❌ <b>Invalid JSON file format!</b> Error: <code>{e}</code>", parse_mode="HTML")
            del admin_sessions[OWNER_ID]

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    await update.message.reply_text(
        f"<b><tg-emoji emoji-id='{EMOJI_SETTINGS}'>⚙️</tg-emoji> SETTINGS</b>\n\n"
        f"<b>Bot Username:</b> @{BOT_USERNAME}\n"
        f"<b>Owner ID:</b> <code>{OWNER_ID}</code>\n"
        f"<b>Data File:</b> <code>{DATA_FILE}</code>\n"
        f"<b>Max Warnings:</b> <code>{MAX_WARNINGS}</code>\n"
        f"<b>Log Channel:</b> <code>{LOG_CHANNEL_ID}</code>",
        parse_mode="HTML")

async def testnotify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    await send_notification_to_owner(context, "🔔 TEST NOTIFICATION", "All systems working fine.")
    await update.message.reply_text("✅ Test notification sent!", parse_mode="HTML")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ CONFIRM CLEAR", callback_data="confirm_clear"),
        InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")
    ]])
    await update.message.reply_text(
        f"<b>⚠️ DANGER ZONE</b>\n\nDelete all data?\n\n"
        f"• <code>{len(all_users)}</code> users\n"
        f"• <code>{len(giveaways)}</code> giveaways\n\n"
        f"<b>Cannot be undone!</b>",
        parse_mode="HTML", reply_markup=keyboard)

async def confirm_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(query.from_user.id):
        return
    global giveaways, all_users, channel_history, vote_messages
    giveaways = {}
    all_users = {}
    channel_history = {}
    vote_messages = {}
    save_data(force=True)
    await query.edit_message_text("✅ <b>All data cleared!</b>", parse_mode="HTML")

# ================= MAIN MENU ================= #
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    if is_owner(query.from_user.id):
        keyboard.append([premium_button("CONNECT", url=f"https://t.me/{BOT_USERNAME}?startchannel=true&admin=post_messages", emoji_id=EMOJI_CONNECT, style=BUTTON_STYLE_SUCCESS)])
        keyboard.append([premium_button("CREATE", callback_data="create_giveaway", emoji_id=EMOJI_CREATE, style=BUTTON_STYLE_PRIMARY),
                         premium_button("MANAGE", callback_data="my_giveaways", emoji_id=EMOJI_MANAGE, style=BUTTON_STYLE_PRIMARY)])
    await query.edit_message_text(text="<b>🌐 MAIN MENU</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

# ================= BUTTON ROUTER ================= #
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ── PERMANENT BAN GATE — koi bhi button press ho, pehle yahan aao ──
    if await is_banned_user(update, context):
        try:
            await update.callback_query.answer()  # spinner hatao
        except Exception:
            pass
        return
    query = update.callback_query
    data = query.data
    if data == "confirm_clear":
        await confirm_clear_callback(update, context)
    elif data == "create_giveaway":
        await create_giveaway_flow(update, context)
    elif data == "cancel_creation":
        await cancel_creation(update, context)
    elif data == "my_giveaways":
        await my_giveaways(update, context)
    elif data == "main_menu":
        await main_menu(update, context)
    elif data.startswith("manage_"):
        await manage_giveaway(update, context)
    elif data.startswith("forcesub_"):
        await configure_force_sub(update, context, data.split("_", 1)[1])
    elif data.startswith("verifyvote_"):
        await verify_vote_callback(update, context)
    elif data.startswith("castvote_"):
        await cast_vote_callback(update, context)
    elif data.startswith("verify_"):
        await verify_force_sub_callback(update, context)
    elif data.startswith("addvotes_"):
        await add_votes_flow(update, context)
    elif data.startswith("removevotes_"):
        await remove_votes_flow(update, context)
    elif data.startswith("leaderboard_"):
        await show_leaderboard(update, context)
    elif data.startswith("endgiveaway_"):
        await end_giveaway(update, context)
    elif data.startswith("confirm_end_"):
        await confirm_end_giveaway(update, context)
    elif data.startswith("join_"):
        await handle_join(update, context)
    elif data.startswith("vote_"):
        await handle_vote(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    uid_str = str(user_id)

    # ── SECURITY LAYER 1: Banned user — message delete + ban notice ──
    if await is_banned_user(update, context):
        try:
            await update.message.delete()
        except Exception:
            pass
        return

    # ── SECURITY LAYER 2: Banned word check ──
    if update.message.text and user_id != OWNER_ID:
        matched = contains_banned_word(update.message.text)
        if matched and update.effective_chat:
            await auto_ban_user(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                user=update.effective_user,
                message_id=update.message.message_id,
                matched_word=matched,
                reason_prefix="Banned word"
            )
            return

    # ── Normal flow ──
    if user_id == OWNER_ID and admin_sessions.get(OWNER_ID, {}).get("step") == "waiting_broadcast":
        await process_broadcast(update, context)
        return
    if user_id in user_sessions and user_sessions[user_id].get("step") == "waiting_channel":
        await process_channel(update, context)
        return
    if "force_sub_giveaway" in context.user_data:
        await process_force_sub(update, context)
        return
    if "vote_giveaway" in context.user_data:
        await process_vote_change(update, context)
        return

# ================= AUTO BACKUP SYSTEM ================= #
backup_task = None

def _load_backup_ids():
    ids = list(backup_msg_ids)
    if not ids and os.path.exists(BACKUP_IDS_FILE):
        try:
            with open(BACKUP_IDS_FILE, 'r', encoding='utf-8') as f:
                old = json.load(f)
            if isinstance(old, list):
                ids = [int(i) for i in old]
        except Exception as e:
            logger.error(f"Backup ids load error: {e}")
    return ids

def _save_backup_ids(ids):
    global backup_msg_ids
    backup_msg_ids = [int(i) for i in ids]
    save_data()

async def restore_from_channel(bot):
    """Restart ke baad DB gayab/khali ho to channel ke PINNED backup se wapas le aata hai."""
    if giveaways or all_users:
        return False
    try:
        chat = await bot.get_chat(BACKUP_CHANNEL_ID)
        pinned = getattr(chat, "pinned_message", None)
        if not pinned or not pinned.document:
            logger.warning("Channel me koi pinned backup nahi mila - restore skip")
            return False
        tg_file = await bot.get_file(pinned.document.file_id)
        await tg_file.download_to_drive(DATA_FILE)
        load_data()
        logger.info(f"Channel backup se RESTORE: {len(all_users)} users, {len(giveaways)} giveaways")
        return True
    except Exception as e:
        logger.error(f"Channel restore fail: {e}")
        return False

async def send_auto_backup(bot):
    """Naya DB channel me bhejta hai, phir purane backup delete kar deta hai."""
    save_data()
    if not os.path.exists(DATA_FILE):
        logger.warning("Auto backup skip: data file nahi mili")
        return None

    now = datetime.now()
    with open(DATA_FILE, 'rb') as f:
        msg = await bot.send_document(
            chat_id=BACKUP_CHANNEL_ID,
            document=f,
            filename=f"bot_data_{now.strftime('%d-%m-%Y_%H-%M')}.json",
            caption=f"<b><tg-emoji emoji-id='{EMOJI_BACKUP}'>💾</tg-emoji> AUTO DATABASE BACKUP</b>\n\n"
                    f"<b>👥 Users:</b> <code>{len(all_users)}</code>\n"
                    f"<b>🎁 Giveaways:</b> <code>{len(giveaways)}</code>\n"
                    f"<b>📺 Channels:</b> <code>{len(channel_history)}</code>\n"
                    f"<b>🚫 Banned:</b> <code>{len(banned_users)}</code>\n"
                    f"<b>🕒 Time:</b> <code>{now.strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode="HTML"
        )

    try:
        await bot.pin_chat_message(
            chat_id=BACKUP_CHANNEL_ID,
            message_id=msg.message_id,
            disable_notification=True
        )
    except Exception as e:
        logger.warning(f"Backup pin nahi hua (Pin Messages permission chahiye): {e}")

    ids = _load_backup_ids()
    ids.append(msg.message_id)

    keep = max(1, KEEP_LAST_BACKUPS)
    old_ids, ids = ids[:-keep], ids[-keep:]

    for mid in old_ids:
        try:
            await bot.delete_message(chat_id=BACKUP_CHANNEL_ID, message_id=mid)
        except Exception as e:
            logger.warning(f"Purana backup {mid} delete nahi hua: {e}")

    _save_backup_ids(ids)
    logger.info(f"Auto backup sent (msg {msg.message_id}) | {len(old_ids)} purane delete")
    return msg

async def auto_backup_loop(app):
    await asyncio.sleep(15)
    while True:
        try:
            await send_auto_backup(app.bot)
        except Exception as e:
            logger.error(f"Auto backup error: {e}")
        await asyncio.sleep(AUTO_BACKUP_MINUTES * 60)

async def autobackup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    try:
        await send_auto_backup(context.bot)
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id='{EMOJI_CONFIRM}'>✅</tg-emoji> Backup channel me bhej diya gaya.</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Backup fail: <code>{e}</code>", parse_mode="HTML"
        )

async def on_startup(app):
    global backup_task
    await restore_from_channel(app.bot)
    await rebuild_vote_messages(app)
    backup_task = asyncio.create_task(auto_backup_loop(app))
    logger.info(f"Auto backup ON: har {AUTO_BACKUP_MINUTES} min -> {BACKUP_CHANNEL_ID}")

# ================= RENDER HEALTH SERVER ================= #
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    return server

# ================= MAIN ================= #
def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .job_queue(None)
        .build()
    )

    app.post_init = on_startup

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("db", db_command))
    app.add_handler(CommandHandler("autobackup", autobackup_command))
    app.add_handler(CommandHandler("restore", restore_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("testnotify", testnotify_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("add", add_votes_silent))
    app.add_handler(CommandHandler("admin", admin_command))

    # Security
    app.add_handler(CommandHandler("addwords", addwords_command))
    app.add_handler(CommandHandler("removewords", removewords_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("banlist", banlist_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("unwarn", unwarn_command))
    app.add_handler(CommandHandler("userinfo", userinfo_command))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("=" * 60)
    print("🤖 BOT ACTIVE!")
    print(f"📌 @{BOT_USERNAME}")
    print(f"👑 Owner: {OWNER_ID}")
    print(f"💾 Auto backup: har {AUTO_BACKUP_MINUTES} min -> {BACKUP_CHANNEL_ID}")
    print(f"🛡️ Security: word ban + manual ban + warn system ACTIVE")
    print("=" * 60)

    # Render Web Service requires an HTTP listener on 0.0.0.0:$PORT.
    # The Telegram bot continues using polling in the same process.
    health_server = start_health_server()
    try:
        app.bot.delete_webhook(drop_pending_updates=False)
        app.run_polling(allowed_updates=["message", "callback_query", "chat_member"])
    finally:
        health_server.shutdown()

if __name__ == "__main__":
    main()
