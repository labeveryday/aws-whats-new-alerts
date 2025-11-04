# AWS What's New Alerts

Automated newsletter system that monitors AWS announcements and delivers daily email digests focused on AI/ML updates.

## Quick Start

Get up and running in 10 minutes:

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Deploy infrastructure (SNS + SQS + AgentCore Memory)
cd backend
python deploy_full_stack.py --email your-email@example.com

# 3. Deploy agent
cd ../deployment
agentcore configure -e agent.py
agentcore launch

# 4. Test
cd ..
python invoke_agent.py --prompt "Generate newsletter for yesterday"
```

📚 **[Full Quick Start Guide →](QUICKSTART.md)**

## What This Does

- 🔍 Automatically fetches latest AWS announcements
- 🎯 Filters for AI/ML-related content (customizable)
- 📧 Generates professional formatted newsletters
- 🧠 Remembers processed articles (no duplicates)
- 📨 Delivers via email (AWS SNS)
- 📊 Tracks delivery status (AWS SQS)

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 10 minutes
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Comprehensive deployment guide
- **[DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)** - Technical implementation details
- **[SES_MIGRATION_PLAN.md](SES_MIGRATION_PLAN.md)** - Alternative email delivery options
- **[backend/README.md](backend/README.md)** - SNS/SQS infrastructure details

## Architecture

```
Bedrock Agent → SNS Topic → Email Subscribers
     ↑                ↓
AWS News Feed    SQS Delivery Tracking
     ↑
AgentCore Memory
```

## Features

- ✅ Daily automated newsletters
- ✅ Content filtering by topic
- ✅ Customizable time ranges
- ✅ Memory-based duplicate prevention
- ✅ Professional formatting with statistics
- ✅ Delivery tracking and analytics
- ✅ Easy cleanup and management

## Requirements

- AWS Account with Bedrock AgentCore access
- Python 3.10+
- Required AWS services enabled (SNS, SQS, Bedrock)

## License

MIT License - see LICENSE file for details.
