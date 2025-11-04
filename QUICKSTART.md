# Quick Start Guide - AWS Newsletter

Get your AWS newsletter agent up and running in 10 minutes.

## Prerequisites Checklist

- [ ] AWS account with credentials configured (`aws configure`)
- [ ] Python 3.10+ installed
- [ ] Git repository cloned
- [ ] **Claude Sonnet 4.0 enabled in AWS Bedrock Console** (required!)

## Step-by-Step Setup

### 1. Activate Virtual Environment & Install Dependencies (2 min)

```bash
# From project root
source .venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### 2. Deploy Infrastructure (3 min)

```bash
# Still in backend/
python deploy_full_stack.py --email your-email@example.com --region us-east-1
```

**What this creates:**
- ✅ SNS topic for sending newsletters
- ✅ SQS queues for delivery tracking
- ✅ IAM roles and policies
- ✅ AgentCore Memory for tracking processed articles
- ✅ `.env` file with all configuration

**Expected output:**
```
🚀 Deploying Full Newsletter Stack: aws-newsletter
✓ Created tracking queue
✓ Created IAM role
✓ Created SNS topic
✓ Created AgentCore Memory
✓ Configuration written to .env
✅ DEPLOYMENT COMPLETED SUCCESSFULLY!
```

### 3. Confirm Email Subscription (1 min)

Check your email for "AWS Notification - Subscription Confirmation" and click the confirmation link.

### 4. Deploy the Agent (5 min)

```bash
cd ../deployment

# Configure agent (creates .bedrock_agentcore.yaml)
agentcore configure -e agent.py
# Accept defaults or specify your region

# Deploy to AgentCore Runtime (takes ~5 minutes first time)
agentcore launch
```

**Save the agent ARN** from the output:
```
Agent Runtime ARN: arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/abc123
```

### 5. Update .env with Agent ARN (30 sec)

```bash
cd ..
echo "AGENTCORE_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/abc123" >> .env
```

### 6. Test the Agent (1 min)

```bash
python invoke_agent.py --prompt "Generate a newsletter for yesterday's AI announcements"
```

**Check your email!** You should receive a formatted newsletter.

### 7. Deploy EventBridge Automation (OPTIONAL - 2 min)

Make your newsletter **fully autonomous** with daily scheduled execution:

```bash
cd backend
python deploy_eventbridge.py
```

**What this creates:**
- ✅ EventBridge Scheduler (runs daily at 8 AM UTC)
- ✅ IAM role for EventBridge to invoke AgentCore
- ✅ IAM role for AgentCore to publish to SNS
- ✅ Updates `.env` with scheduler configuration

**Expected output:**
```
🚀 Deploying EventBridge Scheduler: aws-newsletter
✓ Created EventBridge role
✓ Created AgentCore Runtime role
✓ Created schedule
✓ Updated .env
✅ EVENTBRIDGE DEPLOYMENT COMPLETED SUCCESSFULLY!
```

**Custom schedules:**
```bash
# Run every 12 hours
python deploy_eventbridge.py --schedule "rate(12 hours)"

# Run at noon UTC daily
python deploy_eventbridge.py --schedule "cron(0 12 * * ? *)"

# Run weekdays at 9 AM UTC
python deploy_eventbridge.py --schedule "cron(0 9 ? * MON-FRI *)"
```

**Test manual trigger:**
```bash
python deploy_eventbridge.py --trigger-now
```

## Verification Commands

### Check Infrastructure Status
```bash
# View .env configuration
cat .env

# Verify memory is ready
aws bedrock-agentcore-control get-memory \
  --memory-id $(grep BEDROCK_AGENTCORE_MEMORY_ID .env | cut -d= -f2) \
  --region us-east-1 \
  --query 'memory.status'
```

### Check Agent Status
```bash
cd deployment
agentcore status
agentcore logs
```

### Check EventBridge Scheduler (if deployed)
```bash
cd ../backend
python deploy_eventbridge.py --status

