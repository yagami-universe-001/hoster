# Yagami Bot Manager 🚀

Deploy and manage Telegram bots directly from GitHub repositories through a Telegram interface. Admin-only VPS deployment system.

## 🌟 Features

- 🔗 **Deploy from GitHub** - Clone any bot repository directly
- 📦 **Auto Setup** - Automatically installs requirements.txt
- ▶️ **Full Control** - Start, Stop, Restart bots
- ⬆️ **Git Pull Updates** - Update bots with latest code
- 📋 **View Logs** - Monitor bot activity
- 🔒 **Admin Only** - Secure access control
- 🎯 **Multiple Bots** - Manage unlimited bots from one interface

## 📸 Screenshot

```
🔍 DEPLOYED BOTS INFO

🤖 3 | 🟢 3 | 🔴 0 | 🟠 0 |

🤖 1. tqfilexbot
🟢 RUNNING
📦 Repo: https://github.com/user/filebot

🤖 2. tgfilex2bot
🟢 RUNNING
📦 Repo: https://github.com/user/filebot2

🤖 3. fayefilebot
🟢 RUNNING
📦 Repo: https://github.com/user/filebot3
```

## 🚀 Quick Start

### Prerequisites
- VPS with Ubuntu 20.04+ or Debian 10+
- Python 3.8+
- Git installed
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/yagami-bot-manager.git
cd yagami-bot-manager

# Run setup
chmod +x setup.sh
./setup.sh

# Configure
nano .env
# Add your BOT_TOKEN and ADMIN_IDS

# Start
./run.sh
```

## 📝 Configuration

Edit `.env` file:

```bash
# Your manager bot token
BOT_TOKEN=123456:ABC-DEF-your-token-here

# Admin Telegram user IDs (comma separated)
ADMIN_IDS=123456789,987654321
```

**How to get your User ID:**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID
3. Add it to ADMIN_IDS in .env

## 🎯 Usage

### Deploy a Bot from GitHub

```
/deploy bot_name github_url bot_token [main_file]
```

**Example:**
```
/deploy myfilebot https://github.com/username/filebot 123456:ABC-DEF main.py
```

**Parameters:**
- `bot_name` - Name for your bot (no spaces)
- `github_url` - Full GitHub repository URL
- `bot_token` - Bot token from @BotFather
- `main_file` - Main Python file (optional, default: main.py)

### Manage Bots

Send `/bots` to see this interface:

```
[🟢🤖 1] [🟢🤖 2] [🟢🤖 3]

[❌ STOP ALL] [🗑️ REMOVE ALL]

[➕ ADD NEW BOTS]

[🔄 REFRESH] [❌ CLOSE]
```

Click on any bot number to:
- ▶️ Start/Stop bot
- 🔄 Restart bot
- ⬆️ Update from GitHub
- 📋 View logs
- 🗑️ Remove bot

## 🛠️ Bot Requirements

Your GitHub repository should have:

1. **Main Python file** (e.g., `main.py` or `bot.py`)
   ```python
   import os
   from telegram.ext import Application
   
   def main():
       token = os.getenv('BOT_TOKEN')
       app = Application.builder().token(token).build()
       # Your bot code here
       app.run_polling()
   
   if __name__ == '__main__':
       main()
   ```

2. **requirements.txt** (optional but recommended)
   ```
   python-telegram-bot==20.7
   # other dependencies
   ```

3. **Bot should read token from environment**
   ```python
   token = os.getenv('BOT_TOKEN')
   ```

## 📋 Commands Reference

| Command | Description |
|---------|-------------|
| `/start` | Initialize the manager bot |
| `/deploy <name> <repo> <token> [file]` | Deploy bot from GitHub |
| `/bots` | Show all deployed bots with controls |
| `/help` | Show help information |

## 🔧 Advanced Usage

### Update Bot from GitHub

When you push changes to your bot's GitHub repository:

1. Open `/bots` panel
2. Click on the bot number
3. Click "⬆️ Update from GitHub"
4. Click "🔄 Restart" to apply changes

This will automatically:
- Pull latest code (`git pull`)
- Reinstall requirements if changed
- Keep your bot updated

### View Bot Logs

1. Open `/bots` panel
2. Click on the bot number
3. Click "📋 Logs"

Shows last 20 lines of bot output.

### Run on System Startup (systemd)

```bash
# Copy service file
sudo cp yagami-bot.service /etc/systemd/system/

# Edit paths in service file
sudo nano /etc/systemd/system/yagami-bot.service

# Enable and start
sudo systemctl enable yagami-bot
sudo systemctl start yagami-bot

