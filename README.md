# MCP ChatBot

A Python-based chatbot that integrates Ollama language models with Model Context Protocol (MCP) servers, enabling LLMs to use external tools and data sources through standardized MCP connections.

## Overview

This chatbot creates a bridge between Ollama language models and MCP servers, allowing the LLM to:
- Access local file systems
- Fetch web content

The chatbot follows MCP's client-server architecture, where it acts as an MCP client connecting to multiple MCP servers that expose various capabilities.

## Prerequisites

- Python 3.8+
- uv - Fast Python package manager
- Ollama installed and running locally
- MCP servers (e.g: filesystem, fetch web content)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Mithul-Joseph/mcp_project.git
cd mcp_project
```

2. Install uv (if not already installed)
Windows:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. Create a virtual environment and install dependencies:
```bash
uv init
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv add ollama mcp nest-asyncio
```

Required packages:
- `ollama`
- `mcp`
- `nest-asyncio`

## Usage

1. Activate your virtual environment (if not already activated):
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Start the chatbot:
```bash
uv run python mcp_chatbot.py
```

The chatbot will:
- Connect to configured MCP servers
- Display available tools
- Start an interactive chat session

3. Type `quit` to exit the chat session.

## How It Works

### Architecture

```
┌─────────────────┐    ┌─────────────┐    ┌─────────────────┐
│   Ollama LLM    │◄──►│ MCP ChatBot │◄──►│   MCP Servers   │
│   (qwen3)       │    │  (Client)   │    │ (filesystem,    │
└─────────────────┘    └─────────────┘    │  fetch, etc.)   │
                                          └─────────────────┘
```

### Process Flow

1. **Initialization**: Connect to configured MCP servers and discover available tools
2. **User Input**: Receive user query through command-line interface
3. **LLM Processing**: Send query to Ollama with available tool definitions
4. **Tool Execution**: If LLM requests tools, execute them via MCP servers
5. **Response Generation**: LLM processes tool results and generates final response
6. **Output**: Display response to user and wait for next query

### Tool Call Handling

When the LLM decides to use tools:
1. Parse tool calls from LLM response
2. Route each tool call to appropriate MCP server
3. Execute tools and collect results
4. Send results back to LLM for response generation

## Configuration Options

### Ollama Model
Change the model in the code:
```python
OLLAMA_MODEL = "qwen3"  # Change to your preferred model
```

## Example

### Fetching Web Content
```
Query: First, fetch the contents of https://modelcontextprotocol.io/introduction. After you get the content, then save it to mcp_intro.md
```

### File Analysis
```
Query: Read all .py files in the current directory and tell me what they do
```

## References

- [Model Context Protocol](https://modelcontextprotocol.io/) - Official MCP documentation
- [Ollama](https://ollama.com) - Local LLM platform
- [MCP Servers](https://github.com/modelcontextprotocol/servers) - Official MCP server implementations