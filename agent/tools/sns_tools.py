"""
Secure SNS tool that ONLY allows publishing to the configured newsletter topic.
No create, delete, list, or other operations allowed.
"""
import os
import boto3
import json
from strands import tool
from dotenv import load_dotenv
from botocore.exceptions import ClientError


load_dotenv()


# Get the configured newsletter topic from environment
NEWSLETTER_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


@tool
def publish_to_newsletter_topic(subject: str, message: str) -> str:
    """Publish a message to the configured newsletter SNS topic ONLY.
    
    This tool is restricted to only publish to the pre-configured newsletter topic
    for security. It cannot access any other SNS topics or perform other operations.
    
    Args:
        subject: Email subject line (keep under 100 characters for email delivery)
        message: Newsletter message content
    
    Returns:
        Publication result with message ID
    """
    if not NEWSLETTER_TOPIC_ARN:
        return "❌ Error: Newsletter topic not configured (SNS_TOPIC_ARN missing)"
    
    # Validate subject length (SNS email has ~100 char limit)
    if len(subject) > 100:
        return f"❌ Error: Subject too long ({len(subject)} chars). Keep under 100 characters for email delivery."
    
    client = boto3.client("sns", region_name=AWS_REGION)
    
    try:
        # Publish to the configured newsletter topic only
        response = client.publish(
            TopicArn=NEWSLETTER_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        
        message_id = response["MessageId"]
        topic_name = NEWSLETTER_TOPIC_ARN.split(":")[-1]
        
        result = {
            "status": "success",
            "message_id": message_id,
            "topic_name": topic_name,
            "subject": subject,
            "message_length": len(message),
            "subject_length": len(subject),
            "recipient_email": os.getenv("NEWSLETTER_EMAIL", "configured subscribers")
        }
        
        return json.dumps(result, indent=2)
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        return f"❌ AWS Error: {error_code} - {e.response['Error']['Message']}"
    except Exception as e:
        return f"❌ Error publishing newsletter: {str(e)}"


@tool
def get_newsletter_topic_info() -> str:
    """Get information about the configured newsletter topic (read-only).
    
    Returns basic info about the newsletter topic without exposing other topics.
    """
    if not NEWSLETTER_TOPIC_ARN:
        return "❌ Newsletter topic not configured (SNS_TOPIC_ARN missing)"
    
    return json.dumps({
        "topic_arn": NEWSLETTER_TOPIC_ARN,
        "topic_name": NEWSLETTER_TOPIC_ARN.split(":")[-1],
        "region": AWS_REGION,
        "recipient_email": os.getenv("NEWSLETTER_EMAIL", "Not configured"),
        "subject_limit": "100 characters (for email delivery)",
        "message_limit": "~256KB (but email may have lower practical limits)"
    }, indent=2)