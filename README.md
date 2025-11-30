# AWS What's New Alerts - Datadog Tracing Demo

**Local development setup** for testing Datadog tracing integration. Deploys AWS infrastructure (Memory, SNS) but runs the agent **locally** for easy debugging and tracing.

Built with AWS Bedrock AgentCore, Strands Agents SDK, and CDK. Features a **multi-agent architecture** with an orchestrator and specialized sub-agents for enhanced link extraction.

## Purpose

Test Datadog tracing of Strands agents with AgentCore Memory integration. Agent runs locally on your machine while using AWS services (Memory, SNS, EventBridge).

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
- Python 3.10+
- AWS CDK: `npm install -g aws-cdk`
- AWS credentials configured: `aws configure`

### Setup (One-Time)

**Deploy Infrastructure**
```bash
./deploy.sh --email your-email@example.com
```

This creates:
- AgentCore Memory (semantic deduplication)
- SNS Topic (email delivery)
- Secrets Manager (configuration)
- IAM Roles

**Confirm Email**
Check your inbox and confirm the SNS subscription.

### Run Agent Locally

**Terminal 1: Start Agent**
```bash
cd agent
./run.sh
```

>NOTE: Add your datadog env in the agent.py before running

**Terminal 2: Chat with Agent**
```bash
python local_chat_invoke.py
```

The agent runs on `localhost:8080` and uses your AWS credentials to access Memory, SNS, and other services.

## Testing

### Example Prompts
```
You: What's new in AWS AI today?
You: Generate and send a newsletter about AWS AI news
You: Schedule yourself for 8 AM daily
```

Type `quit`, `exit`, or `bye` to exit.

### What Gets Traced

- Multi-turn conversations with tool calls
- Sub-agent invocations (blog reader)
- AgentCore Memory operations (semantic search + storage)
- External API calls (RSS feeds, blog fetching)
- AWS service calls (SNS, EventBridge, Secrets Manager)

## Project Structure

```
aws-whats-new-alerts/
├── agent/
│   ├── agent.py                # Orchestrator agent
│   ├── memory_hooks.py         # Memory integration
│   ├── secrets_loader.py       # Config loader
│   └── tools/
│       ├── aws_news_tools.py   # RSS fetching
│       ├── link_extractor.py   # Link extraction
│       ├── blog_reader.py      # Sub-agent
│       ├── sns_tools.py        # Email publishing
│       └── create_events.py    # Scheduling
├── backend/
│   ├── newsletter_stack.py     # CDK infrastructure
│   └── configure_secret.py     # Secrets setup
├── deploy.sh                   # One-command deployment
└── local_chat_invoke.py        # Local testing
```

## Operations

### Update Agent
Restart `./run.sh` to pick up code changes.

### View Logs
Logs stream to the terminal running `./run.sh`.

### Cleanup
```bash
./destroy.sh
```

## Memory

The agent uses AgentCore Memory with:
- **Actor ID**: `aws_newsletter_bot`
- **Session ID**: `aws-newsletter-main-session`
- **Namespaces**: `/newsletter/articles` (deduplication), `/newsletter/preferences` (user info)

Memory persists across restarts and conversations.

## License

2025 Amazon Web Services, Inc.
