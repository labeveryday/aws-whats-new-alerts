# AgentCore Memory Validation

This folder contains tools to validate and inspect your AgentCore Memory using boto3.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure .env file is present with AgentCore configuration
# Run from backend directory if needed:
# python generate_env.py --agent-dir
```

## Usage

### Basic Memory Validation
```bash
python validate_memory.py
```

This will:
- ✅ Check memory status and configuration
- ✅ List memory events for your agent
- ✅ Query for processed AWS articles
- ✅ Validate deduplication is working
- ✅ Show sample URLs stored in memory

### Example Output
```
🧠 AgentCore Memory Validation Report
============================================================
Memory ID: aws_newsletter_v2_agent_memory-HCWulmB8eT
Region: us-west-2
Actor ID: aws-newsletter-bot
Session ID: aws-newsletter-main-session

📋 Memory Information:
   Name: aws_newsletter_v2_agent_memory
   Description: Memory store for aws-newsletter-v2 agent...
   Status: ENABLED
   Created: 2024-11-06T10:04:56.789000+00:00
   Updated: 2024-11-06T15:30:12.456000+00:00

📚 Memory Events:
   Total events: 15
   Recent events:
   1. SEMANTIC_EXTRACTION at 2024-11-06T15:30:12Z
   2. USER_MESSAGE at 2024-11-06T15:29:45Z
   3. SEMANTIC_EXTRACTION at 2024-11-06T14:15:30Z

🔍 Querying for Processed Articles:
----------------------------------------
Query: What AWS articles have been processed?
📊 Found 8 memory results
   1. (Score: 0.95) Processed AWS article: Amazon Bedrock now supports Claude 3.7...
   2. (Score: 0.92) Newsletter included announcement about SageMaker updates...
   3. (Score: 0.89) AWS AI/ML article from aws.amazon.com/about-aws/whats-new...

🔄 Deduplication Validation:
----------------------------------------
📊 Found 12 unique AWS URLs in memory
   Sample URLs:
   1. https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-bedrock-claude-3-7
   2. https://aws.amazon.com/about-aws/whats-new/2024/11/sagemaker-inference-updates
   3. https://aws.amazon.com/about-aws/whats-new/2024/11/agentcore-memory-improvements

✅ Deduplication status: Working
```

## Environment Variables Required

The script uses these environment variables (automatically set by `generate_env.py`):

- `BEDROCK_AGENTCORE_MEMORY_ID` - Your memory ID
- `AWS_REGION` - AWS region  
- `AGENT_ACTOR_ID` - Actor ID for memory queries
- `AGENT_SESSION_ID` - Session ID for memory queries

## Troubleshooting

### Memory Not Found
```
❌ Error: Memory not found
```
- Check your `BEDROCK_AGENTCORE_MEMORY_ID` in .env
- Ensure your AWS credentials have `bedrock-agentcore:GetMemory` permissions
- Wait 2-5 minutes after CDK deployment for memory provisioning

### No Memory Events
```
Total events: 0
```
- Run your agent at least once to populate memory
- Check that your agent is using the correct `ACTOR_ID` and `SESSION_ID`
- Verify agent is successfully processing articles

### Permission Errors
```
❌ Error: AccessDeniedException
```
- Ensure your AWS credentials have these permissions:
  - `bedrock-agentcore:GetMemory`
  - `bedrock-agentcore:ListMemories` 
  - `bedrock-agentcore:QueryMemory`
  - `bedrock-agentcore:ListMemoryEvents`

## Advanced Usage

### Custom Queries
You can modify the script to run custom memory queries:

```python
result = validator.query_memory(
    "Show me articles about Amazon Bedrock from last week",
    ACTOR_ID, 
    SESSION_ID,
    max_results=10
)
```

### Memory Cleanup
If you need to reset memory for testing, you can delete and recreate the memory through CDK:

```bash
# From backend directory
cdk destroy
cdk deploy --context email=your-email@example.com --context stack_name=aws-newsletter-v2
```

## Related Documentation

- [AWS Bedrock AgentCore API Reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agentcore.html)
- [AgentCore Memory Concepts](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory.html)