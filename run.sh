#!/bin/bash

# Yagami Bot Manager - Run Script
echo "🤖 Starting Yagami Bot Manager..."

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Environment variables loaded"
else
    echo "⚠️  .env file not found. Using system environment variables."
fi

# Check if BOT_TOKEN is set
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN not set. Please set it in .env file or environment."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run the bot with logging
echo "🚀 Starting bot..."
python3 main.py 2>&1 | tee -a logs/bot_$(date +%Y%m%d).log
