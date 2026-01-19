# 🤖 MCP-Powered AI Assistant

A modular, extensible **AI assistant built with LangGraph and Model Context Protocol (MCP)** that can interact with multiple systems such as **Salesforce**, **GitHub**, and the **local filesystem** — all through natural language.

This project demonstrates how to build a **tool-aware, stateful AI agent** that:

* Chooses tools intelligently
* Avoids unnecessary tool calls
* Handles large tool outputs safely
* Scales cleanly as new MCP servers are added

---

## ✨ Key Features

* 🧠 **Tool-aware reasoning** using LangGraph
* 🔌 **Multi-MCP support**

  * Salesforce MCP
  * GitHub MCP
  * Filesystem MCP
* 🔄 **Stateful conversations** with thread persistence
* 🛑 **Safe handling of large outputs** (filesystem guards, truncation)
* 💬 **Natural responses** (no raw JSON unless requested)
* 🌐 **Simple UI** (single `index.html`, no frontend framework)
* 🧩 **Easily extensible** — add new MCP servers without rewriting logic

---

## 🏗️ Architecture Overview

```
User
 ↓
Frontend (index.html)
 ↓
Flask API
 ↓
LangGraph State Machine
 ↓
LLM (OpenAI / Gemini)
 ↓
MCP Tool Nodes
 ├── Salesforce MCP
 ├── GitHub MCP
 └── Filesystem MCP
```

Key design principles:

* **Frontend is MCP-agnostic**
* **Backend decides when to use tools**
* **Tool outputs are summarized before reaching the user**
* **Unbounded tools (filesystem) are sandboxed**

---

## 📁 Project Structure

```
.
├── app_flask.py                  # Flask backend
├── mcp_chatbot_backend.py        # LangGraph + MCP logic
├── templates/index.html          # Frontend UI (single file)
├── chatbot.db                    # SQLite checkpointer (auto-created)
├── .env                          # Environment variables
└── README.md
```

---

## 🚀 Supported MCP Servers

### ☁️ Salesforce MCP

Examples:

* Get Salesforce username
* List orgs
* Query accounts with SOQL
* Deploy / retrieve metadata

### 🐙 GitHub MCP

Examples:

* Search repositories
* Read files from repos
* Create issues & pull requests
* List commits and issues

> ⚠️ GitHub MCP does **not** expose authenticated user identity (`who am I`) by design.

### 📁 Filesystem MCP

Examples:

* List directories
* Read/write files
* Search files
* Show directory structure (with safety limits)

> Large filesystem outputs are intentionally restricted to avoid token overflows.

---

## 🛡️ Safety & Design Choices

* ❌ No raw filesystem dumps
* ❌ No unbounded directory trees
* ❌ No tool spam on greetings
* ✅ Intent-based tool gating
* ✅ Output truncation for large responses
* ✅ Clear user guidance for narrowing queries

---

## 🧪 Example Prompts

```
Hello
What can you help me with?
Get my Salesforce username
Show my Salesforce accounts
Search GitHub repositories for langgraph
List top-level folders in this directory
Search files named *.py
```

---

## 🛠️ Setup Instructions

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/mcp-ai-assistant.git
cd mcp-ai-assistant
```

---

### 2️⃣ Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
```

---

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Configure environment variables

Create a `.env` file:

```env
OPEN_AI_API_KEY=your_openai_key
GITHUB_TOKEN=your_github_pat
```

> Salesforce authentication is handled via Salesforce CLI (`sf`).


---

### 5️⃣ Authenticate Salesforce (Required for Salesforce MCP)

Salesforce MCP uses the **Salesforce CLI (`sf`)** for authentication.
You must authenticate at least one Salesforce org before MCP tools can access Salesforce data.

---

#### 🔹 Step 1: Install Salesforce CLI

Install the Salesforce CLI using npm:

```bash
npm install -g @salesforce/cli
```

Verify installation:

```bash
sf --version
```

---

#### 🔹 Step 2: Log in to your Salesforce org

Authenticate using a browser-based login:

```bash
npx sf org login web
```

This will:

* Open your default browser
* Prompt you to log in to Salesforce
* Store the authenticated org locally for CLI and MCP use

This works with **Developer**, **Sandbox**, and **Production** orgs.

---

#### 🔹 Step 3: Verify authenticated orgs

List all logged-in orgs:

```bash
npx sf org list
```

The org marked as **default / target-org** will be used automatically by Salesforce MCP.

---

#### 🔹 Step 4: (Optional) Set a default target org

If multiple orgs are authenticated, explicitly set one as default:

```bash
npx sf config set target-org=your_username@force.com --global
```

Verify:

```bash
npx sf config list
```

---

#### 🔹 Step 5: Confirm Salesforce MCP access

After authentication, Salesforce MCP can access your org.
You can verify this by running a simple query or asking the assistant:

```
What's my Salesforce username?
List all Salesforce accounts
```

If authentication is successful, real data from your Salesforce org will be returned.

---

#### ⚠️ Common Issues

**❌ `sf` not recognized**

* Restart the terminal after installation
* Ensure npm global binaries are in your PATH

**❌ Login fails in browser**

* Ensure pop-ups are allowed
* Try logging in manually at [https://login.salesforce.com](https://login.salesforce.com)

**❌ MCP authentication errors**

* Run `npx sf org list` to confirm login
* Re-authenticate using `npx sf org login web`

---

#### 🔐 Security Notes

* Salesforce credentials are managed **entirely by Salesforce CLI**
* No credentials are stored in this project
* Salesforce MCP uses your local CLI authentication context

---

Once Salesforce CLI authentication is complete, Salesforce MCP tools are ready to use.

---


### 6️⃣ Run the chatbot

```bash
python app_flask.py
```
---

## 🧩 Extending the Assistant

Adding a new MCP server is straightforward:

1. Add it to `MCP_SERVERS` in `mcp_chatbot_backend.py`
2. Restart the backend
3. (Optional) Update the sidebar UI to reflect the new server

No changes to routing logic required.

---

## 📌 Known Limitations

* GitHub MCP does not expose authenticated user identity
* Filesystem operations are intentionally limited for safety
* Large outputs are summarized or truncated
* This is a single-user demo setup (not multi-tenant)

---

## 🧠 Why This Project Matters

This project goes beyond “chat with tools” demos and shows:

* How to build **real agent state**
* How to control **tool explosion**
* How to design **MCP-agnostic systems**
* How to safely expose powerful tools to LLMs

It’s a solid foundation for:

* Internal developer assistants
* Ops / DevOps copilots
* Enterprise AI tooling
* Research into agent architectures

---

## 📜 License

MIT License — feel free to use, modify, and extend.

---
