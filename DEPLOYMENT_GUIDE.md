# AWS Newsletter - Full Stack Deployment Guide

This guide walks you through deploying the complete AWS Newsletter infrastructure including SNS, SQS, and AgentCore Memory.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Python 3.10+** installed
4. **Virtual environment** activated

### Required AWS Permissions

Your AWS user/role needs permissions for:
- SNS (create topics, subscriptions, configure attributes)
- SQS (create queues, set policies)
- IAM (create roles and policies)
- Bedrock AgentCore (create memory, deploy agents)
- CloudWatch (for logs)

## Installation

### 1. Set up Python environment

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install boto3 python-dotenv bedrock-agentcore-starter-toolkit
```

### 2. Verify AWS credentials

```bash
aws sts get-caller-identity
```

You should see your AWS account ID and user/role information.

## Deployment Steps

### Step 1: Deploy Infrastructure

Run the full stack deployment script:

```bash
cd backend
python deploy_full_stack.py --email your-email@example.com
```

**Options:**
- `--region us-west-2` - Deploy to specific region (default: us-east-1)
- `--stack-name my-newsletter` - Custom stack name (default: aws-newsletter)
- `--email your@email.com` - Subscribe email to newsletter

**Example with custom configuration:**
```bash
python deploy_full_stack.py \
  --region us-west-2 \
  --stack-name production-newsletter \
  --email alerts@mycompany.com
```

### Step 2: Confirm Email Subscription

After deployment:
1. Check your email inbox for "AWS Notification - Subscription Confirmation"
2. Click the confirmation link
3. You'll see a success message in your browser

### Step 3: Wait for Memory Provisioning

AgentCore Memory takes 2-5 minutes to provision. You can proceed with the next steps while waiting.

### Step 4: Review Generated .env File

The deployment creates a `.env` file in the project root with all configuration:

```bash
cat ../.env
```

Expected content:
```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:aws-newsletter-newsletter-topic
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/aws-newsletter-tracking-queue
BEDROCK_AGENTCORE_MEMORY_ID=abc123xyz
# ... and more
```

### Step 5: Deploy the Agent

Now deploy your agent to AgentCore Runtime:

```bash
cd ../deployment

# Configure agent deployment
agentcore configure -e agent.py

# Deploy agent (first time takes 5-10 minutes)
agentcore launch
```

The CLI will output your agent's ARN. Copy it!

### Step 6: Update .env with Agent ARN

Edit `.env` and add the agent ARN:

```bash
AGENTCORE_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/abc123
```

## Testing the Deployment

### Test 1: Verify Memory is Ready

```bash
cd deployment
python -c "
import boto3
import os
from dotenv import load_dotenv