# Check status
sudo systemctl status yagami-bot
```

## 📁 Project Structure

```
yagami-bot-manager/
├── main.py                 # Main manager bot
├── requirements.txt        # Dependencies
├── bots_config.json       # Bot configurations (auto-created)
├── deployed_bots/         # Deployed bot repositories
│   ├── bot1/              # Each bot in its own folder
│   ├── bot2/
│   └── bot3/
├── logs/                  # Log files
├── setup.sh               # Setup script
├── run.sh                 # Run script
├── .env                   # Configuration (create from .env.example)
└── README.md
```

## 🔒 Security

### Admin-Only Access

Only users with IDs in `ADMIN_IDS` can:
- Deploy bots
- Start/Stop bots
- View bot information
- Update bots
- Remove bots

### Best Practices

1. **Never share tokens**
   ```bash
   chmod 600 .env
   chmod 600 bots_config.json
   ```

2. **Use strong passwords** for VPS

3. **Keep system updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

4. **Enable firewall**
   ```bash
   sudo ufw enable
   sudo ufw allow 22/tcp
   ```

5. **Use private GitHub repos** for sensitive bots

## 🐛 Troubleshooting

### Bot Not Responding

```bash
# Check if manager is running
ps aux | grep "main.py"

# Check logs
tail -f logs/bot_*.log

# Restart manager
./run.sh
```

### Deployment Failed

**Common issues:**

1. **Invalid GitHub URL**
   - Use full URL: `https://github.com/user/repo`
   - Make sure repository is public or you have access

2. **Repository not found**
   - Check if repository exists
   - For private repos, use personal access token:
     ```
     https://TOKEN@github.com/user/repo
     ```

3. **Requirements installation failed**
   - Check `requirements.txt` syntax
   - Install manually: `pip3 install package-name`

4. **Bot won't start**
   - Check main file name is correct
   - Verify bot reads token from environment
   - Check bot code for errors

### Bot Stops Automatically

1. **Check bot logs** for errors
2. **Ensure bot handles exceptions**
3. **Check VPS resources** (RAM/CPU)

### Permission Denied

```bash
chmod +x setup.sh run.sh main.py
sudo chown -R $USER:$USER ~/yagami-bot-manager
```

## 📚 Example Bot Repository

Your bot repository structure:

```
your-bot-repo/
├── main.py              # or bot.py
├── requirements.txt
├── config.py           # optional
├── handlers/           # optional
│   ├── start.py
│   └── files.py
└── README.md
```

**main.py example:**

```python
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

def main():
    # Get token from environment (set by Yagami Manager)
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        print("Error: BOT_TOKEN not set")
        return
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Bot started!")
    app.run_polling()

if __name__ == '__main__':
    main()
```

## 🔄 Updating Yagami Manager

```bash
cd ~/yagami-bot-manager
git pull origin main
pip3 install -r requirements.txt --upgrade

# Restart
sudo systemctl restart yagami-bot
# or
./run.sh
```

## 📦 Supported Bot Types

Yagami can deploy any Python Telegram bot that:
- Uses `python-telegram-bot` library
- Reads token from `BOT_TOKEN` environment variable
- Has a main Python file that runs the bot

Examples:
- ✅ File sharing bots
- ✅ Media download bots
- ✅ Admin bots
- ✅ Service bots
- ✅ Game bots
- ✅ Any Python telegram bot!

## 🆚 Why Yagami?

| Feature | Manual Deployment | Yagami Manager |
|---------|------------------|----------------|
| Deploy from GitHub | Manual clone | One command |
| Start/Stop bots | SSH required | Telegram interface |
| Update bots | Manual git pull | One click |
| View logs | SSH + commands | Telegram interface |
| Manage multiple bots | Complex | Simple panel |
| Access control | SSH keys | Admin IDs |

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🆘 Support

- 📖 Documentation: Check this README and [INSTALL.md](INSTALL.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/yagami-bot-manager/issues)
- 💬 Telegram: [@YourChannel](https://t.me/yourchannel)

## ⚠️ Disclaimer

- This tool is for personal/educational use
- Comply with Telegram's Terms of Service
- Don't deploy malicious or spam bots
- Respect rate limits and API guidelines

## 🙏 Credits

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Inspired by the need for simple VPS bot management

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/yourusername/yagami-bot-manager)
![GitHub forks](https://img.shields.io/github/forks/yourusername/yagami-bot-manager)
![GitHub issues](https://img.shields.io/github/issues/yourusername/yagami-bot-manager)
![Python Version](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

**Made with ❤️ for the Telegram Bot Community**

Star ⭐ this repo if you find it useful!
