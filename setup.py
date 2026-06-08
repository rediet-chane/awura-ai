# Awura AI 🤖

**A completely private, local AI assistant that runs on your device with no internet required.**

![Demo](demo.gif)

## Features ✨

- 💬 **Chat with AI** - Local LLM via Ollama
- 🗄️ **Database Queries** - Employee and project management
- 📧 **Email Integration** - Send emails via Gmail
- 📁 **GitHub Integration** - Create and list repositories
- 🎤 **Voice Input** - Speech recognition with auto-submit
- 📎 **File Processing** - PDF, Word, PowerPoint
- 🌙 **Dark/Light Mode** - Easy on the eyes
- 💾 **Chat History** - Saved to local database

## Quick Start 🚀

### Prerequisites

1. Install [Ollama](https://ollama.com)
2. Pull a model: `ollama pull qwen2.5:1.5b`
3. Run Ollama: `ollama serve`

### Installation

```bash
# Clone the repository
git clone https://github.com/rediet-chane/awura-ai.git
cd awura-ai

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your tokens (optional - for email/GitHub)

# Run the app
python main.py