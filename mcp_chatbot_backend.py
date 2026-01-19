from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
    AIMessage,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
import os
import aiosqlite
import asyncio
import json
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# -------------------------------------------------
# 0. Setup
# -------------------------------------------------
load_dotenv()

WORKING_DIRECTORY = os.getcwd()

# Generic system prompt - works with any MCP tools
SYSTEM_PROMPT = SystemMessage(
    content=f"""You are a helpful AI assistant with access to various tools through MCP servers.

Your working directory is: {WORKING_DIRECTORY}

TOOL USAGE GUIDELINES:
1. When tools are available, use them to provide accurate, real-time information
2. If a tool requires a "directory" parameter, use: "{WORKING_DIRECTORY}"
3. Call tools when they can help answer the user's question
4. After receiving tool results, interpret and present them in a clear, natural way
5. Don't show raw JSON unless the user specifically asks for it
6. Extract and highlight the most relevant information from tool responses
7. If a tool fails, explain the error and suggest alternatives

IMPORTANT FILESYSTEM RULES:
- Never request full directory trees
- Always limit directory depth to 2 levels maximum
- Prefer listing folder names only
- Never return full file contents unless explicitly asked


RESPONSE STYLE:
- Be conversational and natural
- Summarize data clearly (e.g., "I found 5 accounts" instead of showing raw JSON)
- Only show technical details if requested
- Format lists and data in a readable way"""
)

# -------------------------------------------------
# 1. LLMs
# -------------------------------------------------
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPEN_AI_API_KEY"),
    temperature=0,
)

# -------------------------------------------------
# 2. MCP Client Configuration
# -------------------------------------------------
# Configure your MCP servers here
MCP_SERVERS = {
    "salesforce": {
        "transport": "stdio",
        "command": "npx",
        "args": [
            "@salesforce/mcp",
            "--orgs", "DEFAULT_TARGET_ORG",
            "--toolsets", "data,users,metadata,orgs",
        ],
        "env": {
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
            "PWD": WORKING_DIRECTORY
        },
    },
    # Add more MCP servers here as needed:
    # "filesystem": {
    #     "transport": "stdio",
    #     "command": "npx",
    #     "args": ["-y", "@modelcontextprotocol/server-filesystem", WORKING_DIRECTORY],
    # },
    # "github": {
    #     "transport": "stdio",
    #     "command": "npx",
    #     "args": ["-y", "@modelcontextprotocol/server-github"],
    #     "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN")},
    # },
    "github": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN"),
        },
    },
    "filesystem": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", WORKING_DIRECTORY],
    },
}

client = MultiServerMCPClient(MCP_SERVERS)

async def load_mcp_tools() -> list[BaseTool]:
    """Load all tools from configured MCP servers"""
    tools = await client.get_tools()
    return tools

# Use asyncio.run() instead of get_event_loop() to avoid deprecation warning
mcp_tools = None

async def initialize_tools():
    global mcp_tools
    mcp_tools = await load_mcp_tools()
    
    print("\n" + "="*60)
    print("MCP TOOLS LOADED:")
    print("="*60)
    for tool in mcp_tools:
        print(f"  ✓ {tool.name}")
    print("="*60)
    print(f"Total tools: {len(mcp_tools)}")
    print(f"Working Directory: {WORKING_DIRECTORY}")
    print("="*60 + "\n")

# Initialize tools
asyncio.run(initialize_tools())

# Bind tools to LLM
llm_with_tools = llm.bind_tools(mcp_tools)
tool_node = ToolNode(mcp_tools)

# -------------------------------------------------
# 3. State
# -------------------------------------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------------------------------------
# 4. Chat Node - Let LLM interpret tool results
# -------------------------------------------------
async def chat_node(state: ChatState):
    """Main chat processing node - LLM processes both user input and tool results"""
    messages = [SYSTEM_PROMPT] + state["messages"]
    
    # Get LLM response (it will interpret tool results if present)
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}

