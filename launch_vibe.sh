#!/bin/bash
set -e

echo "🛑 Stopping existing VIBE containers..."
docker compose down --remove-orphans

echo "🗑️  Running Docker System Prune (Safe Mode - Preserving Volumes)..."
# Removed --volumes so your database survives the rebuild!
docker system prune -a -f

echo "🏗️  Rebuilding Images..."
docker compose build --no-cache

echo "🌐 Starting Databases and Cache..."
docker compose up -d vibe_db geoserver
sleep 15

echo "🛠️ Initializing NetAlytics Database..."
docker compose run --rm vibe python app_database_setup.py

echo "🚀 Launching All Services..."
docker compose up -d

echo "🧠 Pulling Qwen 2.5 (7B) Model into Ollama..."
echo "⏳ (This may take a few minutes on the first run as it downloads ~4.7GB)..."
docker exec vibe_ollama ollama pull qwen2.5:7b

echo "🧠 Pulling Nomic Embeddings (for Semantic Cache)..."
docker exec vibe_ollama ollama pull nomic-embed-text

echo "✅ ALL SYSTEMS ONLINE (Data Preserved!)"
echo "   NetAlytics: http://qdt-ai.com:5000"
echo "   Metabase: http://qdt-ai.com:8088"
