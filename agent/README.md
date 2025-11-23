# AWS Newsletter Agent

A fully autonomous AI agent built with AWS Bedrock AgentCore and Strands that generates and delivers daily email newsletters about AWS AI/ML announcements.

## Overview

This agent:
- **Fetches** AWS news from https://aws.amazon.com/new/
- **Filters** for AI/ML-related content (or broader coverage on request)
- **Deduplicates** using AgentCore semantic memory
- **Formats** professional ASCII-bordered newsletters with numbered announcements
- **Delivers** via Amazon SNS email subscriptions
- **Chats** via secure, authenticated Web UI
- **Configures Itself** using AWS Secrets Manager and AgentCore discovery

## Architecture

```
Secrets Manager (Config) ←────────┐
                                  │
EventBridge Scheduler ────────→ Bedrock AgentCore Runtime
                                  │
                            Agent execution
                                  │
       ┌──────────────────────────┼────────────────────────────┐
       ↓                          ↓                            ↓
 Strands Agent (agent.py)   AgentCore Memory (Semantic)    SNS Topic
       ↓                          ↓                            ↓
 AWS News Feed              Deduplication               Email subscribers
      ↑
      │
Web Chat UI (S3/CloudFront)
      │
Cognito Auth -> Lambda Function URL (Proxy) -> AgentCore Runtime
```

## Deployment

### 1. Deploy Infrastructure
First, deploy the backend resources (SNS, IAM Roles, Memory, Secrets) using CDK.

```bash
cd ../backend
cdk deploy --context email=your-email@example.com
```

### 2. Configure Secrets
Instead of local `.env` files, we push configuration securely to AWS Secrets Manager.

```bash
python configure_secret.py --email your-email@example.com
```

### 3. Deploy Agent
Deploy the agent to AgentCore Runtime.

```bash
cd ../agent
agentcore configure -e agent.py --region us-west-2
agentcore launch
```

### 4. Autonomous Self-Scheduling (The "Magic" Step)
Ask the agent to set up its own schedule.

1. Send the command via Chat or CLI:
   > "Setup your daily schedule for 8 AM."
   
2. The agent will:
   - Autonomously discover its own Agent ID (`find_agent_id`)
   - Create the EventBridge schedule (`manage_eventbridge_schedule`)
   - Confirm the schedule is active

## Configuration

The agent loads its configuration from AWS Secrets Manager at startup via `secrets_loader.py`.

**Configured Variables (in Secrets Manager):**
- `SNS_TOPIC_ARN`: For email delivery
- `BEDROCK_AGENTCORE_MEMORY_ID`: For deduplication
- `AGENT_NAME`: For self-discovery ("aws_newsletter_bot")
- `NEWSLETTER_EMAIL`: Default recipient

To update configuration, simply re-run `backend/configure_secret.py` with new parameters.

## Agent Capabilities

### Tools
- **http_request** (Strands built-in) - Fetches AWS news feed
- **current_time** (Strands built-in) - Gets current date
- **publish_message** (custom) - Sends emails via SNS
- **manage_eventbridge_schedule** (custom) - Creates/Updates execution schedules
- **find_agent_id** (custom) - Self-discovery tool for agent identity

### Self-Discovery Pattern
This agent implements a "Self-Aware" pattern to solve infrastructure circular dependencies:
1. Agent needs its own ARN to create a schedule.
2. ARN doesn't exist until after deployment.
3. **Solution**: Agent uses `find_agent_id` tool at runtime to look up "aws_newsletter_bot" and retrieve its own ARN dynamically.
4. **Benefit**: Zero manual configuration or post-deployment env var updates required.

### Direct Invocation & Proxying
The agent supports **Direct Invocation** via a secure Lambda Function URL proxy (`backend/lambda/chat_proxy.py`). This architecture:
1. **Bypasses API Gateway Timeouts**: Allows for long-running generations (up to 5 minutes).
2. **Secures Access**: The proxy manually validates Cognito JWT tokens, ensuring only authenticated users can invoke the agent.
3. **Handles CORS**: Allows the frontend (hosted on S3/CloudFront) to communicate securely.

## File Structure

```
agent/
├── agent.py                    # Main agent code (production)
├── secrets_loader.py           # Helper to load config from Secrets Manager
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── tools/                      # Custom tools (auto-loaded)
│   ├── aws_news_tools.py       # AWS news fetching tools
│   ├── create_events.py        # EventBridge scheduling tools
│   └── sns_tools.py            # SNS publish/subscribe tools
└── .bedrock_agentcore/         # AgentCore deployment config
```

## Troubleshooting

### Agent Not Creating Memory Records
**Symptom**: Day 2 doesn't skip duplicates from Day 1

**Causes**:
1. Agent not mentioning article URLs in response
2. Semantic extraction prompt not configured in CDK
3. Memory provisioning incomplete (wait 5min after CDK deploy)

### Email Not Received
**Symptom**: Agent runs successfully but no email arrives

**Causes**:
1. SNS subscription not confirmed (check email for confirmation link)
2. Secrets Manager not configured (run `configure_secret.py`)
3. IAM role lacks SNS publish permissions

**Fix**:
```bash
# Check logs for "Configuration Loaded" message
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow
```

## License

© 2025 Amazon Web Services, Inc.
