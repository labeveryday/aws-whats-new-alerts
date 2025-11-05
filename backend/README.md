# AWS Newsletter Backend Infrastructure

CDK-based infrastructure for the AWS What's New Alerts newsletter system. Deploys SNS for email delivery, AgentCore Memory for article deduplication, and optional EventBridge Scheduler for autonomous operation.

## Architecture

```
EventBridge Scheduler (daily 6 AM EST / 11 AM UTC) → Bedrock AgentCore Runtime
                                               ↓
                                         Agent execution
                                               ↓
                    ┌──────────────────────────┼──────────────────┐
                    ↓                          ↓                  ↓
              AWS News Feed            AgentCore Memory      SNS Topic
                    ↓                          ↓                  ↓
                 Filtering               Deduplication      Email subscribers
```

## Features

- 📧 **Email Newsletter Distribution** via SNS
- 🧠 **Article Deduplication** via AgentCore Memory (30-day retention)
- 🤖 **Autonomous Operation** via EventBridge Scheduler (optional)
- 🔐 **IAM Security** with least privilege roles
- 🚀 **Infrastructure as Code** with AWS CDK
- 📊 **CloudFormation State Management** for reliable deployments

## Infrastructure Components

### Core Resources (Always Deployed)
1. **SNS Topic** - Email distribution to subscribers
2. **AgentCore Memory** - Semantic + user preference strategies for article tracking
3. **AgentCore Runtime Role** - IAM role for agent to publish to SNS

### Optional Resources (Autonomous Mode)
4. **EventBridge Scheduler** - Daily trigger at 6 AM EST (11 AM UTC)
5. **EventBridge Role** - IAM role to invoke AgentCore Runtime

## Quick Start

### Prerequisites

```bash
# Install Node.js (for CDK CLI)
# https://nodejs.org/

# Install CDK CLI globally
npm install -g aws-cdk

# Install Python dependencies
pip install -r requirements.txt

# Configure AWS CLI
aws configure
```

### Initial Deployment

```bash
# 1. Bootstrap CDK (first time only per account/region)
cdk bootstrap

# 2. Deploy infrastructure
cdk deploy --context email=your-email@example.com

# 3. Generate .env file from stack outputs
python generate_env.py

# 4. Wait 2-5 minutes for AgentCore Memory provisioning

# 5. Check email and confirm SNS subscription
#    (Click the confirmation link in the email)
```

### Deploy Agent

After infrastructure is deployed:

```bash
# 6. Navigate to agent directory
cd ../agent

# 7. Configure and deploy agent
agentcore configure -e agent.py
agentcore launch

# 8. Copy the agent ARN from output and add to .env
cd ..
echo "AGENTCORE_ARN=<your-agent-arn>" >> .env
```

### Enable Autonomous Operation (Optional)

```bash
# Redeploy with EventBridge Scheduler
cd backend
cdk deploy --context email=your-email@example.com \
           --context agentcore_arn=<your-agent-arn> \
           --context enable_scheduler=true

# Regenerate .env to include scheduler info
python generate_env.py
```

## CDK Commands

### Development

```bash
# View changes before deploying
cdk diff

# Deploy with custom parameters
cdk deploy --context stack_name=my-newsletter \
           --context region=us-west-2 \
           --context email=your-email@example.com

# List all stacks
cdk list

# Synthesize CloudFormation template
cdk synth
```

### Management

```bash
# View stack outputs
aws cloudformation describe-stacks --stack-name aws-newsletter-prod \
    --query 'Stacks[0].Outputs' --output table

# Regenerate .env from existing stack
python generate_env.py --stack-name aws-newsletter-prod --region us-east-1

# Destroy stack and all resources
cdk destroy
```

## File Structure

```
backend/
├── app.py                  # CDK app entry point
├── newsletter_stack.py     # Complete stack definition (276 lines)
├── generate_env.py         # Generate .env from CloudFormation outputs
├── cdk.json                # CDK configuration with feature flags
├── requirements.txt        # Python dependencies (CDK + AgentCore alpha)
└── README.md               # This file
```

## Configuration

### Context Variables

