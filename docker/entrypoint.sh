#!/bin/bash
set -e

echo "🚀 Starting AngeVoice service..."
exec kokoro-tts serve
