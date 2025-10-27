#!/bin/bash

# Yagami Bot Manager - Setup Script
echo "🤖 Setting up Yagami Bot Manager..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "📦 Installing pip..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi

echo "✅ pip found: $(pip3 --version)"

# Create virtual environment (optional but recommended)
read -p "Do you want to create a virtual environment? (y/n): " use_venv
if [ "$use_venv" == "y" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ Virtual environment created and activated"
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p deployed_bots
mkdir -p logs

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your BOT_TOKEN"
else
    echo "✅ .env file already exists"
fi

# Make scripts executable
chmod +x setup.sh
chmod +x run.sh
chmod +x main.py

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your BOT_TOKEN"
echo "2. Run: ./run.sh (or 'python3 main.py')"
echo ""
echo "For systemd setup, check README.md"
