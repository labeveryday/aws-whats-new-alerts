# Migration Plan: SNS → Amazon SES

## Why Migrate to SES?

### Current SNS Limitations
- ❌ Plain text only (no HTML)
- ❌ Manual subscription confirmations per user
- ❌ No unsubscribe management
- ❌ No bounce/complaint handling
- ❌ Limited analytics
- ❌ Not designed for bulk emails

### SES Benefits
- ✅ **HTML templates** with beautiful formatting
- ✅ **Bulk sending** to verified email lists
- ✅ **No per-recipient confirmations** (send to your list)
- ✅ **Automatic bounce/complaint handling**
- ✅ **Open & click tracking**
- ✅ **Much better deliverability**
- ✅ **Professional appearance**
- ✅ **Cheaper** ($0.10 per 1,000 emails)

## Architecture Comparison

### Current (SNS)
```
Agent → SNS Topic → Email Subscribers (each confirmed individually)
              ↓
            SQS Queue (basic delivery tracking)
```

### Proposed (SES)
```
Agent → SES → Your Email List (verified domain or emails)
         ↓
    SES Events → EventBridge → SQS (detailed tracking)
         ↓
    Opens, Clicks, Bounces, Complaints
```

## Implementation Options

### Option 1: Quick Fix - Keep SNS for Personal Use
**Best for:** Just you receiving newsletters

**Pros:**
- Already working
- No changes needed
- Fine for 1-10 personal subscribers

**Cons:**
- Plain text only
- Can't scale
- Not professional

### Option 2: Migrate to SES - Production Ready
**Best for:** Real newsletter service

**Pros:**
- Professional HTML emails
- Scalable to thousands
- Better tracking
- Industry standard

**Cons:**
- Requires SES setup
- Need to verify domain or emails
- More complex configuration

## Migration Steps (Option 2)

### Step 1: SES Setup & Verification

#### A. Verify Email or Domain

**Option A: Verify Single Email (Quick for testing)**
```bash
aws ses verify-email-identity \
  --email-address newsletters@yourdomain.com \
  --region us-east-1

# Check verification status
aws ses get-identity-verification-attributes \
  --identities newsletters@yourdomain.com
```

Check your email and click verification link.

**Option B: Verify Domain (Recommended for production)**
```bash
aws ses verify-domain-identity \
  --domain yourdomain.com \
  --region us-east-1
```

Add DNS TXT record shown in output to your domain.

#### B. Move Out of Sandbox

**Important:** SES starts in sandbox mode (max 200 emails/day, verified recipients only).

To send to unverified emails:
1. Go to AWS Console → SES → Account Dashboard
2. Click "Request production access"
3. Fill form explaining use case
4. Wait 24 hours for approval

### Step 2: Update Deployment Script

Create `backend/deploy_full_stack_ses.py`:

```python
def create_ses_configuration_set(self) -> str:
    """Create SES configuration set for tracking"""
    ses = boto3.client('sesv2', region_name=self.region)

    config_set_name = f'{self.stack_name}-newsletter-config'

    try:
        ses.create_configuration_set(
            ConfigurationSetName=config_set_name,
            TrackingOptions={
                'CustomRedirectDomain': 'yourdomain.com'  # Optional
            }
        )

        # Add SNS destination for tracking events
        ses.create_configuration_set_event_destination(
            ConfigurationSetName=config_set_name,
            EventDestinationName='newsletter-events',
            EventDestination={
                'Enabled': True,
                'MatchingEventTypes': [
                    'SEND', 'DELIVERY', 'BOUNCE',
                    'COMPLAINT', 'OPEN', 'CLICK'
                ],
                'SnsDestination': {
                    'TopicArn': self.resources['topic_arn']
                }
            }
        )

        print(f"  ✓ Created SES configuration set: {config_set_name}")
        self.resources['ses_config_set'] = config_set_name
        return config_set_name

    except ClientError as e:
        print(f"  ❌ Error creating SES config: {e}")
        raise

def create_ses_template(self) -> str:
    """Create HTML email template"""
    ses = boto3.client('sesv2', region_name=self.region)

    template_name = f'{self.stack_name}-newsletter-template'

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .header { background: linear-gradient(135deg, #232F3E, #FF9900);
                      color: white; padding: 30px; text-align: center; }
            .content { padding: 20px; max-width: 800px; margin: 0 auto; }
            .announcement { background: #f8f9fa; padding: 20px; margin: 20px 0;
                           border-left: 4px solid #FF9900; }
            .announcement h3 { margin-top: 0; color: #232F3E; }
            .stats { display: flex; justify-content: space-around;
                    background: #232F3E; color: white; padding: 20px; }
            .stat { text-align: center; }
            .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌟 AWS Daily Newsletter</h1>
            <p>{{date}}</p>
        </div>
        <div class="content">
            <p>Dear AWS Community,</p>
            {{#if hasAnnouncements}}
            <p>Today brings {{count}} new AI/ML announcements! Here's your roundup:</p>

            {{#each announcements}}
            <div class="announcement">
                <h3>{{number}}. {{title}}</h3>
                <p><strong>📅 {{date}}</strong></p>
                <p>{{summary}}</p>
                <p><a href="{{url}}" style="color: #FF9900;">Read more →</a></p>
            </div>
            {{/each}}

            <div class="stats">
                <div class="stat">
                    <h2>{{stats.total}}</h2>
                    <p>Total Announcements</p>
                </div>
                <div class="stat">
                    <h2>{{stats.bedrock}}</h2>
                    <p>Bedrock Updates</p>
                </div>
                <div class="stat">
                    <h2>{{stats.sagemaker}}</h2>
                    <p>SageMaker Updates</p>
                </div>
            </div>
            {{else}}
            <p>No new AI/ML announcements today. Check back tomorrow!</p>
            {{/if}}
        </div>
        <div class="footer">
            <p>This newsletter was generated automatically</p>
            <p><a href="{{unsubscribeUrl}}">Unsubscribe</a> |
               <a href="https://aws.amazon.com/new/">AWS What's New</a></p>
        </div>
    </body>
    </html>
    """

    try:
        ses.create_email_template(
            TemplateName=template_name,
            TemplateContent={
                'Subject': '🌟 AWS Daily Newsletter | {{date}}',
                'Html': html_template,
                'Text': '{{plainTextVersion}}'  # Fallback
            }
        )

        print(f"  ✓ Created SES email template: {template_name}")
        self.resources['ses_template'] = template_name
        return template_name

    except ClientError as e:
        print(f"  ❌ Error creating SES template: {e}")
        raise
```

### Step 3: Create SES Email Tool

Create `deployment/tools/ses_tools.py`:

```python
"""
Strands Agent tool for sending emails via Amazon SES
"""
import boto3
import json
from strands import tool
from typing import List, Dict


@tool
def send_ses_newsletter(
    subject: str,
    announcements: List[Dict],
    recipient_email: str,
    from_email: str,
    stats: Dict = None
) -> str:
    """Send HTML newsletter via Amazon SES.

    Args:
        subject: Email subject line
        announcements: List of announcement dicts with keys: title, date, summary, url
        recipient_email: Recipient's email address
        from_email: Verified sender email
        stats: Optional stats dict with keys: total, bedrock, sagemaker

    Returns:
        Success/failure message with message ID
    """
    client = boto3.client('sesv2', region_name='us-east-1')

    try:
        # Build HTML content
        announcements_html = ""
        for i, ann in enumerate(announcements, 1):
            announcements_html += f"""
            <div class="announcement">
                <h3>{i}. {ann['title']}</h3>
                <p><strong>📅 {ann['date']}</strong></p>
                <p>{ann['summary']}</p>
                <p><a href="{ann['url']}" style="color: #FF9900;">Read more →</a></p>
            </div>
            """

        # Build stats HTML
        if stats:
            stats_html = f"""
            <div class="stats">
                <div class="stat"><h2>{stats.get('total', 0)}</h2><p>Total</p></div>
                <div class="stat"><h2>{stats.get('bedrock', 0)}</h2><p>Bedrock</p></div>
                <div class="stat"><h2>{stats.get('sagemaker', 0)}</h2><p>SageMaker</p></div>
            </div>
            """
        else:
            stats_html = ""

        # Full HTML email
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: linear-gradient(135deg, #232F3E, #FF9900);
                          color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 20px; max-width: 800px; margin: 0 auto; }}
                .announcement {{ background: #f8f9fa; padding: 20px; margin: 20px 0;
                               border-left: 4px solid #FF9900; }}
                .announcement h3 {{ margin-top: 0; color: #232F3E; }}
                .stats {{ display: flex; justify-content: space-around;
                        background: #232F3E; color: white; padding: 20px; margin: 20px 0; }}
                .stat {{ text-align: center; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🌟 AWS Daily Newsletter</h1>
            </div>
            <div class="content">
                <p>Dear AWS Community,</p>
                <p>Today brings {len(announcements)} new AI/ML announcements!</p>
                {announcements_html}
                {stats_html}
            </div>
            <div class="footer">
                <p>This newsletter was generated automatically</p>
            </div>
        </body>
        </html>
        """

        # Plain text fallback
        plain_text = f"{subject}\n\n"
        for i, ann in enumerate(announcements, 1):
            plain_text += f"{i}. {ann['title']}\n{ann['date']}\n{ann['summary']}\n{ann['url']}\n\n"

        # Send email
        response = client.send_email(
            FromEmailAddress=from_email,
            Destination={'ToAddresses': [recipient_email]},
            Content={
                'Simple': {
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': plain_text}
                    }
                }
            }
        )

        message_id = response['MessageId']
        return json.dumps({
            "status": "success",
            "message_id": message_id,
            "recipient": recipient_email,
            "announcement_count": len(announcements)
        }, indent=2)

    except Exception as e:
        return f"❌ Error sending SES email: {str(e)}"


@tool
def send_bulk_ses_newsletter(
    subject: str,
    announcements: List[Dict],
    recipient_emails: List[str],
    from_email: str
) -> str:
    """Send newsletter to multiple recipients (bulk).

    Args:
        subject: Email subject
        announcements: List of announcements
        recipient_emails: List of recipient email addresses
        from_email: Verified sender email

    Returns:
        Bulk send status
    """
    client = boto3.client('sesv2', region_name='us-east-1')

    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }

    for email in recipient_emails:
        try:
            result = send_ses_newsletter(
                subject=subject,
                announcements=announcements,
                recipient_email=email,
                from_email=from_email
            )
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{email}: {str(e)}")

    return json.dumps(results, indent=2)
```

### Step 4: Update Agent to Use SES

Modify `deployment/agent.py`:

```python
# Change from SNS_TOPIC_ARN to:
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL")  # newsletters@yourdomain.com
SES_TO_EMAIL = os.getenv("SES_TO_EMAIL")      # your@email.com

# In SYSTEM_PROMPT, change:
# "8. Send email via publish_message tool to: {SNS_TOPIC_ARN}"
# to:
# "8. Send email via send_ses_newsletter tool to: {SES_TO_EMAIL} from: {SES_FROM_EMAIL}"
```

### Step 5: Update .env

Add to `.env`:
```bash
SES_FROM_EMAIL=newsletters@yourdomain.com  # Must be verified in SES
SES_TO_EMAIL=your@email.com                # Your email
SES_CONFIG_SET=aws-newsletter-config       # From deployment
```

## Cost Comparison

### SNS (Current)
- $0.50 per 1 million emails
- 1,000 subscribers × 30 days = 30,000 emails/month = **$0.015/month**

### SES (Proposed)
- $0.10 per 1,000 emails
- 1,000 subscribers × 30 days = 30,000 emails/month = **$3.00/month**

**Wait, SES is MORE expensive?** 🤔

Actually:
- SNS is cheaper BUT plain text only and terrible for newsletters
- SES is standard for professional newsletters
- Most email services charge $20-50/month for 1,000 subscribers
- SES at $3/month is extremely cheap for a professional newsletter

## Recommended Approach

### For Personal Use (Just You)
**Keep SNS** - It's working fine for 1 person
```bash
# Current deployment is perfect
python deploy_full_stack.py --email your@email.com
```

### For Real Newsletter (Multiple Subscribers)
**Migrate to SES** - Professional and scalable

Would you like me to:
1. **Keep SNS** (simpler, current solution works for personal use)
2. **Create full SES deployment script** (professional newsletter service)
3. **Hybrid approach** (SNS for testing, SES for production)

Let me know your use case!