Pass configuration via CDK context (command line or `cdk.json`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `email` | No | None | Email to subscribe to newsletter |
| `stack_name` | No | `aws-newsletter` | Stack name prefix |
| `region` | No | `us-east-1` | AWS region |
| `agentcore_arn` | No | None | Agent ARN (required for scheduler) |
| `enable_scheduler` | No | `false` | Enable EventBridge Scheduler |

### Environment File

The `generate_env.py` script creates a `.env` file in the root directory:

```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
SNS_TOPIC_ARN=arn:aws:sns:region:account:aws-newsletter-topic
BEDROCK_AGENTCORE_MEMORY_ID=memory-id
BEDROCK_AGENTCORE_MEMORY_ARN=arn:aws:bedrock-agentcore:...
AGENTCORE_RUNTIME_ROLE_ARN=arn:aws:iam::account:role/...

# Add manually after agent deployment:
AGENTCORE_ARN=arn:aws:bedrock-agentcore:...

# Auto-included if EventBridge Scheduler enabled:
EVENTBRIDGE_SCHEDULE_NAME=aws-newsletter-daily-newsletter
EVENTBRIDGE_ROLE_ARN=arn:aws:iam::account:role/...
```

## Stack Outputs

CloudFormation outputs (accessible via `generate_env.py` or AWS Console):

- `NewsletterTopicArn` - SNS topic ARN for email distribution
- `MemoryId` - AgentCore Memory ID for agent configuration
- `MemoryArn` - AgentCore Memory ARN
- `AgentCoreRuntimeRoleArn` - IAM role for agent runtime
- `EventBridgeScheduleName` - Schedule name (if enabled)
- `EventBridgeRoleArn` - EventBridge IAM role (if enabled)

## AgentCore Memory

The stack creates AgentCore Memory with two strategies:

### Semantic Strategy
- **Name**: `newsletter_facts`
- **Namespaces**: `/newsletter/facts`, `/newsletter/articles`
- **Purpose**: Extract and store article metadata for deduplication

### User Preference Strategy
- **Name**: `user_prefs`
- **Namespaces**: `/newsletter/preferences`, `/user/settings`
- **Purpose**: Remember user preferences and settings

### Event Expiry
- Events automatically expire after **30 days**
- Old articles disappear from deduplication tracking
- Configurable via `expiration_duration` in stack

## IAM Roles

### AgentCore Runtime Role
Allows agent to:
- `sns:Publish` to newsletter topic
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### EventBridge Role (if scheduler enabled)
Allows EventBridge Scheduler to:
- `bedrock-agentcore:InvokeAgentRuntime` on agent ARN

## Cost Estimate

### Monthly Costs (Estimated)

| Service | Usage | Cost |
|---------|-------|------|
| SNS | 1,000 emails/day | Free tier |
| SNS | 100,000 emails/day | ~$0.10/month |
| AgentCore Memory | 30-day retention | ~$5-10/month |
| EventBridge Scheduler | 1 daily invocation | Free tier |
| AgentCore Runtime | 1 daily invocation | ~$0.01-0.05/month |

**Total**: ~$5-10/month for most use cases

### Cost Optimization Tips
- Memory is the primary cost driver
- Reduce `expiration_duration` if 30 days isn't needed
- Free tier covers most newsletter scenarios
- EventBridge Scheduler is free for basic scheduling

## Troubleshooting

### Common Issues

#### 1. Memory not found error
```bash
# Wait 2-5 minutes after deployment for provisioning
aws bedrock-agentcore list-memories --query 'memories[*].[id,state]'

# Check memory state
aws bedrock-agentcore get-memory --memory-id <memory-id>
```

#### 2. Email not delivered
```bash
# Check SNS subscription status
aws sns list-subscriptions-by-topic --topic-arn <topic-arn>

# Look for "PendingConfirmation" status
# User must click confirmation link in email
```

#### 3. CDK bootstrap fails
```bash
# Ensure you have admin permissions
aws sts get-caller-identity

# Force re-bootstrap
cdk bootstrap --force

# Check CDK version
cdk --version  # Should be >= 2.80.0
```

#### 4. Agent can't publish to SNS
```bash
# Verify agent is using the correct IAM role
# Check role ARN in .env: AGENTCORE_RUNTIME_ROLE_ARN

# Test SNS publish manually
aws sns publish --topic-arn <topic-arn> --message "Test"
```

#### 5. EventBridge Scheduler not triggering
```bash
# Check schedule state
aws scheduler get-schedule --name aws-newsletter-daily-newsletter

# View schedule executions (CloudWatch Logs)
aws logs tail /aws/bedrock-agentcore/runtimes/ --follow
```

## Production Considerations

### Scaling
- **SNS** scales automatically to millions of subscribers
- **AgentCore Memory** handles concurrent agent requests
- **EventBridge** reliable for daily scheduling (99.9% SLA)

### Monitoring
- CloudWatch Logs: `/aws/bedrock-agentcore/runtimes/`
- CloudWatch Metrics: Monitor SNS publish failures
- CloudWatch Alarms: Alert on agent execution failures

### Security Best Practices
- ✅ Use least-privilege IAM roles (implemented)
- ✅ Enable CloudTrail for audit logging
- ✅ Use AWS Secrets Manager for sensitive config (if needed)
- ✅ Tag resources for cost allocation

### High Availability
- SNS and AgentCore are fully managed services (multi-AZ)
- EventBridge Scheduler has automatic retries (3 attempts)
- No single points of failure

## Migration from SES

If you need advanced email features:

```python
# Replace SNS with SES in agent tools
# Benefits:
# - HTML email templates
# - Bounce/complaint handling
# - Advanced analytics
# - Higher sending limits (50k/day vs 200/day)
```

See `SES_MIGRATION_PLAN.md` in project root for details.

## Related AWS Services

- **Amazon Bedrock** - Foundation models for agent intelligence
- **AWS Step Functions** - Orchestrate complex workflows
- **Amazon EventBridge Pipes** - Connect event sources
- **AWS CloudFormation** - Infrastructure state management

## Development Workflow

```bash
# 1. Make changes to newsletter_stack.py
vim newsletter_stack.py

# 2. Preview changes
cdk diff

# 3. Deploy changes
cdk deploy

# 4. Regenerate .env if outputs changed
python generate_env.py

# 5. Test manually
cd .. && python invoke_agent.py --prompt "Generate newsletter for yesterday"
```

## Clean Up

```bash
# Destroy all infrastructure
cdk destroy

# Delete .env file (optional)
rm ../.env

# Remove CDK bootstrap (optional, affects all stacks in region)
# aws cloudformation delete-stack --stack-name CDKToolkit
```

## Support

- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/
- **Bedrock AgentCore**: https://docs.aws.amazon.com/bedrock/
- **Project Issues**: https://github.com/your-org/aws-whats-new-alerts/issues

## License

MIT License - see LICENSE file for details.
