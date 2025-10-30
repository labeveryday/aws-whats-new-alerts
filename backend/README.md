# AWS SNS Newsletter with SQS Tracking

This project demonstrates how to build an email newsletter system using AWS SNS with SQS for delivery tracking. It includes both boto3 and CDK Python implementations.

## Architecture

```
Newsletter Service → SNS Topic → Email Subscribers
                         ↓
                 Delivery Status → SQS Queue → Processing/Analytics
                         ↓
                  Failed Messages → Dead Letter Queue
```

## Features

- 📧 **Email Newsletter Distribution** via SNS
- 📊 **Delivery Tracking** via SQS
- 🔄 **Dead Letter Queue** for failed messages
- 🛡️ **IAM Security** with least privilege
- 📈 **Monitoring Ready** with CloudWatch integration
- 🚀 **Two Deployment Options**: Boto3 scripts and CDK

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS CLI
aws configure

# Copy environment file
cp .env.example .env
# Edit .env with your values
```

### Option 1: Boto3 Deployment (Recommended for Demo)

```bash
# Deploy infrastructure
python deploy_boto3.py --email your-email@example.com

# Send test newsletter
python deploy_boto3.py --send-test "Test Subject" "Test message content"

# Check delivery status
python deploy_boto3.py --check-status

# Cleanup resources
python deploy_boto3.py --cleanup
```

### Option 2: CDK Deployment (Recommended for Production)

```bash
# Install CDK
npm install -g aws-cdk

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy stack
cdk deploy --context email=your-email@example.com

# Destroy stack
cdk destroy
```

## Usage Examples

### Using the Client Library

```python
from deploy_utils import NewsletterClient, create_sample_newsletter

# Initialize client
client = NewsletterClient(region='us-east-1')

# Send newsletter
newsletter = create_sample_newsletter()
client.send_newsletter(
    topic_arn="arn:aws:sns:us-east-1:123456789012:newsletter-demo-newsletter-topic",
    subject=newsletter['subject'],
    message=newsletter['message']
)

# Check delivery status
status_reports = client.check_delivery_status(
    queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/newsletter-demo-tracking-queue"
)

# List subscriptions
client.list_subscriptions(topic_arn)
```

### Command Line Usage

```bash
# Deploy with custom configuration
python deploy_boto3.py \\
    --region us-west-2 \\
    --stack-name my-newsletter \\
    --email admin@mycompany.com

# Send newsletter with custom content
python deploy_boto3.py \\
    --send-test \\
    "Weekly AWS Updates" \\
    "This week's AWS announcements..."

# Check delivery status with more messages
python deploy_boto3.py --check-status
```

## File Structure

```
backend/
├── deploy_boto3.py      # Boto3 deployment script
├── app.py              # CDK app entry point
├── newsletter_stack.py  # CDK stack definition
├── deploy_utils.py     # Utility functions
├── requirements.txt    # Python dependencies
├── cdk.json           # CDK configuration
├── .env.example       # Environment variables template
└── README.md          # This file
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
AWS_REGION=us-east-1
STACK_NAME=newsletter-demo
TEST_EMAIL=your-email@example.com
```

### CDK Context

You can also pass configuration via CDK context:

```bash
cdk deploy \\
    --context region=us-west-2 \\
    --context email=test@example.com \\
    --context stack_name=my-newsletter
```

## Monitoring and Analytics

### CloudWatch Metrics

The system automatically creates CloudWatch metrics for:
- SNS message delivery success/failure rates
- SQS queue depth and processing times
- Dead letter queue messages

### Delivery Status Messages

SQS receives detailed delivery status in this format:

```json
{
  "MessageId": "12345678-1234-1234-1234-123456789012",
  "delivery": {
    "messageId": "12345678-1234-1234-1234-123456789012",
    "destination": "user@example.com",
    "deliveryStatus": "SUCCESS",
    "providerResponse": "Message delivered",
    "timestamp": "2023-10-27T10:30:00.000Z"
  }
}
```

## Security Considerations

### IAM Permissions

The system uses least-privilege IAM roles:

- **SNS Service Role**: Only `sqs:SendMessage` to tracking queue
- **SQS Queue Policy**: Only allows messages from the specific SNS topic
- **Lambda Role** (CDK only): Minimal permissions for configuration

### Email Privacy

- No email addresses are logged in CloudWatch
- Delivery status contains hashed destination identifiers
- Failed messages in DLQ don't contain PII

## Cost Optimization

### SNS Pricing
- First 1 million notifications: Free
- After: $0.50 per million notifications

### SQS Pricing
- First 1 million requests: Free  
- After: $0.40 per million requests

### Estimated Monthly Cost
- 10k newsletter subscribers: ~$0.05/month
- 100k newsletter subscribers: ~$0.50/month

## Troubleshooting

### Common Issues

1. **Email not delivered**
   ```bash
   # Check if email confirmed subscription
   python deploy_boto3.py --check-status
   
   # Verify SNS topic permissions
   aws sns get-topic-attributes --topic-arn <topic-arn>
   ```

2. **SQS messages not appearing**
   ```bash
   # Check SNS delivery status configuration
   aws sns get-topic-attributes --topic-arn <topic-arn>
   
   # Verify SQS queue policy
   aws sqs get-queue-attributes --queue-url <queue-url>
   ```

3. **CDK deployment fails**
   ```bash
   # Check CDK version
   cdk --version
   
   # Re-bootstrap if needed
   cdk bootstrap --force
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Production Considerations

### Scaling
- SNS scales automatically to millions of subscribers
- Consider SQS FIFO queues for ordered processing
- Use SNS message filtering for targeted newsletters

### Reliability
- Implement exponential backoff for SQS processing
- Monitor dead letter queue for failed deliveries
- Set up CloudWatch alarms for delivery failures

### Enhanced Features
- Replace SNS email with Amazon SES for:
  - HTML templates
  - Advanced analytics
  - Bounce/complaint handling
  - Higher sending limits

## Related AWS Services

- **Amazon SES**: Production email service with templates
- **Amazon Pinpoint**: Marketing communications platform
- **AWS Step Functions**: Orchestrate complex newsletter workflows
- **Amazon EventBridge**: Event-driven newsletter triggers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test both boto3 and CDK deployments
4. Submit a pull request

## License

MIT License - see LICENSE file for details.