# Or use AWS CLI
aws scheduler get-schedule --name aws-newsletter-daily-newsletter
```

### Test Newsletter Generation
```bash
cd ..
python invoke_agent.py --prompt "Generate newsletter with all AWS announcements from last 3 days"
```

## Common First-Time Issues

### ❌ "Claude Sonnet 4.0 not enabled"

**Solution:** Enable in Bedrock console
1. Go to AWS Console → Bedrock → Model Access
2. Click "Manage model access"
3. Enable "Anthropic Claude Sonnet 4.0"
4. Wait 2-3 minutes for activation

### ❌ "Memory not found"

**Solution:** Memory is still provisioning (takes 2-5 minutes). Wait and retry.

### ❌ "No email received"

**Solutions:**
1. Did you click the confirmation link? Check spam folder.
2. Verify subscription: `aws sns list-subscriptions-by-topic --topic-arn $(grep SNS_TOPIC_ARN .env | cut -d= -f2)`
3. Check agent logs: `cd deployment && agentcore logs`

### ❌ "agentcore: command not found"

**Solution:** Install toolkit:
```bash
pip install bedrock-agentcore-starter-toolkit
```

## What's Next?

### Customize Your Newsletter

Edit `deployment/agent.py` to change:
- Content filters (currently focuses on AI/ML)
- Time ranges (default: last 24 hours)
- Newsletter format
- Categories to track

### Schedule Daily Runs

Option 1: **AWS EventBridge**
```bash
# Create daily schedule (8 AM UTC)
aws events put-rule \
  --name daily-newsletter \
  --schedule-expression "cron(0 8 * * ? *)"

aws events put-targets \
  --rule daily-newsletter \
  --targets "Id=1,Arn=$(grep AGENTCORE_ARN .env | cut -d= -f2)"
```

Option 2: **Local cron**
```bash
# Edit crontab
crontab -e

# Add daily run at 8 AM
0 8 * * * cd /path/to/aws-whats-new-alerts && source .venv/bin/activate && python invoke_agent.py --prompt "Generate daily newsletter" >> logs/cron.log 2>&1
```

### Add Custom Tools

Create new tools in `deployment/tools/`:

```python
# deployment/tools/my_tool.py
from strands import tool

@tool
def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of AWS announcement"""
    # Your custom logic
    return "positive"
```

The agent will automatically load all tools from the `tools/` directory!

### Monitor Performance

```bash
# View agent logs
cd deployment
agentcore logs

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/BedrockAgentCore \
  --metric-name Invocations \
  --dimensions Name=AgentName,Value=aws-newsletter \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│              Daily Newsletter Flow                        │
└──────────────────────────────────────────────────────────┘

  1. EventBridge Scheduler (8 AM UTC daily)
        ↓
  2. Triggers AgentCore Runtime
        ↓
  3. Agent executes (agent.py)
        ↓
        ├─► Fetch AWS News (https://aws.amazon.com/new/)
        ├─► Check Memory (avoid duplicates)
        ├─► Filter AI content
        └─► Generate newsletter
             ↓
  4. Publish to SNS Topic
        ↓
        ├─► Email Subscribers → 📧 Newsletter
        └─► SQS Queue → 📊 Delivery Tracking
```

## Cost Estimate

**For 1,000 subscribers with daily newsletter:**
- SNS: ~$0.05/month
- SQS: Free tier
- AgentCore Memory: ~$0.10/month
- AgentCore Runtime: ~$0.50/month (30 invocations)

**Total: ~$0.65/month** ≈ $0.02/day

## Cleanup

When you're done testing:

```bash
# Remove infrastructure
cd backend
python deploy_full_stack.py --cleanup

# Remove agent
cd ../deployment
agentcore destroy

# Deactivate venv
deactivate
```

## Get Help

- 📚 [Full Deployment Guide](DEPLOYMENT_GUIDE.md)
- 📖 [CLAUDE.md](CLAUDE.md) - Developer reference
- 🐛 [Report Issues](https://github.com/your-repo/issues)
- 📝 [AgentCore Docs](https://aws.github.io/bedrock-agentcore-starter-toolkit/)

## Success Checklist

After completing this guide, you should have:

- [ ] Infrastructure deployed (SNS, SQS, IAM, Memory)
- [ ] Agent deployed to AgentCore Runtime
- [ ] Email subscription confirmed
- [ ] `.env` file populated with all ARNs/IDs
- [ ] Successfully received a test newsletter
- [ ] Agent logs showing successful execution
- [ ] (Optional) EventBridge Scheduler configured for daily automation

**Congratulations! Your AWS Newsletter Agent is live!** 🎉

### Bonus: Fully Autonomous Setup

If you completed step 7 (EventBridge):
- ✅ Newsletter runs automatically daily at 8 AM UTC
- ✅ No manual intervention required
- ✅ CloudWatch logs track all executions
- ✅ Email arrives in your inbox every morning
