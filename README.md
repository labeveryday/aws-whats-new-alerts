# AWS What's New Alerts

**Fully autonomous AI newsletter system** that generates and delivers daily email digests about AWS announcements, with a focus on AI/ML updates.

Built with AWS Bedrock AgentCore, Strands AI framework, and CDK Infrastructure as Code.

## 🎯 What This Does

- 🤖 **Fully Autonomous** - Runs daily at 6 AM EST via EventBridge Scheduler
- 🔍 **Smart Filtering** - Focuses on AI/ML announcements (Bedrock, SageMaker, Claude, AgentCore, etc.)
- 🧠 **Semantic Memory** - Remembers processed articles, prevents duplicates
- 📧 **Professional Formatting** - ASCII-bordered newsletters with numbered announcements
- 📨 **Email Delivery** - Delivers via Amazon SNS to subscribers
- ⚙️ **Zero Maintenance** - Set it and forget it

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ EventBridge Scheduler (6 AM EST daily)                          │
│ "Generate daily AWS AI/ML newsletter for the last 24 hours"     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ AWS Bedrock AgentCore Runtime                                   │
│ - Invokes agent with memory context                             │
│ - Queries /newsletter/facts for processed articles              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Strands AI Agent (agent.py)                                     │
│ - Fetches AWS news (https://aws.amazon.com/new/)                │
│ - Filters for AI/ML content                                     │
│ - Cross-references with memory (deduplication)                  │
│ - Formats newsletter                                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐  ┌──────────────────────────────────────┐
│ AgentCore Memory │  │ Amazon SNS Topic                     │
│ - Semantic       │  │ - Email delivery to subscribers      │
│   extraction     │  │                                      │
│ - 30-day expiry  │  └──────────────────────────────────────┘
└──────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- AWS Account with Bedrock AgentCore access
- Python 3.10+
- AWS CDK CLI: `npm install -g aws-cdk`
- Virtual environment activated: `source .venv/bin/activate`

### 1️⃣ Deploy Infrastructure (5 minutes)
```bash
cd backend

# Bootstrap CDK (first time only, per account/region)
cdk bootstrap

# Deploy SNS, Memory, IAM roles
cdk deploy --context email=your-email@example.com

# Generate .env file from stack outputs
python generate_env.py

# ⏱️ Wait 2-5 minutes for AgentCore Memory to provision
```

**What this creates:**
- ✅ SNS Topic for email delivery
- ✅ AgentCore Memory with semantic extraction
- ✅ IAM roles for AgentCore Runtime

### 2️⃣ Deploy Agent (2 minutes)
```bash
cd ../agent

# Configure and launch
agentcore configure -e agent.py
agentcore launch

# Copy the agent ARN from output
```

**Add agent ARN to .env:**
```bash
cd ..
echo "AGENTCORE_ARN=arn:aws:bedrock-agentcore:region:account:agent/agent-id" >> .env
```

### 3️⃣ Enable Autonomous Operation (Optional)
```bash
cd backend

# Deploy EventBridge Scheduler
cdk deploy --context email=your-email@example.com \
           --context agentcore_arn=$(grep AGENTCORE_ARN ../.env | cut -d'=' -f2) \
           --context enable_scheduler=true
```

**What this adds:**
- ✅ EventBridge Scheduler (6 AM EST daily)
- ✅ IAM role for EventBridge → AgentCore invocation

### 4️⃣ Test Manually
```bash
cd ..
python invoke_agent.py --prompt "Generate daily AWS AI/ML newsletter for the last 24 hours"
```

**Check your email!** Newsletter should arrive within ~15 seconds.

### 5️⃣ Confirm SNS Subscription

⚠️ **CRITICAL**: Check your email for SNS subscription confirmation and click the link. Emails will silently fail if not confirmed.

---

## 📁 Project Structure

```
aws-whats-new-alerts/
├── README.md                      # This file
├── .env                           # Auto-generated from CDK outputs
├── invoke_agent.py                # Manual testing script
├── local_chat_client.py           # Local development client
├── backend/                       # CDK Infrastructure
│   ├── app.py                     # CDK entry point
│   ├── newsletter_stack.py        # Complete infrastructure stack
│   ├── generate_env.py            # Generate .env from CloudFormation
│   ├── cdk.json                   # CDK configuration
│   ├── requirements.txt           # CDK dependencies
│   └── README.md                  # Backend documentation
├── agent/                         # AI Agent
│   ├── agent.py                   # Main agent code (production)
│   ├── requirements.txt           # Agent dependencies
│   ├── tools/                     # Custom tools (auto-loaded)
│   │   └── sns_tools.py          # SNS publish/subscribe
│   └── README.md                  # Agent documentation
└── validation/                    # Memory validation tools
    ├── validate_memory.py         # Memory validation script
    ├── requirements.txt           # Validation dependencies
    └── README.md                  # Validation documentation
```

---

## 🧠 Memory & Deduplication

### How It Works

1. **CDK Creates Memory** with semantic extraction strategy:
   - Namespaces: `/newsletter/facts`, `/newsletter/articles`
   - Custom extraction prompt: "Extract AWS article URLs, titles, dates..."
   - 30-day event expiry

2. **Agent Queries Memory** on session start:
   - Retrieval query: "What AWS articles have been processed?"
   - Gets back: Previously processed article URLs

3. **Agent Fetches News** from aws.amazon.com/new/
   - Extracts all article URLs from feed

4. **Cross-Reference**:
   - NEW articles: Not found in memory → Include in newsletter
   - DUPLICATES: Found in memory → Skip

5. **Agent Sends Newsletter** with only NEW articles

6. **Memory Extracts** from agent response:
   - Semantic strategy extracts mentioned URLs, titles, dates
   - Stores in `/newsletter/facts` for future deduplication

### Configuration

**CDK (backend/newsletter_stack.py:93-105):**
```python
agentcore.MemoryStrategy.using_semantic(
    name="newsletter_facts",
    namespaces=["/newsletter/facts", "/newsletter/articles"],
    custom_extraction=agentcore.OverrideConfig(
        append_to_prompt="Extract facts for AWS article deduplication..."
    )
)
```

**Agent (agent/agent.py:145-155):**
```python
retrieval_config={
    "/newsletter/facts": RetrievalConfig(
        top_k=50,
        initialization_query="What AWS articles have been processed? List URLs."
    )
}
```

---

## 🔧 Configuration

### Content Filtering

**Default**: AI/ML-focused announcements only
- Keywords: AI, ML, Bedrock, Claude, SageMaker, AgentCore, Strands, etc.

**Override**: Request "all announcements" for broader coverage

### Time Frames

Agent responds to natural language:
- `"last 24 hours"` (default)
- `"yesterday"`
- `"last week"` / `"7 days"`
- `"last month"` / `"30 days"`

### Schedule

**Default**: 6 AM EST (11 AM UTC) daily

**Change**: Edit `backend/newsletter_stack.py:196`
```python
schedule_expression="cron(0 11 * * ? *)",  # 6 AM EST / 11 AM UTC
```

---

## 🧪 Testing

### Test Deduplication
```bash
# Day 1: Process articles
python invoke_agent.py --prompt "Generate newsletter for yesterday"

# Day 2: Should skip duplicates
python invoke_agent.py --prompt "Generate newsletter for yesterday"
```

**Expected Day 2 output:** "Skipped X duplicate articles from memory"

### View Memory Contents
```bash
aws bedrock-agentcore get-memory \
    --memory-id $BEDROCK_AGENTCORE_MEMORY_ID \
    --region us-east-1
```

### Check CloudWatch Logs
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow --region us-east-1
```

---

## 📊 Monitoring

### EventBridge Scheduler Status
```bash
aws scheduler get-schedule \
    --name aws-newsletter-v2-prod-daily-newsletter \
    --region us-east-1
```

### Recent Newsletter Deliveries
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/ \
    --since 24h --filter-pattern "newsletter" --region us-east-1
```

### SNS Subscription Status
```bash
aws sns list-subscriptions-by-topic \
    --topic-arn $SNS_TOPIC_ARN \
    --region us-east-1
```

---

## 🐛 Troubleshooting

### Newsletter Has Duplicate Articles

**Symptom**: Day 2 newsletter includes articles from Day 1

**Causes**:
1. Memory not extracting article URLs properly
2. Namespace mismatch between CDK and agent
3. Semantic extraction not configured

**Fix**:
```bash
# Verify CDK has custom_extraction
grep -A 5 "custom_extraction" backend/newsletter_stack.py

# Verify agent queries correct namespace
grep -A 10 "retrieval_config" agent/agent.py

# Should both reference: /newsletter/facts
```

### "Memory Not Found" Error

**Symptom**: Agent fails with memory error

**Cause**: Memory still provisioning (takes 2-5 minutes after `cdk deploy`)

**Fix**: Wait 5 minutes, then redeploy agent

### Email Not Received

**Causes**:
1. ❌ SNS subscription not confirmed (check email for confirmation link)
2. ❌ SNS_TOPIC_ARN not in .env (run `python generate_env.py`)
3. ❌ IAM role lacks SNS permissions (redeploy CDK stack)

**Check subscription status:**
```bash
aws sns list-subscriptions-by-topic \
    --topic-arn $SNS_TOPIC_ARN

# Look for: "SubscriptionArn": "arn:..." (not "PendingConfirmation")
```

### Agent Returns Empty Results

**Causes**:
1. AWS news feed has no AI/ML articles in time frame
2. CUTOFF_DATE too restrictive (only processes articles >= 2022-10-01)
3. Agent filtering too narrow

**Test with broader coverage:**
```bash
python invoke_agent.py --prompt "Generate newsletter with all announcements for the last week"
```

---

## 🔄 Common Operations

### Update Agent Code
```bash
cd agent
# Edit agent.py
agentcore launch  # Redeploys with new code
```

### Update Infrastructure
```bash
cd backend
cdk diff  # Preview changes
cdk deploy --context email=your-email@example.com
```

### Change Email Subscribers
```bash
cd backend
cdk deploy --context email=new-email@example.com
```

### Disable Autonomous Operation
```bash
aws scheduler update-schedule \
    --name aws-newsletter-v2-prod-daily-newsletter \
    --state DISABLED
```

### Clean Up Everything
```bash
cd backend
cdk destroy  # Removes all infrastructure
```

---

## 💰 Cost Estimation

**Monthly cost for daily newsletter:**
- AgentCore Runtime: ~$0.30 (~$0.01/invocation × 30 days)
- Bedrock Claude (Sonnet): ~$1.50-3.00 (depends on article count)
- AgentCore Memory: ~$0.30 (storage + queries)
- SNS: Free (first 1,000 emails/month)
- CloudWatch Logs: ~$0.10

**Total**: ~$2-4/month

---

## 🛠️ Technology Stack

- **Infrastructure**: AWS CDK (Python)
- **Agent Framework**: Strands AI
- **Runtime**: AWS Bedrock AgentCore
- **Memory**: AgentCore Semantic Memory (30-day expiry)
- **Scheduling**: Amazon EventBridge Scheduler
- **Email**: Amazon SNS
- **Model**: Claude 3.5 Sonnet (via Bedrock)

---

## 📚 Documentation

- **[agent/README.md](agent/README.md)** - Agent architecture and configuration
- **[backend/README.md](backend/README.md)** - CDK infrastructure documentation
- **[validation/README.md](validation/README.md)** - Memory validation tools and troubleshooting

---

## 🎯 Design Decisions

### Why No Lazy Loading?
AgentCore Runtime reuses Python processes. A singleton agent would share `session_id` across invocations, breaking memory isolation. We create fresh instances per invocation.

### Why Semantic Memory?
Built-in semantic extraction automatically captures facts from conversation without explicit storage code. Agent mentions URLs, memory extracts them.

### Why /newsletter/facts Namespace?
Single global namespace (not actor-specific) because:
- Single bot deployment (no multi-tenancy)
- Simpler configuration
- Shared deduplication state

### Why 6 AM EST?
- Captures previous day's AWS announcements (most published during US business hours)
- Delivers to subscriber inboxes before they start work
- Allows troubleshooting during work hours if needed

---

## 🤝 Contributing

This is a personal project demonstrating AWS Bedrock AgentCore capabilities. Feel free to:
- Fork and modify for your use case
- Use as reference for AgentCore memory integration
- Adapt for different content sources or delivery methods

---

## 📝 License

© 2025 Amazon Web Services, Inc.

---

## 🔗 Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Strands AI Framework](https://github.com/awslabs/strands)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AgentCore Memory Strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)

---

**Built with ❤️ using AWS Bedrock AgentCore and Strands AI**
