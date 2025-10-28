"""
Yagami Bot Manager - GitHub Repository Deployment System
Deploy Telegram bots from GitHub repositories directly through Telegram
Admin-only bot for VPS deployment management
"""

import os
import json
import asyncio
import subprocess
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Configuration
CONFIG_FILE = 'bots_config.json'
BOTS_DIR = 'deployed_bots'
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

class BotManager:
    def __init__(self):
        self.bots = {}
        self.load_config()
        os.makedirs(BOTS_DIR, exist_ok=True)
        
    def load_config(self):
        """Load bot configurations from file"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.bots = json.load(f)
        else:
            self.bots = {}
            
    def save_config(self):
        """Save bot configurations to file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.bots, f, indent=4)
    
    def clone_repository(self, repo_url, bot_name):
        """Clone GitHub repository"""
        bot_path = os.path.join(BOTS_DIR, bot_name)
        
        # Remove existing directory if exists
        if os.path.exists(bot_path):
            shutil.rmtree(bot_path)
        
        try:
            # Clone the repository
            result = subprocess.run(
                ['git', 'clone', repo_url, bot_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return True, "Repository cloned successfully"
            else:
                return False, f"Clone failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Clone timeout (120s)"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def install_requirements(self, bot_name):
        """Install bot requirements"""
        bot_path = os.path.join(BOTS_DIR, bot_name)
        requirements_file = os.path.join(bot_path, 'requirements.txt')
        
        if not os.path.exists(requirements_file):
            return True, "No requirements.txt found, skipping..."
        
        try:
            result = subprocess.run(
                ['pip3', 'install', '-r', requirements_file],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return True, "Requirements installed successfully"
            else:
                return False, f"Installation failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Installation timeout (300s)"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def add_bot(self, bot_name, repo_url, bot_token, main_file='main.py'):
        """Add a new bot from GitHub"""
        self.bots[bot_name] = {
            'repo_url': repo_url,
            'token': bot_token,
            'main_file': main_file,
            'status': 'stopped',
            'pid': None,
            'added_at': datetime.now().isoformat(),
            'last_deployed': None
        }
        self.save_config()
        
    def remove_bot(self, bot_name):
        """Remove a bot"""
        if bot_name in self.bots:
            self.stop_bot(bot_name)
            
            # Remove bot directory
            bot_path = os.path.join(BOTS_DIR, bot_name)
            if os.path.exists(bot_path):
                shutil.rmtree(bot_path)
            
            del self.bots[bot_name]
            self.save_config()
            return True
        return False
    
    def start_bot(self, bot_name):
        """Start a bot process"""
        if bot_name not in self.bots:
            return False, "Bot not found"
        
        bot_path = os.path.join(BOTS_DIR, bot_name)
        main_file = self.bots[bot_name].get('main_file', 'main.py')
        bot_file = os.path.join(bot_path, main_file)
        
        if not os.path.exists(bot_file):
            return False, f"Main file not found: {main_file}"
        
        # Check if already running
        if self.bots[bot_name]['status'] == 'running':
            return False, "Bot already running"
        
        try:
            # Start bot process
            process = subprocess.Popen(
                ['python3', bot_file],
                cwd=bot_path,
                env={**os.environ, 'BOT_TOKEN': self.bots[bot_name]['token']},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.bots[bot_name]['status'] = 'running'
            self.bots[bot_name]['pid'] = process.pid
            self.save_config()
            return True, f"Bot started (PID: {process.pid})"
        except Exception as e:
            return False, f"Failed to start: {str(e)}"
    
    def stop_bot(self, bot_name):
        """Stop a bot process"""
        if bot_name not in self.bots:
            return False, "Bot not found"
        
        pid = self.bots[bot_name].get('pid')
        if pid:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass  # Process already dead
            except Exception as e:
                return False, f"Error stopping bot: {str(e)}"
        
        self.bots[bot_name]['status'] = 'stopped'
        self.bots[bot_name]['pid'] = None
        self.save_config()
        return True, "Bot stopped"
    
    def restart_bot(self, bot_name):
        """Restart a bot"""
        success, msg = self.stop_bot(bot_name)
        if success:
            return self.start_bot(bot_name)
        return False, msg
    
    def update_bot(self, bot_name):
        """Update bot from GitHub (pull latest changes)"""
        if bot_name not in self.bots:
            return False, "Bot not found"
        
        bot_path = os.path.join(BOTS_DIR, bot_name)
        
        if not os.path.exists(bot_path):
            return False, "Bot directory not found"
        
        try:
            # Pull latest changes
            result = subprocess.run(
                ['git', 'pull'],
                cwd=bot_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Reinstall requirements
                self.install_requirements(bot_name)
                return True, "Bot updated successfully"
            else:
                return False, f"Update failed: {result.stderr}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def get_stats(self):
        """Get deployment statistics"""
        total = len(self.bots)
        running = sum(1 for b in self.bots.values() if b['status'] == 'running')
        stopped = total - running
        
        return {
            'total': total,
            'running': running,
            'stopped': stopped,
            'error': 0
        }
    
    def get_bot_logs(self, bot_name, lines=20):
        """Get bot logs"""
        bot_path = os.path.join(BOTS_DIR, bot_name)
        log_file = os.path.join(bot_path, 'bot.log')
        
        if not os.path.exists(log_file):
            return "No logs found"
        
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading logs: {str(e)}"

# Initialize bot manager
bot_manager = BotManager()

def is_admin(user_id):
    """Check if user is admin"""
    if not ADMIN_IDS:
        return True  # If no admin IDs set, allow all
    return user_id in ADMIN_IDS

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Decorator to restrict commands to admins"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access denied. Admin only.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not await admin_only(update, context):
        return
    
    await update.message.reply_text(
        "🤖 <b>Yagami Bot Manager</b>\n\n"
        "Deploy and manage Telegram bots from GitHub repositories\n\n"
        "<b>Commands:</b>\n"
        "/deploy - Deploy a new bot from GitHub\n"
        "/bots - View all deployed bots\n"
        "/help - Show help message\n\n"
        "Admin only access ✅",
        parse_mode='HTML'
    )

async def show_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deployed bots with management interface"""
    query = update.callback_query
    if query:
        await query.answer()
        message = query.message
        user_id = query.from_user.id
    else:
        message = update.message
        user_id = update.effective_user.id
    
    if not is_admin(user_id):
        if query:
            await query.answer("⛔ Access denied", show_alert=True)
        else:
            await message.reply_text("⛔ Access denied. Admin only.")
        return
    
    stats = bot_manager.get_stats()
    
    # Build bot list text
    text = "🔍 <b>DEPLOYED BOTS INFO</b>\n\n"
    text += f"🤖 {stats['total']} | 🟢 {stats['running']} | 🔴 {stats['stopped']} | 🟠 {stats['error']} |\n\n"
    
    if not bot_manager.bots:
        text += "No bots deployed yet.\n"
        text += "Use /deploy to deploy your first bot from GitHub!"
    else:
        for idx, (bot_name, info) in enumerate(bot_manager.bots.items(), 1):
            status_emoji = "🟢" if info['status'] == 'running' else "🔴"
            status_text = info['status'].upper()
            text += f"🤖 {idx}. <b>{bot_name}</b>\n"
            text += f"{status_emoji} <b>{status_text}</b>\n"
            text += f"📦 Repo: <code>{info['repo_url']}</code>\n\n"
    
    text += "\n<b>CLICK BELOW BUTTONS TO CHANGE SETTINGS</b>"
    
    # Build keyboard
    keyboard = []
    
    # Bot selection buttons (3 per row)
    bot_buttons = []
    for idx, bot_name in enumerate(bot_manager.bots.keys(), 1):
        status = bot_manager.bots[bot_name]['status']
        emoji = "🟢" if status == 'running' else "🔴"
        bot_buttons.append(InlineKeyboardButton(
            f"{emoji}🤖 {idx}",
            callback_data=f"select_{bot_name}"
        ))
    
    # Add bot buttons in rows of 3
    for i in range(0, len(bot_buttons), 3):
        keyboard.append(bot_buttons[i:i+3])
    
    # Control buttons
    keyboard.append([
        InlineKeyboardButton("❌ STOP ALL", callback_data="stop_all"),
        InlineKeyboardButton("🗑️ REMOVE ALL", callback_data="remove_all")
    ])
    
    keyboard.append([
        InlineKeyboardButton("➕ ADD NEW BOTS", callback_data="add_new")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
        InlineKeyboardButton("❌ CLOSE", callback_data="close")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await message.edit_text(text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def show_bot_settings(query, bot_name):
    """Show individual bot settings"""
    if bot_name not in vps_manager.bots:
        await query.answer("Bot not found!", show_alert=True)
        return
    
    info = vps_manager.bots[bot_name]
    
    text = f"🤖 <b>{bot_name}</b>\n\n"
    text += f"📦 Repo: <code>{info['repo_url']}</code>\n"
    text += f"🔧 Type: <b>{info['type'].upper()}</b>\n"
    text += f"📄 Main: <code>{info['main_file']}</code>\n"
    text += f"Status: <b>{info['status'].upper()}</b>\n"
    if info.get('pid'):
        text += f"PID: <code>{info['pid']}</code>\n"
    text += f"\n📍 Path: <code>{os.path.join(BOTS_DIR, bot_name)}</code>"
    
    keyboard = []
    
    if info['status'] == 'running':
        keyboard.append([
            InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{bot_name}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{bot_name}")
        ])
    else:
        keyboard.append([InlineKeyboardButton("▶️ Start", callback_data=f"start_{bot_name}")])
    
    keyboard.append([
        InlineKeyboardButton("⬆️ Update", callback_data=f"update_{bot_name}"),
        InlineKeyboardButton("📋 Logs", callback_data=f"logs_{bot_name}")
    ])
    keyboard.append([
        InlineKeyboardButton("🗑️ Remove", callback_data=f"rm_{bot_name}"),
        InlineKeyboardButton("🔙 Back", callback_data="refresh")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def execute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute shell command on VPS"""
    if not is_admin(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "<b>Execute Command on VPS</b>\n\n"
            "<code>/cmd your_command</code>\n\n"
            "<b>Examples:</b>\n"
            "<code>/cmd ls -la</code>\n"
            "<code>/cmd df -h</code>\n"
            "<code>/cmd free -h</code>\n"
            "<code>/cmd ps aux | grep python</code>\n\n"
            "⚠️ Use with caution!",
            parse_mode='HTML'
        )
        return
    
    command = ' '.join(context.args)
    
    msg = await update.message.reply_text(f"⚙️ Executing: <code>{command}</code>", parse_mode='HTML')
    
    success, output = vps_manager.execute_command(command)
    
    if len(output) > 4000:
        output = output[:4000] + "\n... (output truncated)"
    
    result_text = f"<b>Command:</b> <code>{command}</code>\n\n"
    result_text += f"<b>Output:</b>\n<code>{output}</code>"
    
    await msg.edit_text(result_text, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    data = query.data
    
    if data == "refresh":
        await show_bots(update, context)
        await query.answer("Refreshed!")
    
    elif data == "close":
        await query.message.delete()
        await query.answer()
    
    elif data == "stopall":
        count = 0
        for name in vps_manager.bots.keys():
            if vps_manager.stop_bot(name)[0]:
                count += 1
        await query.answer(f"Stopped {count} bot(s)!", show_alert=True)
        await show_bots(update, context)
    
    elif data == "rmall":
        count = len(vps_manager.bots)
        for name in list(vps_manager.bots.keys()):
            vps_manager.remove_bot(name)
        await query.answer(f"Removed {count} bot(s)!", show_alert=True)
        await show_bots(update, context)
    
    elif data == "addnew":
        await query.answer()
        await query.message.reply_text("/deploy name repo_url bot_token")
    
    elif data == "vpsinfo":
        await query.answer("Refreshing...")
        await vps_info(update, context)
    
    elif data.startswith("sel_"):
        await query.answer()
        await show_bot_settings(query, data[4:])
    
    elif data.startswith("start_"):
        name = data[6:]
        await query.answer("Starting...", show_alert=False)
        success, msg = vps_manager.start_bot(name)
        await query.answer(msg, show_alert=True)
        await show_bot_settings(query, name)
    
    elif data.startswith("stop_"):
        name = data[5:]
        await query.answer("Stopping...", show_alert=False)
        success, msg = vps_manager.stop_bot(name)
        await query.answer(msg, show_alert=True)
        await show_bot_settings(query, name)
    
    elif data.startswith("restart_"):
        name = data[8:]
        await query.answer("Restarting...", show_alert=False)
        success, msg = vps_manager.restart_bot(name)
        await query.answer(msg, show_alert=True)
        await show_bot_settings(query, name)
    
    elif data.startswith("update_"):
        name = data[7:]
        await query.answer("Updating from GitHub...", show_alert=False)
        success, msg = vps_manager.update_bot(name)
        await query.answer(msg, show_alert=True)
        await show_bot_settings(query, name)
    
    elif data.startswith("logs_"):
        name = data[5:]
        await query.answer()
        logs = vps_manager.get_logs(name)
        if len(logs) > 4000:
            logs = logs[-4000:]
        await query.message.reply_text(
            f"📋 <b>Logs: {name}</b>\n\n<code>{logs}</code>",
            parse_mode='HTML'
        )
    
    elif data.startswith("rm_"):
        name = data[3:]
        vps_manager.remove_bot(name)
        await query.answer("Bot removed!", show_alert=True)
        await show_bots(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    if not is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text(
        "🤖 <b>Yagami VPS Manager - Help</b>\n\n"
        "<b>Control your VPS remotely!</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Start & VPS status\n"
        "/vps - Detailed VPS info\n"
        "/deploy name repo token - Deploy bot\n"
        "/bots - Manage all bots\n"
        "/cmd command - Execute shell command\n"
        "/help - This help\n\n"
        "<b>Supported Bot Types:</b>\n"
        "✅ Python\n"
        "✅ Node.js\n"
        "✅ Docker\n"
        "✅ Golang\n"
        "✅ Shell scripts\n\n"
        "<b>Features:</b>\n"
        "• Deploy from any GitHub repo\n"
        "• Auto-detect bot type\n"
        "• Auto-install dependencies\n"
        "• Start/Stop/Restart bots\n"
        "• Update from GitHub\n"
        "• View logs\n"
        "• Execute VPS commands\n"
        "• Monitor VPS resources\n\n"
        "<b>Admin Only Access 🔒</b>",
        parse_mode='HTML'
    )

def main():
    """Start the VPS manager bot"""
    # Create directories
    os.makedirs(BOTS_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Get bot token
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("❌ BOT_TOKEN not set!")
        return
    
    # Check admin IDs
    if not ADMIN_IDS:
        print("⚠️  WARNING: No ADMIN_IDS set!")
        print("   Anyone can control your VPS!")
        print("   Set ADMIN_IDS in .env for security!")
    else:
        print(f"✅ Admin IDs: {ADMIN_IDS}")
    
    # Create application
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("vps", vps_info))
    app.add_handler(CommandHandler("deploy", deploy_command))
    app.add_handler(CommandHandler("bots", show_bots))
    app.add_handler(CommandHandler("cmd", execute_cmd))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Print startup info
    print("=" * 60)
    print("🤖 Yagami VPS Manager")
    print("=" * 60)
    print("Control your VPS remotely through Telegram!")
    print("")
    print("✅ Python bots")
    print("✅ Node.js bots")
    print("✅ Docker containers")
    print("✅ Golang bots")
    print("✅ Shell scripts")
    print("")
    print(f"📁 Bots directory: {BOTS_DIR}")
    print(f"💾 Config file: {CONFIG_FILE}")
    print("=" * 60)
    print("🚀 Bot Manager Started!")
    print("=" * 60)
    
    # Start polling
    app.run_polling()

if __name__ == '__main__':
    main()

async def deploy_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deploy a new bot from GitHub"""
    if not await admin_only(update, context):
        return
    
    await update.message.reply_text(
        "📦 <b>Deploy Bot from GitHub</b>\n\n"
        "Send me the deployment details in this format:\n\n"
        "<code>/deploy bot_name github_url bot_token main_file</code>\n\n"
        "<b>Example:</b>\n"
        "<code>/deploy myfilebot https://github.com/user/repo 123456:ABC-DEF main.py</code>\n\n"
        "<b>Parameters:</b>\n"
        "• <b>bot_name</b>: Name for your bot (no spaces)\n"
        "• <b>github_url</b>: GitHub repository URL\n"
        "• <b>bot_token</b>: Bot token from @BotFather\n"
        "• <b>main_file</b>: Main Python file (default: main.py)\n\n"
        "Note: main_file is optional, defaults to main.py",
        parse_mode='HTML'
    )

async def deploy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deploy command with parameters"""
    if not await admin_only(update, context):
        return
    
    if len(context.args) < 3:
        await deploy_bot(update, context)
        return
    
    bot_name = context.args[0]
    repo_url = context.args[1]
    bot_token = context.args[2]
    main_file = context.args[3] if len(context.args) > 3 else 'main.py'
    
    # Validate inputs
    if ' ' in bot_name:
        await update.message.reply_text("❌ Bot name cannot contain spaces")
        return
    
    if not repo_url.startswith('http'):
        await update.message.reply_text("❌ Invalid GitHub URL")
        return
    
    msg = await update.message.reply_text(
        f"🚀 <b>Deploying {bot_name}...</b>\n\n"
        f"📦 Cloning repository...",
        parse_mode='HTML'
    )
    
    # Clone repository
    success, message = bot_manager.clone_repository(repo_url, bot_name)
    
    if not success:
        await msg.edit_text(
            f"❌ <b>Deployment Failed</b>\n\n"
            f"Error: {message}",
            parse_mode='HTML'
        )
        return
    
    await msg.edit_text(
        f"🚀 <b>Deploying {bot_name}...</b>\n\n"
        f"✅ Repository cloned\n"
        f"📦 Installing requirements...",
        parse_mode='HTML'
    )
    
    # Install requirements
    success, message = bot_manager.install_requirements(bot_name)
    
    if not success:
        await msg.edit_text(
            f"⚠️ <b>Partial Deployment</b>\n\n"
            f"Repository cloned but requirements failed:\n{message}\n\n"
            f"You may need to install them manually.",
            parse_mode='HTML'
        )
    else:
        await msg.edit_text(
            f"🚀 <b>Deploying {bot_name}...</b>\n\n"
            f"✅ Repository cloned\n"
            f"✅ Requirements installed\n"
            f"💾 Saving configuration...",
            parse_mode='HTML'
        )
    
    # Add bot to configuration
    bot_manager.add_bot(bot_name, repo_url, bot_token, main_file)
    bot_manager.bots[bot_name]['last_deployed'] = datetime.now().isoformat()
    bot_manager.save_config()
    
    await msg.edit_text(
        f"✅ <b>Deployment Successful!</b>\n\n"
        f"Bot: <b>{bot_name}</b>\n"
        f"Repository: <code>{repo_url}</code>\n"
        f"Status: <b>Stopped</b>\n\n"
        f"Use /bots to start the bot!",
        parse_mode='HTML'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    data = query.data
    
    if data == "refresh":
        await show_bots(update, context)
        
    elif data == "close":
        await query.message.delete()
        
    elif data == "stop_all":
        count = 0
        for bot_name in bot_manager.bots.keys():
            success, _ = bot_manager.stop_bot(bot_name)
            if success:
                count += 1
        await query.answer(f"Stopped {count} bot(s)!", show_alert=True)
        await show_bots(update, context)
        
    elif data == "remove_all":
        count = len(bot_manager.bots)
        for bot_name in list(bot_manager.bots.keys()):
            bot_manager.remove_bot(bot_name)
        await query.answer(f"Removed {count} bot(s)!", show_alert=True)
        await show_bots(update, context)
        
    elif data == "add_new":
        await query.message.reply_text(
            "To deploy a new bot:\n"
            "/deploy bot_name github_url bot_token [main_file]"
        )
        
    elif data.startswith("select_"):
        bot_name = data.replace("select_", "")
        await show_bot_settings(query, bot_name)
    
    elif data.startswith("start_"):
        bot_name = data.replace("start_", "")
        success, message = bot_manager.start_bot(bot_name)
        await query.answer(message, show_alert=True)
        await show_bot_settings(query, bot_name)
    
    elif data.startswith("stop_"):
        bot_name = data.replace("stop_", "")
        success, message = bot_manager.stop_bot(bot_name)
        await query.answer(message, show_alert=True)
        await show_bot_settings(query, bot_name)
    
    elif data.startswith("restart_"):
        bot_name = data.replace("restart_", "")
        success, message = bot_manager.restart_bot(bot_name)
        await query.answer(message, show_alert=True)
        await show_bot_settings(query, bot_name)
    
    elif data.startswith("update_"):
        bot_name = data.replace("update_", "")
        await query.answer("Updating bot...", show_alert=False)
        success, message = bot_manager.update_bot(bot_name)
        await query.answer(message, show_alert=True)
        await show_bot_settings(query, bot_name)
    
    elif data.startswith("remove_"):
        bot_name = data.replace("remove_", "")
        success = bot_manager.remove_bot(bot_name)
        if success:
            await query.answer("Bot removed!", show_alert=True)
            await show_bots(update, context)
        else:
            await query.answer("Failed to remove bot", show_alert=True)
    
    elif data.startswith("logs_"):
        bot_name = data.replace("logs_", "")
        logs = bot_manager.get_bot_logs(bot_name)
        await query.message.reply_text(
            f"📋 <b>Logs for {bot_name}</b>\n\n"
            f"<code>{logs}</code>",
            parse_mode='HTML'
        )

async def show_bot_settings(query, bot_name):
    """Show settings for a specific bot"""
    if bot_name not in bot_manager.bots:
        await query.answer("Bot not found!", show_alert=True)
        return
    
    bot_info = bot_manager.bots[bot_name]
    status = bot_info['status']
    
    text = f"🤖 <b>Bot: {bot_name}</b>\n\n"
    text += f"📦 Repository: <code>{bot_info['repo_url']}</code>\n"
    text += f"📄 Main File: <code>{bot_info['main_file']}</code>\n"
    text += f"Status: <b>{status.upper()}</b>\n"
    
    if bot_info.get('pid'):
        text += f"PID: <code>{bot_info['pid']}</code>\n"
    
    text += f"\n📅 Added: {bot_info.get('added_at', 'Unknown')[:10]}\n"
    
    if bot_info.get('last_deployed'):
        text += f"🔄 Last Deployed: {bot_info['last_deployed'][:10]}\n"
    
    keyboard = []
    
    if status == 'running':
        keyboard.append([
            InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{bot_name}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{bot_name}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("▶️ Start", callback_data=f"start_{bot_name}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬆️ Update from GitHub", callback_data=f"update_{bot_name}"),
        InlineKeyboardButton("📋 Logs", callback_data=f"logs_{bot_name}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Remove", callback_data=f"remove_{bot_name}"),
        InlineKeyboardButton("🔙 Back", callback_data="refresh")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    if not await admin_only(update, context):
        return
    
    help_text = """
🤖 <b>Yagami Bot Manager - Help</b>

<b>Deploy bots from GitHub repositories</b>

<b>Commands:</b>
/start - Start the manager
/deploy - Deploy a new bot from GitHub
/bots - View and manage all bots
/help - Show this help

<b>How to Deploy:</b>
1. Push your bot code to GitHub
2. Use /deploy with repo URL
3. Manager clones and sets up bot
4. Start bot from /bots panel

<b>Features:</b>
• Clone from any GitHub repository
• Auto-install requirements.txt
• Start/Stop/Restart bots
• Update bots from GitHub (git pull)
• View bot logs
• Remove bots completely

<b>Example Deployment:</b>
<code>/deploy mybot https://github.com/user/repo TOKEN123 main.py</code>

<b>Admin Only Access ✅</b>
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

def main():
    """Start the bot"""
    # Create directories
    os.makedirs(BOTS_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Get bot token
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("❌ Error: BOT_TOKEN environment variable not set")
        return
    
    # Check admin IDs
    if not ADMIN_IDS:
        print("⚠️  Warning: No ADMIN_IDS set. All users will have access!")
        print("   Set ADMIN_IDS in .env file for security")
    else:
        print(f"✅ Admin IDs configured: {ADMIN_IDS}")
    
    # Create application
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bots", show_bots))
    app.add_handler(CommandHandler("deploy", deploy_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    print("=" * 60)
    print("🤖 Yagami Bot Manager Started!")
    print("=" * 60)
    print("Deploy Telegram bots from GitHub repositories")
    print("Admin-only access enabled")
    print("=" * 60)
    app.run_polling()

if __name__ == '__main__':
    main()
