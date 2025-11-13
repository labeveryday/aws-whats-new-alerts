# AWS What's New Alerts

**Fully autonomous AI newsletter system** that generates and delivers daily email digests about AWS announcements, with a focus on AI/ML updates.

Built with AWS Bedrock AgentCore, Strands AI framework, and CDK Infrastructure as Code.

## 🎯 What This Does

- 🤖 **Fully Autonomous** - Runs daily at 6 AM EST via EventBridge Scheduler
- 🔍 **Smart Filtering** - Focuses on AI/ML announcements (Bedrock, SageMaker, Claude, AgentCore)
- 🧠 **Semantic Memory** - Remembers processed articles, prevents duplicates (30-day expiry)
- 📧 **Professional Formatting** - ASCII-bordered newsletters with ranked announcements
- 📨 **Email Delivery** - Delivers via Amazon SNS to subscribers

## 🚀 Quick Start

### Prerequisites
- AWS Account with Bedrock AgentCore access
- Python 3.10+ in virtual environment: `source .venv/bin/activate`
- AWS CDK CLI: `npm install -g aws-cdk`

### 1. Deploy Infrastructure (5 minutes)
```bash
cd backend

# Bootstrap CDK (first time only per account/region)
cdk bootstrap

# Deploy SNS + Memory + IAM roles
cdk deploy --context email=your-email@example.com

# Generate .env from stack outputs
python generate_env.py

# ⏱️ Wait 2-5 minutes for AgentCore Memory to provision
```

**Creates:** SNS Topic, AgentCore Memory (semantic deduplication), IAM roles

### 2. Test Agent Locally (Optional but Recommended)
```bash
cd ../agent

# Run agent locally
python agent.py --port 8080

# In another terminal, test it
cd ..
python local_chat_client.py
```

This lets you iterate quickly without deploying to AgentCore.

### 3. Deploy Agent (2 minutes)
```bash
cd agent

# Configure agent
agentcore configure -e agent.py --region us-west-2

# Launch to AWS
agentcore launch

# Copy the agent ARN from output
```

**Agent Configuration:**
- Name: `newsletter_agent`
- Execution Role: Use `AGENTCORE_RUNTIME_ROLE_ARN` from `.env`
- Region: Must match your CDK deployment

**Add agent ARN to .env:**
```bash
cd ..
# Edit .env and add:
# AGENTCORE_ARN=arn:aws:bedrock-agentcore:region:account:runtime/id
```

### 4. Test Manually
```bash
python invoke_agent.py --prompt "Generate daily AWS AI/ML newsletter for the last 24 hours"
```

Check your email! Newsletter arrives in ~15 seconds.

⚠️ **CRITICAL**: Click SNS subscription confirmation link in your email first, or emails will silently fail.

### 5. Enable Autonomous Operation (Optional)
```bash
cd backend

# Deploy EventBridge Scheduler for daily execution
cdk deploy --context email=your-email@example.com \
           --context agentcore_arn=$(grep AGENTCORE_ARN ../.env | cut -d'=' -f2) \
           --context enable_scheduler=true

# Regenerate .env to include scheduler config
python generate_env.py
```

**Adds:** EventBridge Scheduler (6 AM EST daily), IAM role, SQS Dead Letter Queue

---

## 📁 Project Structure

```
aws-whats-new-alerts/
├── agent/                         # AI Agent
│   ├── agent.py                   # Main agent (memory + newsletter logic)
│   ├── tools/                     # Custom tools (auto-loaded)
│   │   └── sns_tools.py          # SNS publish/subscribe
│   └── requirements.txt
├── backend/                       # CDK Infrastructure
│   ├── app.py                     # CDK entry point
│   ├── newsletter_stack.py        # Complete stack (SNS + Memory + EventBridge + DLQ)
│   ├── generate_env.py            # Auto-generate .env from CloudFormation
│   └── requirements.txt
├── invoke_agent.py                # Manual testing script
├── local_chat_client.py           # Local development client
└── .env                           # Auto-generated config
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

### Schedule
**Default**: 6 AM EST (11 AM UTC) daily

**Change**: Edit `backend/newsletter_stack.py` line 244:
```python
schedule_expression="cron(0 11 * * ? *)"  # 6 AM EST
```

---

## 🧪 Testing & Debugging

### Local Testing (Fast Iteration)
```bash
# Terminal 1: Run agent locally
cd agent && python agent.py --port 8080

# Terminal 2: Test with client
python local_chat_client.py
```

### Manual Invocation
```bash
# Test deployed agent
python invoke_agent.py --prompt "Generate newsletter for yesterday"

# Interactive conversation mode
python invoke_agent.py
```

### CloudWatch Logs
```bash
# Tail agent runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow --region us-west-2

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/bedrock-agentcore/runtimes/ \
    --filter-pattern "ERROR" \
    --region us-west-2

