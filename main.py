import os
import re
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

ADMINS = [int(id.strip()) for id in os.getenv("ADMINS", "").split(",") if id.strip()]
if not ADMINS:
    raise ValueError("ADMINS environment variable is not set properly")

DATABASE_NAME = os.getenv("DATABASE_NAME", "bot_data.db")
MAX_WARNINGS = int(os.getenv("MAX_WARNINGS", 3))

# Database class
class BotDatabase:
    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Banned users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Custom commands table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_commands (
                command TEXT PRIMARY KEY,
                response TEXT
            )
        """)

        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # User warnings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_warnings (
                user_id INTEGER,
                chat_id INTEGER,
                warnings INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        """)

        conn.commit()
        conn.close()

    def is_user_banned(self, user_id: int) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking banned user: {e}")
            return False

    def add_banned_user(self, user_id: int, username: str = "", first_name: str = ""):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO banned_users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username or "", first_name or ""),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error adding banned user: {e}")
            return False

    def remove_banned_user(self, user_id: int) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error removing banned user: {e}")
            return False

    def get_banned_users(self) -> List[Tuple]:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, first_name, banned_at FROM banned_users")
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return []

    def add_custom_command(self, command: str, response: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO custom_commands (command, response) VALUES (?, ?)",
                (command.lower(), response),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error adding custom command: {e}")
            return False

    def get_custom_command(self, command: str) -> Optional[str]:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT response FROM custom_commands WHERE command = ?", (command.lower(),)
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting custom command: {e}")
            return None

    def get_all_commands(self) -> List[Tuple[str, str]]:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT command, response FROM custom_commands")
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting all commands: {e}")
            return []

    def delete_custom_command(self, command: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_commands WHERE command = ?", (command.lower(),))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error deleting custom command: {e}")
            return False

    def set_setting(self, key: str, value: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error setting setting: {e}")
            return False

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else default
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default

    def add_user_warning(self, user_id: int, chat_id: int) -> int:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_warnings (user_id, chat_id, warnings) 
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, chat_id) 
                DO UPDATE SET warnings = warnings + 1
                """,
                (user_id, chat_id),
            )
            conn.commit()

            cursor.execute(
                "SELECT warnings FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id),
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error adding user warning: {e}")
            return 0

    def reset_user_warnings(self, user_id: int, chat_id: int) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error resetting user warnings: {e}")
            return False

    def get_user_warnings(self, user_id: int, chat_id: int) -> int:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT warnings FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id),
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting user warnings: {e}")
            return 0


# Initialize database
db = BotDatabase()

# Helper functions
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def is_bot_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        bot_member = context.bot.get_chat_member(chat_id, context.bot.id)
        return bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f"Error checking bot admin status: {e}")
        return False

def extract_user_from_message(update: Update) -> Optional[Tuple[int, str, str]]:
    """Extract user from reply or mention"""
    # Check if replying to a message
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        return (user.id, user.username or "", user.first_name or "")

    # Check for username mention
    if update.message.text and "@" in update.message.text:
        # Simple mention extraction
        mention = re.search(r"@(\w+)", update.message.text)
        if mention:
            username = mention.group(1)
            # We can't get user ID from mention without API call
            return None

    return None

def extract_username_from_text(text: str) -> Optional[str]:
    """Extract username from text"""
    match = re.search(r"@(\w+)", text)
    return match.group(1) if match else None


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    try:
        keyboard = [
            [InlineKeyboardButton("➕ গ্রুপে এড করুন", url=f"https://t.me/{context.bot.username}?startgroup=true")],
            [InlineKeyboardButton("📖 সম্পূর্ণ গাইড", callback_data="guide")],
            [InlineKeyboardButton("👨‍💻 Developed by", url="https://t.me/md_alif_islam")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = """
🤖 **বটে স্বাগতম!**

এই বটের মাধ্যমে আপনি আপনার গ্রুপ ম্যানেজমেন্ট সহজ করতে পারবেন।

**মূল ফিচারসমূহ:**
• 🔗 লিংক অটো ডিলিট
• ⚙️ কাস্টম কমান্ড
• 🚫 ইউজার ব্যান/আনবান
• 📝 টেক্সট অন/অফ সিস্টেম
• ⚠️ ওয়ার্নিং সিস্টেম

গ্রুপে অ্যাড করে সম্পূর্ণ গাইড দেখুন!
        """

        await update.message.reply_text(
            welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")


async def guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle guide button callback"""
    try:
        query = update.callback_query
        await query.answer()

        guide_text = """
📖 **সম্পূর্ণ গাইড**

**সেটআপ করার নিয়ম:**

1. **বটকে গ্রুপে অ্যাড করুন** এডমিন হিসেবে
2. **নিম্নলিখিত কমান্ডগুলো ব্যবহার করুন:**

**🔹 এডমিন কমান্ডসমূহ:**
• `/welcome [text]` - ওয়েলকাম মেসেজ সেট করুন
• `/rules [text]` - রুলস মেসেজ সেট করুন  
• `/cmd [command] [response]` - কাস্টম কমান্ড অ্যাড করুন
• `/help [text]` - হেল্প মেসেজ সেট করুন
• `/ban @user` - ইউজার ব্যান করুন
• `/banlist` - ব্যানলিস্ট দেখুন
• `/unban @user` - ইউজার আনবান করুন
• `/text off [message]` - টেক্সট অফ মোড চালু করুন
• `/text on [message]` - টেক্সট অন মোড চালু করুন
• `/tw [message]` - ওয়ার্নিং মেসেজ সেট করুন

**🔹 লিংক ডিলিট:** কোনো লিংক পাঠালেই অটো ডিলিট হয়ে যাবে।

**🔹 কাস্টম কমান্ড:** `/cmd test Hello` সেট করলে কেউ `test` লিখলে বট `Hello` রিপ্লে দিবে।
        """

        await query.edit_message_text(guide_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in guide callback: {e}")
        await query.edit_message_text("❌ গাইড লোড করতে সমস্যা হয়েছে।")


async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set welcome message"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: `/welcome আপনার ওয়েলকাম মেসেজ`", parse_mode=ParseMode.MARKDOWN)
            return

        welcome_text = " ".join(context.args)
        if db.set_setting("welcome_message", welcome_text):
            await update.message.reply_text("✅ ওয়েলকাম মেসেজ সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ ওয়েলকাম মেসেজ সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in set_welcome: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set rules message"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: `/rules আপনার রুলস মেসেজ`", parse_mode=ParseMode.MARKDOWN)
            return

        rules_text = " ".join(context.args)
        if db.set_setting("rules_message", rules_text):
            await update.message.reply_text("✅ রুলস মেসেজ সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ রুলস মেসেজ সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in set_rules: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def set_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set help message"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: `/help আপনার হেল্প মেসেজ`", parse_mode=ParseMode.MARKDOWN)
            return

        help_text = " ".join(context.args)
        if db.set_setting("help_message", help_text):
            await update.message.reply_text("✅ হেল্প মেসেজ সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ হেল্প মেসেজ সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in set_help: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def set_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add or update a custom command"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if len(context.args) < 2:
            await update.message.reply_text("❌ ব্যবহার: `/cmd command_name response_text`", parse_mode=ParseMode.MARKDOWN)
            return

        command = context.args[0].lower()
        response = " ".join(context.args[1:])

        if db.add_custom_command(command, response):
            await update.message.reply_text(f"✅ কমান্ড `{command}` সেট করা হয়েছে!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ কমান্ড সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in set_custom_command: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user from the bot"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        # Check if replying to a message
        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
            if user.id == context.bot.id:
                await update.message.reply_text("❌ বটকে ব্যান করা যাবে না!")
                return
            if is_admin(user.id):
                await update.message.reply_text("❌ এডমিনকে ব্যান করা যাবে না!")
                return

            if db.add_banned_user(user.id, user.username or "", user.first_name or ""):
                await update.message.reply_text(f"✅ {user.first_name} কে ব্যান করা হয়েছে!")
            else:
                await update.message.reply_text("❌ ব্যান করতে সমস্যা হয়েছে।")
            return

        # Check for username mention
        if context.args:
            username = context.args[0]
            if username.startswith("@"):
                username = username[1:]
            await update.message.reply_text("❌ ইউজারনেম দিয়ে ব্যান সাপোর্টেড নয়। রিপ্লে দিয়ে ব্যান করুন।")
            return

        await update.message.reply_text("❌ ব্যবহার: রিপ্লে দিয়ে `/ban` অথবা `/ban @username`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in ban_user: {e}")
        await update.message.reply_text("❌ ব্যান করতে সমস্যা হয়েছে।")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        # Check if replying to a message
        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
            if db.remove_banned_user(user.id):
                await update.message.reply_text(f"✅ {user.first_name} কে আনবান করা হয়েছে!")
            else:
                await update.message.reply_text("❌ আনবান করতে সমস্যা হয়েছে।")
            return

        # Check for username mention
        if context.args:
            username = context.args[0]
            if username.startswith("@"):
                username = username[1:]
            await update.message.reply_text("❌ ইউজারনেম দিয়ে আনবান সাপোর্টেড নয়। রিপ্লে দিয়ে আনবান করুন।")
            return

        await update.message.reply_text("❌ ব্যবহার: রিপ্লে দিয়ে `/unban`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in unban_user: {e}")
        await update.message.reply_text("❌ আনবান করতে সমস্যা হয়েছে।")


async def ban_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of banned users"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        banned_users = db.get_banned_users()
        if not banned_users:
            await update.message.reply_text("📝 ব্যানলিস্ট খালি")
            return

        ban_text = "📋 **ব্যানলিস্ট:**\n\n"
        for user_id, username, first_name, banned_at in banned_users:
            name = first_name or "Unknown"
            user_tag = f"@{username}" if username else f"ID: {user_id}"
            ban_text += f"• {name} {user_tag}\n"

        await update.message.reply_text(ban_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in ban_list: {e}")
        await update.message.reply_text("❌ ব্যানলিস্ট লোড করতে সমস্যা হয়েছে।")


async def text_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn text off mode on"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            message = db.get_setting("text_off_message", "❌ টেক্সট অফ মোড চালু আছে!")
            await update.message.reply_text(message)
            return

        message = " ".join(context.args)
        if db.set_setting("text_off_message", message) and db.set_setting("text_mode", "off"):
            await update.message.reply_text("✅ টেক্সট অফ মোড সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ টেক্সট অফ মোড সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in text_off: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def text_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn text off mode off"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            message = db.get_setting("text_on_message", "✅ টেক্সট অন মোড চালু আছে!")
            await update.message.reply_text(message)
            return

        message = " ".join(context.args)
        if db.set_setting("text_on_message", message) and db.set_setting("text_mode", "on"):
            await update.message.reply_text("✅ টেক্সট অন মোড সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ টেক্সট অন মোড সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in text_on: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def set_warning_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set warning message"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: `/tw আপনার ওয়ার্নিং মেসেজ`", parse_mode=ParseMode.MARKDOWN)
            return

        warning_text = " ".join(context.args)
        if db.set_setting("warning_message", warning_text):
            await update.message.reply_text("✅ ওয়ার্নিং মেসেজ সেট করা হয়েছে!")
        else:
            await update.message.reply_text("❌ ওয়ার্নিং মেসেজ সেট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in set_warning_message: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে。")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a custom command"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: `/delcmd command_name`", parse_mode=ParseMode.MARKDOWN)
            return

        command = context.args[0].lower()
        if db.delete_custom_command(command):
            await update.message.reply_text(f"✅ কমান্ড `{command}` ডিলিট করা হয়েছে!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ কমান্ড ডিলিট করতে সমস্যা হয়েছে।")
    except Exception as e:
        logger.error(f"Error in delete_command: {e}")
        await update.message.reply_text("❌ কিছু সমস্যা হয়েছে।")


async def list_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all custom commands"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ আপনি এডমিন নন!")
            return

        commands = db.get_all_commands()
        if not commands:
            await update.message.reply_text("📝 কোনো কাস্টম কমান্ড নেই")
            return

        cmd_text = "📋 **কাস্টম কমান্ডসমূহ:**\n\n"
        for cmd, response in commands:
            cmd_text += f"• `{cmd}` → {response}\n"

        await update.message.reply_text(cmd_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in list_commands: {e}")
        await update.message.reply_text("❌ কমান্ড লিস্ট লোড করতে সমস্যা হয়েছে।")


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining"""
    try:
        welcome_message = db.get_setting("welcome_message")
        if not welcome_message:
            return

        for member in update.message.new_chat_members:
            # Check if it's the bot
            if member.id == context.bot.id:
                keyboard = [[InlineKeyboardButton("📖 সম্পূর্ণ গাইড", callback_data="guide")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    "🤖 গ্রুপে অ্যাড করার জন্য ধন্যবাদ!\nসম্পূর্ণ গাইড দেখতে নিচের বাটনে ক্লিক করুন:",
                    reply_markup=reply_markup,
                )
                return

            # Welcome new member
            mention = member.mention_html()
            welcome_text = welcome_message.replace("{mention}", mention)
            await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in handle_new_member: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    try:
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_text = update.message.text

        # Check if user is banned
        if db.is_user_banned(user_id):
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"Error deleting banned user's message: {e}")
            return

        # Check for links (improved regex)
        link_pattern = r"https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+"
        if re.search(link_pattern, message_text, re.IGNORECASE):
            try:
                await update.message.delete()
                # Notify user about link deletion
                await update.message.reply_text("🔗 লিংক পাঠানো নিষিদ্ধ!")
            except Exception as e:
                logger.error(f"Error deleting link message: {e}")
            return

        # Check text mode
        text_mode = db.get_setting("text_mode", "on")
        if text_mode == "off" and not is_admin(user_id):
            warning_message = db.get_setting(
                "text_off_message", "❌ টেক্সট অফ মোড চালু আছে!"
            )

            try:
                await update.message.delete()
                await update.message.reply_text(warning_message)
            except Exception as e:
                logger.error(f"Error handling text_off mode: {e}")

            # Add warning
            warnings = db.add_user_warning(user_id, chat_id)
            if warnings >= MAX_WARNINGS:
                if db.add_banned_user(
                    user_id,
                    update.effective_user.username or "",
                    update.effective_user.first_name or "",
                ):
                    await update.message.reply_text(
                        f"❌ {update.effective_user.first_name} কে {MAX_WARNINGS}টি ওয়ার্নিং এর জন্য ব্যান করা হয়েছে!"
                    )
            return

        # Check for custom commands
        command_response = db.get_custom_command(message_text.lower())
        if command_response:
            await update.message.reply_text(command_response)
            return

        # Handle rules command
        if message_text.lower() == "/rules":
            rules = db.get_setting("rules_message")
            if rules:
                await update.message.reply_text(rules)
            return

        # Handle help command
        if message_text.lower() == "/help":
            help_text = db.get_setting("help_message")
            if help_text:
                await update.message.reply_text(help_text)
            return

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")


def main():
    """Start the bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()

        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("welcome", set_welcome))
        application.add_handler(CommandHandler("rules", set_rules))
        application.add_handler(CommandHandler("help", set_help))
        application.add_handler(CommandHandler("cmd", set_custom_command))
        application.add_handler(CommandHandler("delcmd", delete_command))
        application.add_handler(CommandHandler("listcmd", list_commands))
        application.add_handler(CommandHandler("ban", ban_user))
        application.add_handler(CommandHandler("unban", unban_user))
        application.add_handler(CommandHandler("banlist", ban_list))
        application.add_handler(CommandHandler("text", text_off))
        application.add_handler(CommandHandler("texton", text_on))
        application.add_handler(CommandHandler("tw", set_warning_message))

        # Callback query handler
        application.add_handler(CallbackQueryHandler(guide_callback, pattern="^guide$"))

        # Message handlers
        application.add_handler(
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member)
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Start the bot
        logger.info("🤖 Bot is starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        raise


if __name__ == "__main__":
    main()
