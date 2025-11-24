import logging
import sqlite3
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot Token (এখানে আপনার বট টোকেন দিন)
BOT_TOKEN = "8431791443:AAHubkEB6OacN4gK044S1joGtpfugxWftmY"

# Admin list (এখানে আপনার Admin এর User ID গুলো দিন)
ADMINS = [123456789, 987654321]  # Replace with actual admin user IDs

# Database setup
DB_NAME = "bot_data.db"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Banned users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Custom commands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_commands (
                command TEXT PRIMARY KEY,
                response TEXT
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # User warnings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_warnings (
                user_id INTEGER,
                chat_id INTEGER,
                warnings INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_banned_user(self, user_id: int, username: str, first_name: str):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO banned_users (user_id, username, first_name) VALUES (?, ?, ?)',
            (user_id, username, first_name)
        )
        self.conn.commit()
    
    def remove_banned_user(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def get_banned_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM banned_users')
        return cursor.fetchall()
    
    def is_user_banned(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM banned_users WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def add_custom_command(self, command: str, response: str):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO custom_commands (command, response) VALUES (?, ?)',
            (command, response)
        )
        self.conn.commit()
    
    def get_custom_command(self, command: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT response FROM custom_commands WHERE command = ?', (command,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_all_commands(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT command, response FROM custom_commands')
        return cursor.fetchall()
    
    def delete_custom_command(self, command: str):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM custom_commands WHERE command = ?', (command,))
        self.conn.commit()
    
    def set_setting(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        self.conn.commit()
    
    def get_setting(self, key: str, default=None):
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else default
    
    def add_user_warning(self, user_id: int, chat_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO user_warnings (user_id, chat_id, warnings) 
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, chat_id) 
            DO UPDATE SET warnings = warnings + 1
        ''', (user_id, chat_id))
        self.conn.commit()
        
        cursor.execute('SELECT warnings FROM user_warnings WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def reset_user_warnings(self, user_id: int, chat_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM user_warnings WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        self.conn.commit()
    
    def get_user_warnings(self, user_id: int, chat_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT warnings FROM user_warnings WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        result = cursor.fetchone()
        return result[0] if result else 0

# Initialize database
db = BotDatabase()

# Check if user is admin
def is_admin(user_id: int):
    return user_id in ADMINS

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("গ্রুপে এড করুন", url="https://t.me/your_bot_username?startgroup=true")],
        [InlineKeyboardButton("সম্পূর্ণ গাইড", callback_data="guide")],
        [InlineKeyboardButton("Developed by", url="https://t.me/md_alif_islam")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🤖 **বটে স্বাগতম!**

এই বটের মাধ্যমে আপনি আপনার গ্রুপ ম্যানেজমেন্ট সহজ করতে পারবেন।

**মূল ফিচারসমূহ:**
• লিংক অটো ডিলিট
• কাস্টম কমান্ড
• ইউজার ব্যান/আনবান
• টেক্সট অন/অফ সিস্টেম
• ওয়ার্নিং সিস্টেম

গ্রুপে অ্যাড করে সম্পূর্ণ গাইড দেখুন!
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# Guide callback
async def guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    guide_text = """
📖 **সম্পূর্ণ গাইড**

**সেটআপ করার নিয়ম:**

1. **বটকে গ্রুপে অ্যাড করুন** এডমিন হিসেবে
2. **নিম্নলিখিত কমান্ডগুলো সেটআপ করুন:**

**এডমিন কমান্ডসমূহ:**
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

**লিংক ডিলিট:** কোনো লিংক পাঠালেই অটো ডিলিট হয়ে যাবে।

**কাস্টম কমান্ড:** `/cmd test Hello` সেট করলে কেউ `test` লিখলে বট `Hello` রিপ্লে দিবে।
    """
    
    await query.edit_message_text(guide_text, parse_mode='Markdown')

# Welcome command
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ ব্যবহার: `/welcome আপনার ওয়েলকাম মেসেজ`", parse_mode='Markdown')
        return
    
    welcome_text = ' '.join(context.args)
    db.set_setting('welcome_message', welcome_text)
    await update.message.reply_text("✅ ওয়েলকাম মেসেজ সেট করা হয়েছে!")

# Rules command  
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ ব্যবহার: `/rules আপনার রুলস মেসেজ`", parse_mode='Markdown')
        return
    
    rules_text = ' '.join(context.args)
    db.set_setting('rules_message', rules_text)
    await update.message.reply_text("✅ রুলস মেসেজ সেট করা হয়েছে!")

# Help command
async def set_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ ব্যবহার: `/help আপনার হেল্প মেসেজ`", parse_mode='Markdown')
        return
    
    help_text = ' '.join(context.args)
    db.set_setting('help_message', help_text)
    await update.message.reply_text("✅ হেল্প মেসেজ সেট করা হয়েছে!")

# Custom command
async def set_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ ব্যবহার: `/cmd command_name response_text`", parse_mode='Markdown')
        return
    
    command = context.args[0].lower()
    response = ' '.join(context.args[1:])
    
    db.add_custom_command(command, response)
    await update.message.reply_text(f"✅ কমান্ড `{command}` সেট করা হয়েছে!")

# Ban command
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not update.message.reply_to_message and not context.args:
        await update.message.reply_text("❌ ব্যবহার: রিপ্লে দিয়ে `/ban` অথবা `/ban @username`")
        return
    
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        # Extract user from mention (simplified)
        await update.message.reply_text("❌ রিপ্লে দিয়ে ইউজার ব্যান করুন")
        return
    
    db.add_banned_user(user.id, user.username, user.first_name)
    await update.message.reply_text(f"✅ {user.first_name} ব্যান করা হয়েছে!")

# Unban command
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ ব্যবহার: `/unban @username`")
        return
    
    # Simplified unban logic
    await update.message.reply_text("❌ রিপ্লে দিয়ে আনবান সাপোর্টেড নয় এই ভার্সনে")

# Banlist command
async def ban_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    banned_users = db.get_banned_users()
    if not banned_users:
        await update.message.reply_text("📝 ব্যানলিস্ট খালি")
        return
    
    ban_text = "📋 **ব্যানলিস্ট:**\n"
    for user in banned_users:
        ban_text += f"• {user[2]} (@{user[1]})\n"
    
    await update.message.reply_text(ban_text)

# Text off command
async def text_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        # If already set, show the message
        message = db.get_setting('text_off_message', "❌ টেক্সট অফ মোড চালু আছে!")
        await update.message.reply_text(message)
        return
    
    message = ' '.join(context.args)
    db.set_setting('text_off_message', message)
    db.set_setting('text_mode', 'off')
    await update.message.reply_text("✅ টেক্সট অফ মোড সেট করা হয়েছে!")

# Text on command
async def text_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        # If already set, show the message
        message = db.get_setting('text_on_message', "✅ টেক্সট অন মোড চালু আছে!")
        await update.message.reply_text(message)
        return
    
    message = ' '.join(context.args)
    db.set_setting('text_on_message', message)
    db.set_setting('text_mode', 'on')
    await update.message.reply_text("✅ টেক্সট অন মোড সেট করা হয়েছে!")

# Set warning message
async def set_warning_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ ব্যবহার: `/tw আপনার ওয়ার্নিং মেসেজ`", parse_mode='Markdown')
        return
    
    warning_text = ' '.join(context.args)
    db.set_setting('warning_message', warning_text)
    await update.message.reply_text("✅ ওয়ার্নিং মেসেজ সেট করা হয়েছে!")

# Handle text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text
    
    # Check if user is banned
    if db.is_user_banned(user_id):
        await update.message.delete()
        return
    
    # Check for links and delete
    if any(link in message_text.lower() for link in ['http://', 'https://', 't.me/', 'www.']):
        await update.message.delete()
        return
    
    # Check text mode
    text_mode = db.get_setting('text_mode', 'on')
    if text_mode == 'off' and not is_admin(user_id):
        warning_message = db.get_setting('text_off_message', "❌ টেক্সট অফ মোড চালু আছে!")
        await update.message.reply_text(warning_message)
        
        # Add warning
        warnings = db.add_user_warning(user_id, chat_id)
        if warnings >= 3:
            db.add_banned_user(user_id, update.effective_user.username, update.effective_user.first_name)
            await update.message.reply_text(f"❌ {update.effective_user.first_name} কে ৩টি ওয়ার্নিং এর জন্য ব্যান করা হয়েছে!")
        return
    
    # Check for custom commands
    command_response = db.get_custom_command(message_text.lower())
    if command_response:
        await update.message.reply_text(command_response)
        return
    
    # Handle other commands if needed
    if message_text.startswith('/'):
        return

# Handle new chat members
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = db.get_setting('welcome_message')
    if welcome_message:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                # Bot added to group
                keyboard = [
                    [InlineKeyboardButton("সম্পূর্ণ গাইড", callback_data="guide")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🤖 গ্রুপে অ্যাড করার জন্য ধন্যবাদ!\nসম্পূর্ণ গাইড দেখতে নিচের বাটনে ক্লিক করুন:",
                    reply_markup=reply_markup
                )
            else:
                # New user joined
                mention = member.mention_html()
                welcome_text = welcome_message.replace('{mention}', mention)
                await update.message.reply_text(welcome_text, parse_mode='HTML')

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("welcome", set_welcome))
    application.add_handler(CommandHandler("rules", set_rules))
    application.add_handler(CommandHandler("help", set_help))
    application.add_handler(CommandHandler("cmd", set_custom_command))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("banlist", ban_list))
    application.add_handler(CommandHandler("text", text_off))
    application.add_handler(CommandHandler("texton", text_on))
    application.add_handler(CommandHandler("tw", set_warning_message))
    
    # Callback handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()