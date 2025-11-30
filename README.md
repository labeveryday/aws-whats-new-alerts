# AWS What's New Alerts - Datadog Tracing Demo

**Simplified AgentCore agent** for testing Datadog tracing integration. This is a stripped-down version without authentication or frontend - just the core agent infrastructure with AgentCore memory and tools.

Built with AWS Bedrock AgentCore, Strands Agents SDK, and CDK. Features a **multi-agent architecture** with an orchestrator and specialized sub-agents for enhanced link extraction.

## Purpose

This branch is designed for Datadog engineers to test tracing of Strands agents running on AgentCore. It removes Cognito authentication and frontend complexity so you can focus purely on agent tracing.

## Features

- Multi-Agent Architecture - Orchestrator + sub-agent for intelligent link extraction
- Agentic AI Focus - Prioritizes AgentCore, Strands, MCP, Kiro, A2A, Claude
- Enhanced Links - Extracts documentation and GitHub links from announcements and blogs
- AgentCore Memory - Semantic deduplication of articles
- Email Delivery - Professional newsletters via SNS
- Self-Scheduling - Agent discovers its own ARN and creates EventBridge schedules

## Architecture

### Multi-Agent Design

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                        │
│                   (Strands + Sonnet)                         │
│                                                              │
│  Workflow: Fetch → Filter → Enhance → Format → Publish      │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌────────────┬────┴────┬─────────────┐
         ▼            ▼         ▼             ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │fetch_aws_│ │extract_  │ │read_blog_│ │publish_  │
   │  news    │ │links     │ │for_links │ │newsletter│
   └──────────┘ └──────────┘ └────┬─────┘ └──────────┘
      Tool         Tool           │          Tool
                            ┌─────▼─────┐
                            │ SUB-AGENT │
                            │ (Sonnet)  │
                            └───────────┘
                            Blog analysis
```

### System Overview (Simplified)

```
┌─────────────────────────────────────────────────────┐
│                 Agent Runtime                        │
│  ┌────────────────────────────────────────────────┐ │
│  │           AgentCore Runtime                     │ │
│  │  ┌────────────┐  ┌────────────┐                │ │
│  │  │Orchestrator│  │ Sub-Agent  │                │ │
│  │  │   Agent    │──│(Blog Reader)│               │ │
│  │  └─────┬──────┘  └────────────┘                │ │
│  │        │                                        │ │
│  │  ┌─────▼──────┐                                │ │
│  │  │   Tools    │                                │ │
│  │  └────────────┘                                │ │
│  └────────────────────────────────────────────────┘ │
└─────────┬─────────────────────────────────────────┬─┘
          │                                         │
    ┌─────▼─────┐                            ┌─────▼─────┐
    │  Memory   │                            │    SNS    │
    │(AgentCore)│                            │  (Email)  │
    └───────────┘                            └───────────┘
```

## Quick Start

### Prerequisites
- AWS Account with Bedrock AgentCore access
- Python 3.10+: `source .venv/bin/activate`
- AWS CDK: `npm install -g aws-cdk`
- AgentCore CLI: `pip install bedrock-agentcore-cli`

### Deployment

**1. Deploy Infrastructure**
```bash
cd backend
cdk bootstrap  # First time only
cdk deploy --context email=your-email@example.com
```

**2. Configure Secrets**
```bash
python configure_secret.py --email your-email@example.com
```

**3. Deploy Agent**
```bash
cd ../agent
source agent_config.env
agentcore configure -e agent.py \
  --region $AWS_REGION \
  --name $AGENT_NAME \
  --execution-role $AGENTCORE_RUNTIME_ROLE_ARN
agentcore launch --env SECRET_NAME=$SECRET_NAME --env AWS_REGION=$AWS_REGION
```

**4. Test the Agent**
```bash
python invoke_agent.py --prompt "What's new in AWS today?"
```

## Testing Datadog Tracing

The `invoke_agent.py` script provides both single-prompt and interactive chat modes with real-time streaming output.

### Single Prompt Mode
```bash
# Simple query
python invoke_agent.py --prompt "What AWS AI announcements happened today?"

# Generate newsletter (sends email)
python invoke_agent.py --prompt "Generate and send a newsletter about AWS AI news"

# Self-scheduling
python invoke_agent.py --prompt "Schedule yourself for 8 AM daily"
```

### Interactive Chat Mode
```bash
python invoke_agent.py
```

This opens an interactive session where you can have multi-turn conversations with the agent. Type `quit` to exit or `clear` to start a new session.

### Tracing Identifiers

For consistent tracing, these identifiers are fixed across all invocations:

| Identifier | Value | Source |
|------------|-------|--------|
| Session ID | `datadog-tracing-demo-session-0001` | `invoke_agent.py` |
| Actor ID | `aws_newsletter_bot` | Secrets Manager |

The agent exercises:
- Multi-turn conversation with tools
- Sub-agent invocation (blog reader)
- AgentCore Memory (semantic search + storage)
- External API calls (RSS, blog fetching)
- AWS service calls (SNS, EventBridge)

## Project Structure

```
aws-whats-new-alerts/
├── agent/
│   ├── agent.py              # Orchestrator agent
│   ├── memory_hooks.py       # Long-term memory integration
│   ├── secrets_loader.py     # Config loader
│   └── tools/
│       ├── aws_news_tools.py   # RSS fetching
│       ├── link_extractor.py   # Regex-based link extraction
│       ├── blog_reader.py      # Sub-agent for blog analysis
│       ├── sns_tools.py        # Email publishing
│       └── create_events.py    # Scheduling + self-discovery
├── backend/
│   ├── newsletter_stack.py   # CDK infrastructure
│   └── configure_secret.py   # Secrets setup
└── invoke_agent.py           # Invocation script
```

## Operations

### Update Agent
```bash
cd agent
agentcore launch --env SECRET_NAME=$SECRET_NAME --env AWS_REGION=$AWS_REGION
```

### View Logs
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow
```

### Destroy
```bash
cd backend
cdk destroy
```

## License

2025 Amazon Web Services, Inc.