# -------------------------------------------------
# 5. Checkpointer
# -------------------------------------------------
async def init_checkpointer():
    """Initialize SQLite checkpointer for conversation history"""
    conn = await aiosqlite.connect("chatbot.db")
    return AsyncSqliteSaver(conn)

checkpointer = asyncio.run(init_checkpointer())

# -------------------------------------------------
# 6. Graph Construction
# -------------------------------------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

def route_after_chat(state: ChatState):
    """Route to tools if LLM made tool calls, otherwise end"""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END

graph.add_edge(START, "chat_node")
graph.add_conditional_edges(
    "chat_node",
    route_after_chat,
    {"tools": "tools", END: END},
)
graph.add_edge("tools", "chat_node")  # Tool results go back to chat_node for interpretation

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------------------------------------
# 7. Thread Management
# -------------------------------------------------
async def retrieve_all_threads():
    """Get list of all conversation threads"""
    threads = set()
    async for cp in checkpointer.alist(None):
        threads.add(cp.config["configurable"]["thread_id"])
    return list(threads)

# -------------------------------------------------
# 8. Interactive Testing Mode
# -------------------------------------------------
async def interactive_test():
    """Interactive testing mode for the chatbot"""
    import uuid
    
    print("\n" + "="*60)
    print("🤖 MCP CHATBOT - INTERACTIVE TEST MODE")
    print("="*60)
    print("\nCommands:")
    print("  • Type your message and press Enter")
    print("  • Type 'new' to start a new conversation")
    print("  • Type 'threads' to list all threads")
    print("  • Type 'quit' or 'exit' to stop")
    print("="*60 + "\n")
    
    thread_id = str(uuid.uuid4())
    print(f"📝 Started new thread: {thread_id[:8]}...\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit']:
                print("\n👋 Goodbye!\n")
                break
            
            if user_input.lower() == 'new':
                thread_id = str(uuid.uuid4())
                print(f"\n📝 Started new thread: {thread_id[:8]}...\n")
                continue
            
            if user_input.lower() == 'threads':
                threads = await retrieve_all_threads()
                print(f"\n📋 Total threads: {len(threads)}")
                for t in threads[:5]:
                    print(f"  • {t}")
                if len(threads) > 5:
                    print(f"  ... and {len(threads) - 5} more")
                print()
                continue
            
            # Process message
            result = await chatbot.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config={"configurable": {"thread_id": thread_id}}
            )
            
            # Print response (only the final AI message)
            response = result["messages"][-1]
            if isinstance(response, AIMessage):
                print(f"\n🤖 Assistant: {response.content}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

async def automated_test():
    """Automated test with predefined questions"""
    import uuid
    
    print("\n" + "="*60)
    print("🧪 AUTOMATED TEST MODE")
    print("="*60 + "\n")
    
    thread_id = str(uuid.uuid4())
    
    test_questions = [
        "Hello! What can you help me with?",
        "What tools do you have access to?",
        # Add more test questions based on your MCP tools
        # For Salesforce: "What's my Salesforce username?"
        # For Salesforce: "Show me my Salesforce accounts"
        # For filesystem: "List files in the current directory"
        # For GitHub: "What are my recent GitHub repos?"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"Test {i}: {question}")
        print("-" * 60)
        
        try:
            result = await chatbot.ainvoke(
                {"messages": [HumanMessage(content=question)]},
                config={"configurable": {"thread_id": thread_id}}
            )
            
            response = result["messages"][-1]
            if isinstance(response, AIMessage):
                print(f"Response: {response.content}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    print("="*60)
    print("✅ Automated tests completed")
    print("="*60 + "\n")

# -------------------------------------------------
# 9. Main Entry Point
# -------------------------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Run automated tests
        asyncio.run(automated_test())
    else:
        # Run interactive mode (default)
        asyncio.run(interactive_test())
