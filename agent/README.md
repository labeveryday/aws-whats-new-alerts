# AWS Newsletter Agent

Strands agent that generates AWS newsletters focused on Agentic AI and AI/ML announcements.

## Features

- 🎯 **Agentic AI Focus** - Prioritizes AgentCore, Strands, MCP, Kiro, A2A, Claude
- 📰 **Browse vs Publish** - View news or send newsletters on demand
- 🧠 **Per-User Memory** - Remembers name, preferences, newsletter history
- 🔄 **Self-Scheduling** - Discovers own ARN and creates EventBridge schedules
- 📧 **Email Delivery** - Professional newsletters via SNS

## Architecture

```mermaid
graph TD
    User[User] -->|JWT| Runtime[AgentCore Runtime]
    Runtime -->|Execute| Agent[Strands Agent]

    Agent -->|Retrieve Context| Memory[AgentCore Memory]
    Agent -->|Save Events| Memory

    subgraph Tools
        News[fetch_aws_news]
        SNS[publish_to_newsletter_topic]
        Schedule[manage_eventbridge_schedule]
        Find[find_agent_id]
    end

    Agent --> Tools
```

## Usage Modes

### Browse Mode
```
User: "What's new in AWS today?"
Agent: Shows summary, asks if you want to publish
```

### Publish Mode
```
User: "Send me a newsletter"
Agent: Generates, sends email, confirms with timestamp
       "Newsletter sent on November 27, 2025 at 1:15 PM EST"
```

### Memory Recall
```
User: "What's the most recent newsletter you sent me?"
Agent: Recalls date, subject, and content summary
```

## Deployment

```bash
# Source config
source agent_config.env

# Configure
agentcore configure -e agent.py \
  --region $AWS_REGION \
  --name $AGENT_NAME \
  --execution-role $AGENTCORE_RUNTIME_ROLE_ARN

# Deploy
agentcore launch --env SECRET_NAME=$SECRET_NAME --env AWS_REGION=$AWS_REGION
```

## Memory Integration

The agent uses `LongTermMemoryHookProvider` (in `memory_hooks.py`) for persistent memory:

| Event | Action |
|-------|--------|
| `MessageAddedEvent` | Retrieves relevant context from memory |
| `AfterInvocationEvent` | Saves conversation to memory |

### Memory Namespaces

| Namespace | Purpose |
|-----------|---------|
| `/newsletter/articles/{userId}` | Article URLs for deduplication |
| `/newsletter/preferences/{userId}` | User preferences and history |

### Per-User Isolation

JWT `sub` claim from Cognito becomes the `actor_id`, ensuring each user has isolated memory.

## Tools

| Tool | Purpose |
|------|---------|
| `fetch_aws_news` | Fetches AWS What's New RSS feed |
| `publish_to_newsletter_topic` | Sends email via SNS |
| `manage_eventbridge_schedule` | Creates/updates schedules |
| `find_agent_id` | Self-discovery for scheduling |
| `current_time` | Gets current date/time |

## Configuration

Loaded from Secrets Manager at runtime via `secrets_loader.py`:

| Variable | Purpose |
|----------|---------|
| `SNS_TOPIC_ARN` | Email delivery |
| `BEDROCK_AGENTCORE_MEMORY_ID` | Memory store |
| `AGENT_NAME` | Self-discovery |
| `SCHEDULER_ROLE_ARN` | EventBridge permissions |

## Files

```
agent/
├── agent.py              # Main agent with system prompt
├── memory_hooks.py       # Long-term memory integration
├── secrets_loader.py     # Secrets Manager loader
├── requirements.txt      # Dependencies
└── tools/
    ├── aws_news_tools.py   # RSS fetching
    ├── sns_tools.py        # Email publishing
    └── create_events.py    # Scheduling + self-discovery
```

## Troubleshooting

### Memory Not Saving
- Check CloudWatch logs for "Successfully saved event to memory"
- Ensure JWT has valid `sub` claim
- Wait a few minutes for memory extraction

### Newsletter Not Received
- Confirm SNS subscription (check email)
- Verify `SNS_TOPIC_ARN` in Secrets Manager
- Check agent has `sns:Publish` permission

### View Logs
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow
```