# Check EventBridge Scheduler failures
aws sqs receive-message \
    --queue-url $(grep SCHEDULER_DLQ_URL .env | cut -d'=' -f2) \
    --region us-west-2
```

### Memory Validation
```bash
cd validation
python validate_memory.py --memory-id $(grep MEMORY_ID ../.env | cut -d'=' -f2)
```

---

## 🧠 How Memory Works

1. **Agent queries memory on startup**: "What AWS articles have been processed?"
2. **Fetches latest news** from aws.amazon.com/new/
3. **Cross-references** with memory to identify NEW vs DUPLICATE articles
4. **Sends newsletter** with only new articles
5. **Memory automatically extracts** article URLs/dates from agent response for future deduplication
6. **Events expire after 30 days** (automatic cleanup)

**Memory Namespaces:**
- `/newsletter/facts` - Semantic extraction of article metadata
- `/newsletter/articles` - Additional article storage
- `/newsletter/preferences` - User preferences

---

## 🛠️ Common Operations

### Update Agent
```bash
cd agent
# Edit agent.py
agentcore update
```

### View Stack Outputs
```bash
cd backend
aws cloudformation describe-stacks --stack-name aws-newsletter-prod \
    --query 'Stacks[0].Outputs' --output table --region us-west-2
```

### Regenerate .env
```bash
cd backend
python generate_env.py --region us-west-2
```

### Destroy Everything
```bash
cd backend
cdk destroy
```

---

## 🚨 Troubleshooting

### No emails received
1. ✅ Check SNS subscription confirmed (click email link)
2. ✅ Check spam folder
3. ✅ Verify SNS_TOPIC_ARN in `.env` matches stack output
4. ✅ Check CloudWatch logs for errors

### "Memory not found" error
- Wait 5 minutes after `cdk deploy` for memory provisioning
- Verify `BEDROCK_AGENTCORE_MEMORY_ID` in `.env`

### Region mismatch errors
- All services must be in same region (CDK, agent, memory)
- Default is `us-west-2` - check `.env` AWS_REGION
- Regenerate `.env` if you deployed to different region

### EventBridge not triggering
- Check schedule is `ENABLED` in EventBridge console
- Verify `AGENTCORE_ARN` was provided during scheduler deployment
- Check Dead Letter Queue for failures

### Duplicate articles in newsletter
- Memory takes 24-48 hours to fully index after first run
- Check memory validation: `cd validation && python validate_memory.py`

---

## 📝 Environment Variables

Auto-generated by `backend/generate_env.py` from CloudFormation outputs:

```bash
AWS_REGION=us-west-2                        # Deployment region
AWS_ACCOUNT_ID=123456789012                 # Your AWS account
SNS_TOPIC_ARN=arn:aws:sns:...              # Email delivery
BEDROCK_AGENTCORE_MEMORY_ID=memory-id      # Deduplication
BEDROCK_AGENTCORE_MEMORY_ARN=arn:aws:...   # Memory ARN
AGENTCORE_RUNTIME_ROLE_ARN=arn:aws:iam:... # Runtime permissions
AGENTCORE_ARN=arn:aws:bedrock-agentcore:...# Agent runtime (add manually)

# EventBridge Scheduler (optional, added if enabled)
EVENTBRIDGE_SCHEDULE_NAME=aws-newsletter-daily-newsletter
EVENTBRIDGE_ROLE_ARN=arn:aws:iam:...
SCHEDULER_DLQ_ARN=arn:aws:sqs:...          # Dead letter queue
SCHEDULER_DLQ_URL=https://sqs...            # DLQ URL

# Agent Identity (for persistent memory sessions)
AGENT_ACTOR_ID=aws-newsletter-bot
AGENT_SESSION_ID=aws-newsletter-main-session
```

---

## 📚 Technical Details

### Stack Components
- **SNS Topic**: Email delivery to subscribers
- **AgentCore Memory**: 30-day semantic memory with custom extraction
- **S3 Bucket**: Newsletter archive storage (lifecycle: 90d→IA, 365d→Glacier)
- **IAM Roles**: Least-privilege access (AgentCore→SNS, EventBridge→AgentCore)
- **EventBridge Scheduler**: Daily cron trigger with retry policy
- **SQS DLQ**: Captures failed scheduler invocations (14-day retention)

### Dependencies
- `aws-cdk-lib>=2.80.0` - CDK framework
- `aws-cdk.aws-bedrock-agentcore-alpha` - AgentCore constructs (alpha)
- `strands-agents` - AI agent framework
- `boto3` - AWS SDK

For detailed technical documentation, see [CLAUDE.md](CLAUDE.md).
