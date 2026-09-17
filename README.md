#  Awura AI - Local AI Assistant

A powerful, privacy-focused AI assistant that runs entirely on your local machine. Built for Awura to provide intelligent document analysis, database queries, and automated workflows without sending sensitive data to the cloud.

![Status](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Ollama](https://img.shields.io/badge/Ollama-Latest-orange)

## ✨ Features

### Core Capabilities
- 🏠 **100% Local** - Runs entirely offline, no internet required for inference
- 🔒 **Privacy First** - Your data never leaves your machine
- 💬 **Natural Chat** - Intuitive chat interface with real-time streaming responses
- 📎 **Multi-Format Support** - Upload and analyze PDF, DOCX, PPTX, TXT, and MD files
- 🗄️ **Database Integration** - Query company data (employees, projects) directly via SQL
- ⚡ **MCP Tools** - Automated tools for calculations, datetime, and external actions
- 🎤 **Voice Input** - Speak your queries hands-free (Web Speech API)
- 📜 **Chat History** - All conversations saved locally in SQLite
- 🌙 **Dark/Light Mode** - Beautiful, responsive UI themes

### MCP (Model Context Protocol) Tools
- **🕐 DateTime** - Get current real-time date and time
- **👥 Database Query** - Search employees, projects, and company data
- **🧮 Calculator** - Perform mathematical calculations safely
- **📧 Email Integration** - Send emails via Zapier (configurable)
- **💻 GitHub Integration** - Manage repositories via Zapier (configurable)

##  Quick Start

### Prerequisites
- Python 3.10 or higher
- [Ollama](https://ollama.com) installed and running
- 8GB+ RAM (16GB recommended for larger models)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/rediet-chane/awura-ai.git
   cd awura-ai
