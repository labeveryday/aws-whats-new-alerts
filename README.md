# AWS What's New Alerts

**Fully autonomous AI newsletter system** that generates and delivers daily email digests about AWS announcements, with a focus on AI/ML updates.

Built with AWS Bedrock AgentCore, Strands AI framework, and CDK Infrastructure as Code.

## 🎯 What This Does

- 🤖 **Fully Autonomous** - Runs daily via EventBridge Scheduler
- 🔍 **Smart Filtering** - Focuses on AI/ML announcements (Bedrock, SageMaker, Claude, AgentCore)
- 🧠 **Semantic Memory** - Remembers processed articles, prevents duplicates (30-day expiry)
- 📧 **Professional Formatting** - ASCII-bordered newsletters with ranked announcements
- 📨 **Email Delivery** - Delivers via Amazon SNS to subscribers
- 💬 **Web Chat UI** - Clean, authenticated web interface to chat with the agent (Markdown supported)
- 🔒 **Secure Configuration** - Uses AWS Secrets Manager for zero-touch deployment
- ⚡ **Robust Architecture** - Uses Lambda Function URL to handle long-running generation tasks (5 min timeout support)
- 🛡️ **Bank-Grade Security** - Chat Proxy validates Cognito JWTs, blocking unauthorized access

## 🚀 Quick Start

### Prerequisites
- AWS Account with Bedrock AgentCore access
- Python 3.10+ in virtual environment: `source .venv/bin/activate`
- AWS CDK CLI: `npm install -g aws-cdk`
- Docker Desktop (required for bundling Lambda dependencies)

### 1. Deploy Infrastructure (5-10 minutes)
```bash
cd backend

# Bootstrap CDK (first time only per account/region)
cdk bootstrap

# Deploy all resources (Backend + Frontend)
# This will use Docker to bundle secure dependencies
cdk deploy --context email=your-email@example.com
# ⏱️ Wait for deployment to complete
```

**Creates:** SNS Topic, AgentCore Memory, IAM roles, Secrets Manager, **Cognito Auth**, **CloudFront/S3 Hosting**, and **Secure Lambda Function URL** for chat proxy.

### 2. Configure Agent Secrets
Push configuration securely to AWS Secrets Manager:

```bash
python configure_secret.py --email your-email@example.com
```

>NOTE: You will need to get the AGENTCORE_RUNTIME_ROLE_ARN from .env and use it when you launch the agent. This contains all the permissions for your agent.

### 3. Deploy Agent (2 minutes)
```bash
cd ../agent

# Configure agent (builds the artifact)
agentcore configure -e agent.py --region us-west-2

# Launch to AWS
agentcore launch
```

### 4. Deploy Frontend (1 minute)
Generates config and uploads the Chat UI to S3.

```bash
cd ../backend
python deploy_frontend.py
```
Open the printed CloudFront URL to chat with your agent!

### 5. Autonomous Self-Scheduling (The "Magic" Step)
Ask the agent to set up its own schedule via the chat interface or CLI. It will discover its own ARN and configure EventBridge autonomously.

**Via CLI:**
```bash
cd ..
python invoke_agent.py --prompt "Setup your daily schedule for 8 AM"
```

**Via Web UI:**
Just type: "Set up daily newsletter delivery at 8 AM"

The agent will:
1. Autonomously discover its own Agent ID (`find_agent_id` tool)
2. Create the EventBridge schedule (`manage_eventbridge_schedule` tool)
3. Confirm the schedule is active

---

## 📁 Project Structure

```
aws-whats-new-alerts/
├── agent/                         # AI Agent
│   ├── agent.py                   # Main agent (loads config from Secrets Manager)
│   ├── secrets_loader.py          # Helper to fetch secrets
│   ├── tools/                     # Custom tools
│   │   ├── aws_news_tools.py      # AWS RSS feed parser
│   │   ├── create_events.py       # EventBridge Scheduler management (Self-Scheduling)
│   │   └── sns_tools.py           # SNS publish/subscribe
│   └── requirements.txt
├── backend/                       # CDK Infrastructure
│   ├── app.py                     # CDK entry point
│   ├── newsletter_stack.py        # Complete stack (SNS + Memory + Secrets + Frontend + Lambda)
│   ├── configure_secret.py        # Config script (pushes to Secrets Manager)
│   ├── deploy_frontend.py         # Deploys Chat UI to S3 & Invalidates CloudFront
│   └── lambda/                    # Lambda Functions
│       ├── chat_proxy.py          # Secure Proxy (Validates JWT, handles timeout)
│       └── requirements.txt       # Proxy dependencies (python-jose, requests)
├── frontend/                      # Web Chat UI
│   ├── index.html                 # Single-page chat app (Tailwind + Markdown + Cognito)
│   └── config.js                  # Generated config
├── invoke_agent.py                # Manual testing script
└── requirements.txt
```

---

## 🔧 Configuration

### Content Filtering
- **Default**: AI/ML-focused (Bedrock, Claude, SageMaker, AgentCore, ML, AI workflows)
- **Override**: Say "all announcements" for broader AWS news

### Time Frames
Agent responds to natural language:
- `"last 24 hours"` (default)
- `"yesterday"` / `"last 3 days"`
- `"last week"` / `"last month"`

---

## 🧪 Testing & Debugging

### Manual Invocation
```bash
# Test deployed agent
python invoke_agent.py --prompt "Generate newsletter for yesterday"
```

### CloudWatch Logs
```bash
# Tail agent runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow --region us-west-2
```

### Secret Management
To update configuration (e.g., change email or region), simply run the config script again:
```bash
cd backend
python configure_secret.py --email new-email@example.com
```
No need to redeploy the agent code for configuration changes!

---

## 🧠 How Memory Works

1. **Agent queries memory on startup**: "What AWS articles have been processed?"
2. **Fetches latest news** from aws.amazon.com/new/
3. **Cross-references** with memory to identify NEW vs DUPLICATE articles
4. **Sends newsletter** with only new articles
5. **Memory automatically extracts** article URLs/dates from agent response for future deduplication
6. **Events expire after 30 days** (automatic cleanup)

---

## 🛠️ Common Operations

### Update Agent Code
```bash
cd agent
# Edit agent.py
agentcore configure -e agent.py
agentcore update # or agentcore deploy --rebuild
```

### Destroy Everything
```bash
cd backend
cdk destroy
```
