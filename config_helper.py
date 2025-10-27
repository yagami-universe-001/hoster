"""
Yagami Bot Manager - Configuration Helper
Interactive script to help configure the bot
"""

import os
import sys

def print_header():
    """Print header"""
    print("=" * 60)
    print("🤖 Yagami Bot Manager - Configuration Helper")
    print("=" * 60)
    print()

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import telegram
        print("✅ python-telegram-bot is installed")
        return True
    except ImportError:
        print("❌ python-telegram-bot is not installed")
        print("   Run: pip3 install -r requirements.txt")
        return False

def get_bot_token():
    """Get bot token from user"""
    print("\n📝 Bot Token Configuration")
    print("-" * 60)
    print("You need a bot token from @BotFather on Telegram")
    print()
    
    token = input("Enter your bot token: ").strip()
    
    if not token:
        print("❌ Token cannot be empty")
        return None
        
    if ':' not in token:
        print("❌ Invalid token format")
        return None
        
    return token

def create_env_file(token, admin_ids=""):
    """Create .env file"""
    env_content = f"""# Yagami Bot Manager Configuration

# Your main bot token from @BotFather
BOT_TOKEN={token}

# Optional: Admin user IDs (comma separated)
ADMIN_IDS={admin_ids}

# Optional: Database path
CONFIG_FILE=bots_config.json

# Optional: Bots directory
BOTS_DIR=deployed_bots
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("\n✅ .env file created successfully")
        return True
    except Exception as e:
        print(f"\n❌ Error creating .env file: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    dirs = ['deployed_bots', 'logs']
    
    for directory in dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        except Exception as e:
            print(f"❌ Error creating {directory}: {e}")
            return False
    
    return True

def show_next_steps():
    """Show next steps"""
    print("\n" + "=" * 60)
    print("🎉 Configuration completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the bot:")
    print("   ./run.sh")
    print("   or")
    print("   python3 main.py")
    print()
    print("2. Open Telegram and find your bot")
    print("3. Send /start to your bot")
    print("4. Use /bots to manage deployed bots")
    print()
    print("For more help, check README.md or INSTALL.md")
    print("=" * 60)

def main():
    """Main function"""
    print_header()
    
    # Check Python version
    if not check_python_version():
        return
    
    print()
    
    # Check dependencies
    if not check_dependencies():
        install = input("\nDo you want to install dependencies now? (y/n): ").lower()
        if install == 'y':
            print("\nInstalling dependencies...")
            os.system("pip3 install -r requirements.txt")
            print()
        else:
            print("\nPlease install dependencies before continuing")
            return
    
    # Check if .env already exists
    if os.path.exists('.env'):
        overwrite = input("\n⚠️  .env file already exists. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Configuration cancelled")
            return
    
    # Get bot token
    token = get_bot_token()
    if not token:
        return
    
    # Optional: Get admin IDs
    print("\n📝 Admin Configuration (Optional)")
    print("-" * 60)
    print("You can add admin user IDs for restricted access")
    print("Leave empty to skip")
    admin_ids = input("Enter admin user IDs (comma separated): ").strip()
    
    # Create .env file
    if not create_env_file(token, admin_ids):
        return
    
    # Create directories
    print("\n📁 Creating directories...")
    if not create_directories():
        return
    
    # Show next steps
    show_next_steps()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuration cancelled by user")
        sys.exit(0)
