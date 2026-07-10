#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting local setup..."

# Check if uv is installed
if ! command -v uv &> /dev/null
then
    echo "❌ 'uv' is not installed. Please install it first: https://github.com/astral-sh/uv"
    exit 1
fi

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Copying .env.example to .env..."
    cp .env.example .env
fi

# Install dependencies
echo "📦 Installing backend dependencies..."
uv --project backend sync

# Run migrations
echo "⚙️ Running database migrations..."
cd backend
uv run alembic upgrade head

# Create superuser
echo "👤 Creating first superuser..."
uv run python -m app.commands.create_first_superuser
uv run python -m app.commands.seed_defaults

echo "✅ Setup complete! You can now run the app with 'make run-backend' (local dev) or 'make docker-local' (containers)."
