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


def _get_config():
    """Get configuration at call time (after secrets are loaded)."""
    return {
        "topic_arn": os.getenv("SNS_TOPIC_ARN"),
        "region": os.getenv("AWS_REGION"),
        "email": os.getenv("NEWSLETTER_EMAIL")
    }


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
    config = _get_config()
    topic_arn = config["topic_arn"]
    region = config["region"]

    if not topic_arn:
        return "❌ Error: Newsletter topic not configured (SNS_TOPIC_ARN missing)"

    # Validate subject length (SNS email has ~100 char limit)
    if len(subject) > 100:
        return f"❌ Error: Subject too long ({len(subject)} chars). Keep under 100 characters for email delivery."

    client = boto3.client("sns", region_name=region)

    try:
        # Publish to the configured newsletter topic only
        response = client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )

        message_id = response["MessageId"]
        topic_name = topic_arn.split(":")[-1]

        result = {
            "status": "success",
            "message_id": message_id,
            "topic_name": topic_name,
            "subject": subject,
            "message_length": len(message),
            "subject_length": len(subject),
            "recipient_email": config["email"] or "configured subscribers"
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
    config = _get_config()
    topic_arn = config["topic_arn"]

    if not topic_arn:
        return "❌ Newsletter topic not configured (SNS_TOPIC_ARN missing)"

    return json.dumps({
        "topic_arn": topic_arn,
        "topic_name": topic_arn.split(":")[-1],
        "region": config["region"],
        "recipient_email": config["email"] or "Not configured",
        "subject_limit": "100 characters (for email delivery)",
        "message_limit": "~256KB (but email may have lower practical limits)"
    }, indent=2)