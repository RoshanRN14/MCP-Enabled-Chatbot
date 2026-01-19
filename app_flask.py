from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import asyncio
import uuid
import os
import threading

from langchain_core.messages import HumanMessage
from mcp_chatbot_backend import chatbot, retrieve_all_threads

# -------------------------------------------------
# Global event loop for async operations
# -------------------------------------------------
_loop = None
_loop_thread = None
_chatbot = None

def get_or_create_loop():
    """Get or create a persistent event loop running in a background thread"""
    global _loop, _loop_thread
    
    if _loop is None or not _loop.is_running():
        _loop = asyncio.new_event_loop()
        
        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        
        _loop_thread = threading.Thread(target=run_loop, daemon=True)
        _loop_thread.start()
    
    return _loop

def run_async(coro):
    """Run async code using the persistent event loop"""
    loop = get_or_create_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)  # 30 second timeout

async def get_or_create_chatbot():
    global _chatbot
    if _chatbot is None:
        _chatbot = chatbot 
    return _chatbot


# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
CORS(app)

def get_thread_id():
    """Get or create thread ID for session"""
    if "thread_id" not in session:
        session["thread_id"] = str(uuid.uuid4())
    return session["thread_id"]

# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json or {}
        user_message = data.get("message", "").strip()
        thread_id = data.get("thread_id") or get_thread_id()

        if not user_message:
            return jsonify({"success": False, "error": "No message provided"}), 400

        # Get chatbot and invoke
        async def process_message():
            bot = await get_or_create_chatbot()
            result = await bot.ainvoke(
                {"messages": [HumanMessage(content=user_message)]},
                config={"configurable": {"thread_id": thread_id}},
            )
            return result
        
        result = run_async(process_message())
        last_msg = result["messages"][-1]

        return jsonify({
            "success": True,
            "response": last_msg.content,
            "thread_id": thread_id,
            "discovered_username": result.get("discovered_username"),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/threads", methods=["GET"])
def get_threads():
    try:
        threads = run_async(retrieve_all_threads())
        return jsonify({
            "success": True,
            "threads": [{"id": t} for t in threads]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/new-thread", methods=["POST"])
def new_thread():
    thread_id = str(uuid.uuid4())
    session["thread_id"] = thread_id
    return jsonify({
        "success": True,
        "thread_id": thread_id
    })

@app.route("/api/history/<thread_id>", methods=["GET"])
def get_history(thread_id):
    """Get conversation history from checkpointer"""
    try:
        async def fetch_history():
            bot = await get_or_create_chatbot()
            # Get state from checkpointer
            state = await bot.aget_state({"configurable": {"thread_id": thread_id}})
            if state and state.values:
                messages = state.values.get("messages", [])
                return [
                    {
                        "role": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                        "content": msg.content
                    }
                    for msg in messages
                ]
            return []
        
        history = run_async(fetch_history())
        return jsonify({
            "success": True,
            "history": history,
            "thread_id": thread_id
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/clear/<thread_id>", methods=["DELETE"])
def clear_thread(thread_id):
    """Note: LangGraph checkpointer doesn't support deletion easily"""
    return jsonify({
        "success": False,
        "message": "Thread clearing not supported. Create a new thread instead."
    }), 501

# -------------------------------------------------
# Startup: Initialize chatbot
# -------------------------------------------------
@app.before_request
def ensure_chatbot():
    """Ensure chatbot is initialized before first request"""
    global _chatbot
    if _chatbot is None:
        try:
            run_async(get_or_create_chatbot())
            print("✅ Chatbot initialized successfully")
        except Exception as e:
            print(f"⚠️  Chatbot initialization deferred: {e}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Starting Salesforce MCP Chatbot")
    print("="*60)
    
    # Initialize event loop and chatbot
    print("Initializing chatbot...")
    try:
        run_async(get_or_create_chatbot())
        print("✅ Chatbot ready!")
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("Chatbot will initialize on first request")
    
    print("="*60)
    print("🌐 Server starting on http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)