load_dotenv('../.env')
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
memory_id = os.getenv('BEDROCK_AGENTCORE_MEMORY_ID')
response = client.get_memory(memoryId=memory_id)
print(f\"Memory Status: {response['memory']['status']}\")
"
```

Expected output: `Memory Status: ACTIVE`

### Test 2: Invoke the Agent

```bash
cd ..
python invoke_agent.py --prompt "Generate a newsletter for yesterday's AWS announcements"
```

### Test 3: Check Newsletter Email

If the agent ran successfully, you should receive an email at your subscribed address.

### Test 4: Verify SQS Delivery Tracking

```bash
cd backend
python -c "
import boto3
import os
from dotenv import load_dotenv

load_dotenv('../.env')
sqs = boto3.client('sqs', region_name='us-east-1')
queue_url = os.getenv('SQS_QUEUE_URL')

response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
messages = response.get('Messages', [])
print(f'Delivery status messages: {len(messages)}')
for msg in messages:
    print(msg['Body'])
"
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Newsletter System                     │
└─────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  Your Agent  │  (Bedrock AgentCore)
    │  agent.py    │
    └──────┬───────┘
           │
           ├──► Fetches: https://aws.amazon.com/new/
           │
           ├──► Reads: AgentCore Memory
           │             (processed articles)
           │
           └──► Publishes: SNS Topic
                           │
                ┌──────────┴─────────┐
                │                    │
                ▼                    ▼
         ┌─────────────┐      ┌──────────┐
         │   Emails    │      │   SQS    │
         │ Subscribers │      │  Queue   │
         └─────────────┘      └────┬─────┘
                                   │
                              Delivery
                              Tracking
```

## Configuration Files

### .env (Generated automatically)
Contains all ARNs, URLs, and IDs needed by the agent.

### .bedrock_agentcore.yaml (Created by agentcore configure)
Contains agent deployment configuration.

## Common Issues & Solutions

### Issue: "Memory not found" error

**Solution:** Memory is still provisioning. Wait 2-5 minutes and try again.

```bash
# Check memory status
aws bedrock-agentcore-control get-memory \
  --memory-id $(grep BEDROCK_AGENTCORE_MEMORY_ID .env | cut -d= -f2) \
  --region us-east-1
```

### Issue: "No new announcements found"

**Solution:** The agent filters for AI-related content by default. Try:
```bash
python invoke_agent.py --prompt "Generate newsletter with all announcements from last week"
```

### Issue: "Email not received"

**Checklist:**
1. Did you confirm the subscription? Check spam folder for confirmation email.
2. Is the SNS subscription active?
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn $(grep SNS_TOPIC_ARN .env | cut -d= -f2)
   ```
3. Did the agent successfully publish?
   ```bash
   # Check CloudWatch logs
   agentcore logs
   ```

### Issue: "IAM role already exists" during deployment

**Solution:** This is normal on re-deployment. The script will reuse existing resources.

### Issue: Agent deployment fails

**Solution:** Ensure Claude Sonnet 4.0 is enabled in Bedrock console:
1. Go to AWS Bedrock Console
2. Navigate to Model Access
3. Enable "Anthropic Claude Sonnet 4.0"

## Cleanup

To remove all resources:

```bash
cd backend
python deploy_full_stack.py --cleanup
```

**Warning:** This will:
- Delete SNS topic (all subscriptions)
- Delete SQS queues (all messages)
- Delete AgentCore Memory (all stored data)
- Delete IAM role and policies

The agent deployment must be cleaned up separately:
```bash
cd ../deployment
agentcore destroy
```

## Cost Estimation

### Monthly costs for 10k newsletter subscribers:

| Service | Usage | Cost |
|---------|-------|------|
| SNS | 10k emails/month | ~$0.50 |
| SQS | 20k requests/month | Free tier |
| AgentCore Memory | Always-on | ~$0.10 |
| AgentCore Runtime | ~30 invocations/month | ~$0.50 |
| **Total** | | **~$1.10/month** |

### Daily newsletter (30 days/month):
- ~$0.033/day for 10k subscribers
- ~$0.0033/day for 1k subscribers

## Next Steps

1. **Customize the Agent**: Edit `deployment/agent.py` to adjust:
   - Newsletter format
   - Content filters
   - Time ranges
   - Categories

2. **Add Custom Tools**: Create new tools in `deployment/tools/`:
   ```python
   from strands import tool

   @tool
   def my_custom_tool(param: str) -> str:
       """Tool description"""
       # Your logic here
       return result
   ```

3. **Schedule Daily Runs**: Use AWS EventBridge or cron to invoke the agent daily.

4. **Monitor Performance**: Check CloudWatch logs:
   ```bash
   agentcore logs
   ```

## Support

- **Issues**: https://github.com/your-repo/issues
- **AgentCore Docs**: https://aws.github.io/bedrock-agentcore-starter-toolkit/
- **AWS Support**: https://console.aws.amazon.com/support/

## Additional Resources

- [AgentCore Runtime Overview](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/overview.html)
- [AgentCore Memory Quickstart](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/memory/quickstart.html)
- [AWS SNS Documentation](https://docs.aws.amazon.com/sns/)
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
