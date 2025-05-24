import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import List, Dict, Any, Optional, TypedDict
import asyncio
import nest_asyncio
import json
from contextlib import AsyncExitStack

nest_asyncio.apply()

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict

class MCP_ChatBot:
    """
    A chatbot that interacts with an Ollama language model and can use tools
    provided by an MCP (Modular Computing Platform) server.
    """

    OLLAMA_MODEL = "qwen3"  # Define the Ollama model    

    def __init__(self):
        """Initializes the MCP_ChatBot."""
        self.sessions: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        self.ollama = ollama.AsyncClient()
        self.available_tools: List[Dict[str, Any]] = []
        self.tool_to_session: Dict[str, ClientSession] = {}

    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions.append(session)
            
            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])
            
            for tool in tools:
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                }
                })

        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")

    async def connect_to_servers(self):
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            if not servers:
                print("No MCP servers configured in server_config.json or 'mcpServers' key is missing/empty.")
                return
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise

    async def _handle_tool_calls(self,
                                 tool_calls: List['ollama.ToolCall'],
                                 messages: List[Dict[str, Any]]):
        """
        Processes tool calls requested by the LLM, executes them via MCP,
        and appends the results to the messages list.
        """
        if not tool_calls:
            return

        if not self.sessions: # Check if any server connections exist at all
            print("Warning: LLM requested tool calls, but no MCP servers are connected.")
            for tool_call_obj in tool_calls:
                # Safely get attributes for error reporting
                tool_function_obj = getattr(tool_call_obj, 'function', None)
                tool_name = getattr(tool_function_obj, 'name', 'unknown_tool')

                messages.append({
                    'role': 'tool',
                    'content': f"Error: No MCP server connections available to execute tool {tool_name}."
                })
            return messages

        for tool_call_obj in tool_calls:

            tool_function_obj = getattr(tool_call_obj, 'function', None)
            tool_name = getattr(tool_function_obj, 'name', None)
            tool_args_dict = getattr(tool_function_obj, 'arguments', None)

            if tool_function_obj is None:
                print(f"Error: Malformed tool call object received (missing 'function' attribute). Skipping. Object: {tool_call_obj}")
                continue

            if tool_name is None or tool_args_dict is None:
                print(f"Error: Malformed tool call function object received (missing 'name' or 'arguments'). "
                      f"Skipping. Function Object: {tool_function_obj}")
                continue

            print(f"\nLLM wants to call tool: '{tool_name}' with arguments: {tool_args_dict}")

            tool_message_content = ""
            session_for_tool = self.tool_to_session.get(tool_name)

            if session_for_tool:
                try:
                    mcp_tool_result = await session_for_tool.call_tool(tool_name, arguments=tool_args_dict)
                    raw_tool_output = mcp_tool_result.content

                    if isinstance(raw_tool_output, list) and raw_tool_output and hasattr(raw_tool_output[0], 'text'):
                        tool_message_content = raw_tool_output[0].text
                    elif isinstance(raw_tool_output, str):
                        tool_message_content = raw_tool_output
                    else:
                        tool_message_content = str(raw_tool_output)
                except Exception as e:
                    error_message = f"Error calling MCP tool '{tool_name}': {e}"
                    print(error_message)
                    tool_message_content = error_message
            else:
                is_advertised_tool = any(t['function']['name'] == tool_name for t in self.available_tools)
                if is_advertised_tool:
                    error_message = f"Error: Tool '{tool_name}' was advertised to LLM, but no specific MCP session is associated with it. This indicates an internal setup error."
                else:
                    error_message = f"Error: LLM requested unknown tool '{tool_name}'. This tool was not in the list of available tools provided."
                print(error_message)
                tool_message_content = error_message
            
            messages.append({
                'role': 'tool',
                'content':tool_message_content
            })

    async def process_query(self, query: str):
        """
        Processes a user query by sending it to the Ollama model,
        handling any requested tool calls, and printing the final response.

        Args:
            query: The user's input query string.
        """

        messages: List[Dict[str, Any]] = [{'role': 'user', 'content': query}]

        try:
            # Initial call to LLM
            llm_response = await self.ollama.chat(
                model=self.OLLAMA_MODEL,
                messages=messages,
                tools=self.available_tools if self.available_tools else None,
            )

            print(f"\nDEBUG: LLM Response: {llm_response}")
            messages.append(llm_response.message.model_dump(exclude_none=True))

            process_query = True
            while process_query:
                assistant_content = []

                if not llm_response.message.tool_calls:
                    print(llm_response.message.content)
                    assistant_content.append(llm_response.message.content)
                    process_query= False

                elif len(llm_response.message.tool_calls) > 0: #tool use
                    await self._handle_tool_calls(llm_response.message.tool_calls, messages)                        
                    print(f"DEBUG: Messages after tool execution: {messages}")
                    llm_response = await self.ollama.chat(
                                                        model=self.OLLAMA_MODEL,
                                                        messages=messages, 
                                                        tools=self.available_tools if self.available_tools else None, 
                                                    )   
                    messages.append(llm_response.message.model_dump(exclude_none=True))

                    if not llm_response.message.tool_calls:
                        print(llm_response.message.content)
                        process_query = False
                    else:
                        print("DEBUG: Tool calls requested!")
        
        except Exception as e:
            print(f"\nError during LLM interaction or tool processing: {e}")

    async def chat_loop(self):
        """Runs the interactive chat loop, taking user input and processing queries."""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    print("Exiting chat loop.")
                    break
                if not query: 
                    continue # Skip empty input
                    
                await self.process_query(query)
                    
            except KeyboardInterrupt:
                print("\nExiting chat loop due to KeyboardInterrupt.")
                break
            except Exception as e:
                print(f"\nError in chat loop: {e}")

    async def cleanup(self): 
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

async def main():
    """Main entry point for the chatbot application."""
    chatbot = MCP_ChatBot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    
    finally:
        await chatbot.cleanup()
  
if __name__ == "__main__":
    asyncio.run(main())