import os
import json
import subprocess
import docker
import psutil
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from datetime import datetime
import re
import threading

# Configuration
CONFIG_FILE = 'bots_config.json'
BOTS_DIR = 'hosted_bots'
LOGS_DIR = 'logs'
MAX_BOTS_PER_USER = 5

# Conversation states
WAITING_BOT_TOKEN, WAITING_BOT_NAME, WAITING_GITHUB_REPO = range(3)

class DockerBotHosting:
    def __init__(self):
        self.bots = self.load_config()
        os.makedirs(BOTS_DIR, exist_ok=True)
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            print("✅ Docker connected successfully")
        except Exception as e:
            print(f"❌ Docker connection failed: {e}")
            self.docker_client = None
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.bots, f, indent=2)
    
    def clone_repo(self, repo_url, bot_dir):
        """Clone GitHub repository"""
        try:
            if os.path.exists(bot_dir):
                shutil.rmtree(bot_dir)
            
            result = subprocess.run(
                ['git', 'clone', repo_url, bot_dir],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return result.returncode == 0, result.stderr if result.returncode != 0 else "Cloned"
        except Exception as e:
            return False, str(e)
    
    def detect_project_type(self, bot_dir):
        """Detect project language/framework"""
        if os.path.exists(os.path.join(bot_dir, 'package.json')):
            return 'nodejs'
        elif os.path.exists(os.path.join(bot_dir, 'requirements.txt')) or \
             os.path.exists(os.path.join(bot_dir, 'Pipfile')):
            return 'python'
        elif os.path.exists(os.path.join(bot_dir, 'go.mod')):
            return 'golang'
        elif os.path.exists(os.path.join(bot_dir, 'Gemfile')):
            return 'ruby'
        elif os.path.exists(os.path.join(bot_dir, 'composer.json')):
            return 'php'
        elif os.path.exists(os.path.join(bot_dir, 'Dockerfile')):
            return 'docker'
        else:
            return 'python'  # Default
    
    def create_dockerfile(self, bot_dir, project_type, token):
        """Create appropriate Dockerfile"""
        dockerfile_content = ""
        
        if project_type == 'nodejs':
            dockerfile_content = f"""FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ENV BOT_TOKEN={token}
CMD ["node", "index.js"]"""
        
        elif project_type == 'python':
            dockerfile_content = f"""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV BOT_TOKEN={token}
CMD ["python", "bot.py"]"""
        
        elif project_type == 'golang':
            dockerfile_content = f"""FROM golang:1.21-alpine
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
ENV BOT_TOKEN={token}
RUN go build -o main .
CMD ["./main"]"""
        
        elif project_type == 'ruby':
            dockerfile_content = f"""FROM ruby:3.2-alpine
WORKDIR /app
COPY Gemfile* ./
RUN bundle install
COPY . .
ENV BOT_TOKEN={token}
CMD ["ruby", "bot.rb"]"""
        
        elif project_type == 'php':
            dockerfile_content = f"""FROM php:8.2-cli
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install
COPY . .
ENV BOT_TOKEN={token}
CMD ["php", "bot.php"]"""
        
        # Write Dockerfile if not exists
        dockerfile_path = os.path.join(bot_dir, 'Dockerfile')
        if not os.path.exists(dockerfile_path):
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
        
        return dockerfile_path
    
    def build_docker_image(self, bot_dir, image_name):
        """Build Docker image"""
        try:
            if not self.docker_client:
                return False, "Docker not available"
            
            image, logs = self.docker_client.images.build(
                path=bot_dir,
                tag=image_name,
                rm=True,
                pull=True
            )
            return True, "Image built successfully"
        except Exception as e:
            return False, str(e)
    
    def add_bot(self, user_id, bot_name, token, repo_url):
        """Deploy bot from GitHub using Docker"""
        user_id = str(user_id)
        if user_id not in self.bots:
            self.bots[user_id] = {}
        
        # Check bot limit
        if len(self.bots[user_id]) >= MAX_BOTS_PER_USER:
            return False, f"Bot limit reached ({MAX_BOTS_PER_USER} bots max)"
        
        bot_dir = os.path.join(BOTS_DIR, f"{user_id}_{bot_name}")
        container_name = f"bot_{user_id}_{bot_name}"
        image_name = f"bot_image_{user_id}_{bot_name}".lower()
        
        # Clone repository
        success, msg = self.clone_repo(repo_url, bot_dir)
        if not success:
            return False, f"Clone failed: {msg}"
        
        # Detect project type
        project_type = self.detect_project_type(bot_dir)
        
        # Create Dockerfile
        self.create_dockerfile(bot_dir, project_type, token)
        
        # Build Docker image
        success, msg = self.build_docker_image(bot_dir, image_name)
        if not success:
            shutil.rmtree(bot_dir, ignore_errors=True)
            return False, f"Build failed: {msg}"
        
        # Save bot info
        self.bots[user_id][bot_name] = {
            'token': token,
            'repo_url': repo_url,
            'bot_dir': bot_dir,
            'container_name': container_name,
            'image_name': image_name,
            'project_type': project_type,
            'status': 'stopped',
            'added_at': datetime.now().isoformat()
        }
        self.save_config()
        
        return True, f"Bot deployed! Type: {project_type.upper()}"
    
    def start_bot(self, user_id, bot_name):
        """Start bot container"""
        user_id = str(user_id)
        if user_id not in self.bots or bot_name not in self.bots[user_id]:
            return False, "Bot not found"
        
        bot_info = self.bots[user_id][bot_name]
        
        try:
            if not self.docker_client:
                return False, "Docker not available"
            
            # Stop if already running
            try:
                container = self.docker_client.containers.get(bot_info['container_name'])
                container.stop()
                container.remove()
            except:
                pass
            
            # Start new container
            log_file = os.path.join(LOGS_DIR, f"{user_id}_{bot_name}.log")
            
            container = self.docker_client.containers.run(
                bot_info['image_name'],
                name=bot_info['container_name'],
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                environment={"BOT_TOKEN": bot_info['token']},
                network_mode="bridge",
                mem_limit="512m",
                cpu_quota=50000
            )
            
            self.bots[user_id][bot_name]['status'] = 'running'
            self.bots[user_id][bot_name]['container_id'] = container.id
            self.save_config()
            
            return True, "Bot started successfully"
        except Exception as e:
            return False, str(e)
    
    def stop_bot(self, user_id, bot_name):
        """Stop bot container"""
        user_id = str(user_id)
        if user_id not in self.bots or bot_name not in self.bots[user_id]:
            return False, "Bot not found"
        
        bot_info = self.bots[user_id][bot_name]
        
        try:
            if not self.docker_client:
                return False, "Docker not available"
            
            container = self.docker_client.containers.get(bot_info['container_name'])
            container.stop(timeout=10)
            container.remove()
            
            self.bots[user_id][bot_name]['status'] = 'stopped'
            self.save_config()
            
            return True, "Bot stopped"
        except Exception as e:
            self.bots[user_id][bot_name]['status'] = 'stopped'
            self.save_config()
            return True, "Bot stopped"
    
    def remove_bot(self, user_id, bot_name):
        """Remove bot completely"""
        user_id = str(user_id)
        if user_id not in self.bots or bot_name not in self.bots[user_id]:
            return False, "Bot not found"
        
        bot_info = self.bots[user_id][bot_name]
        
        # Stop container
        self.stop_bot(user_id, bot_name)
        
        # Remove Docker image
        try:
            if self.docker_client:
                self.docker_client.images.remove(bot_info['image_name'], force=True)
        except:
            pass
        
        # Remove files
        if os.path.exists(bot_info['bot_dir']):
            shutil.rmtree(bot_info['bot_dir'], ignore_errors=True)
        
        # Remove from config
        del self.bots[user_id][bot_name]
        self.save_config()
        
        return True, "Bot removed"
    
    def update_bot(self, user_id, bot_name):
        """Update bot from GitHub"""
        user_id = str(user_id)
        if user_id not in self.bots or bot_name not in self.bots[user_id]:
            return False, "Bot not found"
        
        bot_info = self.bots[user_id][bot_name]
        was_running = bot_info['status'] == 'running'
        
        # Stop bot
        if was_running:
            self.stop_bot(user_id, bot_name)
        
        # Pull latest changes
        try:
            result = subprocess.run(
                ['git', 'pull'],
                cwd=bot_info['bot_dir'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return False, "Git pull failed"
            
            # Rebuild image
            success, msg = self.build_docker_image(
                bot_info['bot_dir'],
                bot_info['image_name']
            )
            
            if not success:
                return False, f"Rebuild failed: {msg}"
            
            # Start if was running
            if was_running:
                self.start_bot(user_id, bot_name)
            
            return True, "Bot updated successfully"
        except Exception as e:
            return False, str(e)
    
    def get_logs(self, user_id, bot_name, lines=50):
        """Get bot logs"""
        user_id = str(user_id)
        if user_id not in self.bots or bot_name not in self.bots[user_id]:
            return None
        
        bot_info = self.bots[user_id][bot_name]
        
        try:
            if not self.docker_client:
                return "Docker not available"
            
            container = self.docker_client.containers.get(bot_info['container_name'])
            logs = container.logs(tail=lines).decode('utf-8')
            return logs if logs else "No logs yet"
        except:
            return "Bot not running"
    
    def get_user_bots(self, user_id):
        user_id = str(user_id)
        return self.bots.get(user_id, {})
    
    def get_status(self, user_id):
        user_bots = self.get_user_bots(user_id)
        total = len(user_bots)
        running = sum(1 for b in user_bots.values() if b['status'] == 'running')
        stopped = total - running
        return {'total': total, 'running': running, 'stopped': stopped}
    
    def get_system_stats(self):
        """Get VPS system statistics"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu': cpu,
            'memory_percent': memory.percent,
            'memory_used': memory.used / (1024**3),
            'memory_total': memory.total / (1024**3),
            'disk_percent': disk.percent,
            'disk_used': disk.used / (1024**3),
            'disk_total': disk.total / (1024**3)
        }

hosting = DockerBotHosting()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_name = update.effective_user.first_name
    
    stats = hosting.get_system_stats()
    
    welcome_text = f"""
🤖 <b>Welcome to Yato VPS Bot Hosting!</b>

Hi {user_name}! 👋

Deploy and host ANY Telegram bot on our VPS! 🚀

<b>✨ Supported Languages:</b>
🐍 Python | 📦 Node.js | 🐹 Go
💎 Ruby | 🐘 PHP | 🐳 Docker

<b>🎯 Features:</b>
✅ Deploy from GitHub (any language!)
✅ Auto-detect project type
✅ Docker containerization
✅ 24/7 uptime monitoring
✅ Easy start/stop/update
✅ Real-time logs
✅ Resource limits per bot

<b>📊 VPS Status:</b>
CPU: {stats['cpu']:.1f}% | RAM: {stats['memory_percent']:.1f}%
Disk: {stats['disk_used']:.1f}GB / {stats['disk_total']:.1f}GB

<b>Commands:</b>
/start - This message
/deploy - Deploy bot from GitHub
/bots - Manage your bots
/stats - VPS statistics
/help - Help & examples

Ready? Use /deploy to get started!
    """
    
    keyboard = [
        [InlineKeyboardButton("📋 My Bots", callback_data="my_bots")],
        [InlineKeyboardButton("🚀 Deploy New Bot", callback_data="deploy_new")],
        [InlineKeyboardButton("📊 VPS Stats", callback_data="vps_stats")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_bots_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deployed bots"""
    user_id = update.effective_user.id
    query = update.callback_query
    
    status = hosting.get_status(user_id)
    user_bots = hosting.get_user_bots(user_id)
    
    message_text = f"🤖 <b>Yato</b>\n📁 <b>/bots</b>\n\n"
    message_text += "🔍 <b>DEPLOYED BOTS INFO</b>\n\n"
    message_text += f"🤖 <b>{status['total']}</b> | 🟢 <b>{status['running']}</b> | 🔴 <b>{status['stopped']}</b> | 🟠 <b>0</b> |\n\n"
    
    if not user_bots:
        message_text += "📭 No bots deployed yet.\n\n"
        message_text += "Use /deploy to add your first bot!"
    else:
        for idx, (bot_name, info) in enumerate(user_bots.items(), 1):
            status_emoji = "🟢" if info['status'] == 'running' else "🔴"
            status_text = "RUNNING" if info['status'] == 'running' else "STOPPED"
            lang_emoji = {"python": "🐍", "nodejs": "📦", "golang": "🐹", "ruby": "💎", "php": "🐘"}.get(info.get('project_type', 'python'), "🐳")
            message_text += f"{lang_emoji} <b>{idx}. @{bot_name}</b>\n"
            message_text += f"{status_emoji} <b>{status_text}</b>\n\n"
    
    message_text += "\n<b>CLICK BELOW BUTTONS TO CHANGE SETTINGS</b>"
    
    keyboard = []
    
    # Bot buttons (3 per row)
    bot_buttons = []
    for idx in range(1, len(user_bots) + 1):
        bot_buttons.append(InlineKeyboardButton(f"🟢🤖 {idx}", callback_data=f"bot_{idx}"))
        if idx % 3 == 0:
            keyboard.append(bot_buttons)
            bot_buttons = []
    if bot_buttons:
        keyboard.append(bot_buttons)
    
    # Control buttons
    if user_bots:
        keyboard.extend([
            [
                InlineKeyboardButton("❌ STOP ALL", callback_data="stop_all"),
                InlineKeyboardButton("🗑️ REMOVE ALL", callback_data="remove_all")
            ]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ ADD NEW BOTS", callback_data="add_new")],
        [
            InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
            InlineKeyboardButton("CLOSE ❌", callback_data="close")
        ]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_vps_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show VPS statistics"""
    query = update.callback_query
    stats = hosting.get_system_stats()
    
    stats_text = f"""
📊 <b>VPS Statistics</b>

<b>CPU Usage:</b> {stats['cpu']:.1f}%
<b>Memory:</b> {stats['memory_used']:.2f}GB / {stats['memory_total']:.2f}GB ({stats['memory_percent']:.1f}%)
<b>Disk:</b> {stats['disk_used']:.1f}GB / {stats['disk_total']:.1f}GB ({stats['disk_percent']:.1f}%)

<b>Docker Status:</b> {'✅ Running' if hosting.docker_client else '❌ Not Available'}

<b>System Info:</b>
🐧 Linux VPS
🐳 Docker Enabled
🔒 Container Isolated
    """
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="my_bots")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, parse_mode='HTML', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "my_bots" or data == "refresh":
        await show_bots_menu(update, context)
    
    elif data == "close":
        await query.message.delete()
    
    elif data == "vps_stats":
        await show_vps_stats(update, context)
    
    elif data == "help":
        help_text = """
❓ <b>Help - Deploy Bots from GitHub</b>

<b>📝 Step-by-Step Guide:</b>

1️⃣ Create bot with @BotFather
2️⃣ Push your code to GitHub
3️⃣ Send /deploy to this bot
4️⃣ Provide token, name, and repo URL
5️⃣ Done! Bot deployed automatically

<b>🐍 Python Example (bot.py):</b>
<code>import os
from telegram.ext import Application, CommandHandler

async def start(update, context):
    await update.message.reply_text('Hi!')

app = Application.builder().token(os.getenv('BOT_TOKEN')).build()
app.add_handler(CommandHandler('start', start))
app.run_polling()</code>

<b>📦 Node.js Example (index.js):</b>
<code>const { Telegraf } = require('telegraf');
const bot = new Telegraf(process.env.BOT_TOKEN);
bot.start((ctx) => ctx.reply('Hi!'));
bot.launch();</code>

<b>📋 Requirements:</b>
• Public GitHub repo
• requirements.txt (Python) or package.json (Node.js)
• Use <code>process.env.BOT_TOKEN</code> or <code>os.getenv('BOT_TOKEN')</code>
• Main file: bot.py, index.js, main.go, etc.

<b>🐳 Advanced: Custom Docker</b>
Include Dockerfile for custom setup!

Need more help? Check examples:
https://github.com/examples/telegram-bots
        """
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="my_bots")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, parse_mode='HTML', reply_markup=reply_markup)
    
    elif data == "stop_all":
        user_bots = hosting.get_user_bots(user_id)
        for bot_name in user_bots.keys():
            hosting.stop_bot(user_id, bot_name)
        await query.answer("✅ All bots stopped!", show_alert=True)
        await show_bots_menu(update, context)
    
    elif data == "remove_all":
        user_bots = hosting.get_user_bots(user_id)
        for bot_name in list(user_bots.keys()):
            hosting.remove_bot(user_id, bot_name)
        await query.answer("✅ All bots removed!", show_alert=True)
        await show_bots_menu(update, context)
    
    elif data == "add_new" or data == "deploy_new":
        await start_deploy(update, context)
    
    elif data.startswith("bot_"):
        bot_idx = int(data.split("_")[1]) - 1
        user_bots = list(hosting.get_user_bots(user_id).keys())
        if bot_idx < len(user_bots):
            bot_name = user_bots[bot_idx]
            await show_bot_control(update, context, bot_name)

async def show_bot_control(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_name: str):
    """Show bot control panel"""
    query = update.callback_query
    user_id = update.effective_user.id
    bot_info = hosting.get_user_bots(user_id)[bot_name]
    
    status_emoji = "🟢" if bot_info['status'] == 'running' else "🔴"
    status_text = "RUNNING" if bot_info['status'] == 'running' else "STOPPED"
    lang = bot_info.get('project_type', 'unknown').upper()
    
    message_text = f"<b>🤖 Bot: @{bot_name}</b>\n\n"
    message_text += f"Status: {status_emoji} <b>{status_text}</b>\n"
    message_text += f"Language: <b>{lang}</b>\n"
    message_text += f"Repository: <code>{bot_info.get('repo_url', 'N/A')[:50]}</code>\n"
    message_text += f"Added: {bot_info['added_at'][:10]}\n"
    
    keyboard = []
    
    if bot_info['status'] == 'running':
        keyboard.append([InlineKeyboardButton("⏹️ STOP BOT", callback_data=f"stop_{bot_name}")])
        keyboard.append([InlineKeyboardButton("🔄 RESTART", callback_data=f"restart_{bot_name}")])
    else:
        keyboard.append([InlineKeyboardButton("▶️ START BOT", callback_data=f"start_{bot_name}")])
    
    keyboard.append([InlineKeyboardButton("🔃 UPDATE FROM GITHUB", callback_data=f"update_{bot_name}")])
    keyboard.append([InlineKeyboardButton("📊 VIEW LOGS", callback_data=f"logs_{bot_name}")])
    keyboard.append([InlineKeyboardButton("🗑️ REMOVE BOT", callback_data=f"remove_{bot_name}")])
    keyboard.append([InlineKeyboardButton("⬅️ BACK", callback_data="back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=reply_markup)

async def handle_bot_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot actions"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data == "back":
        await show_bots_menu(update, context)
        return
    
    action, bot_name = data.split("_", 1)
    
    if action == "start":
        await query.answer("⏳ Starting bot...")
        success, msg = hosting.start_bot(user_id, bot_name)
        await query.message.reply_text(f"{'✅' if success else '❌'} {msg}")
    
    elif action == "stop":
        success, msg = hosting.stop_bot(user_id, bot_name)
        await query.answer(f"{'✅' if success else '❌'} {msg}", show_alert=True)
    
    elif action == "restart":
        await query.answer("⏳ Restarting...")
        hosting.stop_bot(user_id, bot_name)
        success, msg = hosting.start_bot(user_id, bot_name)
        await query.message.reply_text(f"{'✅' if success else '❌'} {msg}")
    
    elif action == "update":
        await query.answer("⏳ Updating from GitHub...")
        success, msg = hosting.update_bot(user_id, bot_name)
        await query.message.reply_text(f"{'✅' if success else '❌'} {msg}")
    
    elif action == "remove":
        success, msg = hosting.remove_bot(user_id, bot_name)
        await query.answer(f"{'✅' if success else '❌'} {msg}", show_alert=True)
        await show_bots_menu(update, context)
        return
    
    elif action == "logs":
        await query.answer("📊 Fetching logs...")
        logs = hosting.get_logs(user_id, bot_name)
        await query.message.reply_text(f"📊 <b>Logs:</b>\n\n<code>{logs}</code>", parse_mode='HTML')
    
    await show_bot_control(update, context, bot_name)

# Deploy conversation
async def start_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        message = update.message
    
    deploy_text = """
🚀 <b>Deploy Bot from GitHub</b>

I'll deploy your bot using Docker containers!

<b>Step 1:</b> Send your bot token from @BotFather

Example: <code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>

Send /cancel to cancel.
    """
    await message.reply_text(deploy_text, parse_mode='HTML')
    return WAITING_BOT_TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    
    if ':' not in token or len(token) < 20:
        await update.message.reply_text("❌ Invalid token format.")
        return WAITING_BOT_TOKEN
    
    context.user_data['deploy_token'] = token
    
    await update.message.reply_text(
        "✅ Token received!\n\n"
        "<b>Step 2:</b> Send bot username (without @)\n\n"
        "Example: <code>myfilebot</code>",
        parse_mode='HTML'
    )
    return WAITING_BOT_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_name = update.message.text.strip().replace('@', '').lower()
    
    if not bot_name.isalnum():
        await update.message.reply_text("❌ Bot name should contain only letters and numbers.")
        return WAITING_BOT_NAME
    
    context.user_data['deploy_name'] = bot_name
    
    repo_example = """
✅ Bot name received!

<b>Step 3:</b> Send your GitHub repository URL

<b>Supported Languages:</b>
🐍 Python | 📦 Node.js | 🐹 Go | 💎 Ruby | 🐘 PHP

<b>Examples:</b>
<code>https://github.com/username/telegram-bot</code>
<code>https://github.com/username/bot-repo.git</code>

<b>Requirements:</b>
• Public repository
• Use <code>BOT_TOKEN</code> environment variable
• Include requirements.txt or package.json

<b>Python Example:</b>
Use <code>os.getenv('BOT_TOKEN')</code>

<b>Node.js Example:</b>
Use <code>process.env.BOT_TOKEN</code>

Repository will be auto-detected and deployed!
    """
    await update.message.reply_text(repo_example, parse_mode='HTML')
    return WAITING_GITHUB_REPO

async def receive_github_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    repo_url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Validate GitHub URL
    if not re.match(r'https?://github\.com/[\w-]+/[\w.-]+', repo_url):
        await update.message.reply_text(
            "❌ Invalid GitHub URL.\n\n"
            "Example: <code>https://github.com/username/repo</code>",
            parse_mode='HTML'
        )
        return WAITING_GITHUB_REPO
    
    token = context.user_data.get('deploy_token')
    bot_name = context.user_data.get('deploy_name')
    
    status_msg = await update.message.reply_text(
        "⏳ <b>Deploying your bot...</b>\n\n"
        "🔄 Step 1: Cloning repository...",
        parse_mode='HTML'
    )
    
    try:
        # Deploy bot
        success, message = hosting.add_bot(user_id, bot_name, token, repo_url)
        
        if success:
            await status_msg.edit_text(
                "🔄 Step 2: Building Docker image...\n"
                "This may take a minute...",
                parse_mode='HTML'
            )
            
            success_text = f"""
✅ <b>Bot Deployed Successfully!</b>

🤖 Bot: @{bot_name}
📦 Repository: <code>{repo_url[:50]}...</code>
📍 Status: Ready to start
{message}

Your bot is now hosted in a Docker container!
Click below to start it.
            """
            
            keyboard = [
                [InlineKeyboardButton("▶️ Start Bot Now", callback_data=f"start_{bot_name}")],
                [InlineKeyboardButton("📋 View My Bots", callback_data="my_bots")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(success_text, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await status_msg.edit_text(
                f"❌ <b>Deployment Failed</b>\n\n"
                f"Error: {message}\n\n"
                f"<b>Common Issues:</b>\n"
                f"• Check if repo is public\n"
                f"• Ensure requirements.txt or package.json exists\n"
                f"• Verify bot code is correct\n\n"
                f"Try again with /deploy",
                parse_mode='HTML'
            )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Error:</b>\n<code>{str(e)}</code>\n\nTry /deploy again",
            parse_mode='HTML'
        )
        return ConversationHandler.END

async def cancel_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Deployment cancelled.")
    return ConversationHandler.END

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show VPS stats command"""
    stats = hosting.get_system_stats()
    user_bots = hosting.get_user_bots(update.effective_user.id)
    
    stats_text = f"""
📊 <b>VPS Statistics</b>

<b>System Resources:</b>
💻 CPU: {stats['cpu']:.1f}%
🧠 RAM: {stats['memory_used']:.2f}GB / {stats['memory_total']:.2f}GB ({stats['memory_percent']:.1f}%)
💾 Disk: {stats['disk_used']:.1f}GB / {stats['disk_total']:.1f}GB ({stats['disk_percent']:.1f}%)

<b>Your Bots:</b>
🤖 Total: {len(user_bots)}
🟢 Running: {sum(1 for b in user_bots.values() if b['status'] == 'running')}
🔴 Stopped: {sum(1 for b in user_bots.values() if b['status'] == 'stopped')}

<b>Docker Status:</b> {'✅ Active' if hosting.docker_client else '❌ Inactive'}
    """
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

def main():
    """Start the bot"""
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ Error: BOT_TOKEN not set in environment!")
        return
    
    # Check Docker
    try:
        docker_client = docker.from_env()
        docker_client.ping()
        print("✅ Docker is running")
    except Exception as e:
        print(f"❌ Docker not available: {e}")
        print("Install Docker: curl -fsSL https://get.docker.com | sh")
        return
    
    # Check Git
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        print("✅ Git is installed")
    except:
        print("❌ Git not installed! Run: apt install git")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    # Deploy conversation
    deploy_conv = ConversationHandler(
        entry_points=[
            CommandHandler('deploy', start_deploy),
            CallbackQueryHandler(start_deploy, pattern="^(add_new|deploy_new)$")
        ],
        states={
            WAITING_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            WAITING_BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_GITHUB_REPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_github_repo)]
        },
        fallbacks=[CommandHandler('cancel', cancel_deploy)]
    )
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("bots", show_bots_menu))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(deploy_conv)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(my_bots|refresh|close|vps_stats|help|stop_all|remove_all)$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^bot_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_bot_action))
    
    print("🚀 Yato VPS Bot Hosting Service Started!")
    print("📦 Docker: Enabled")
    print("🌐 Multi-language support: Active")
    print("👥 Ready to accept deployments...")
    
    application.run_polling()

if __name__ == '__main__':
    main()
