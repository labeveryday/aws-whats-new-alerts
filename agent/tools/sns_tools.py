"""
Strands Agents tool that can:
Create, delete, and list Amazon SNS topics
Create, delete, and list Amazon SNS subscriptions
Publish messages to SNS topics
Verify topic existence and manage topic attributes
"""
import boto3
import json
from strands import tool


@tool
def create_topic(topic_name: str, display_name: str = "") -> str:
    """Create a new SNS topic.

    Args:
        topic_name: Name for the new topic
        display_name: Optional display name for the topic

    Returns:
        Creation result with topic ARN
    """
    client = boto3.client("sns")
    
    try:
        create_args = {"Name": topic_name}
        if display_name:
            create_args["Attributes"] = {"DisplayName": display_name}
            
        response = client.create_topic(**create_args)
        topic_arn = response["TopicArn"]
        
        result = {
            "status": "success",
            "topic_name": topic_name,
            "topic_arn": topic_arn,
            "display_name": display_name or "None"
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error creating topic: {str(e)}"


@tool
def delete_topic(topic_arn: str) -> str:
    """Delete an SNS topic.

    Args:
        topic_arn: ARN of the topic to delete

    Returns:
        Deletion result
    """
    client = boto3.client("sns")
    
    try:
        # First verify topic exists
        client.get_topic_attributes(TopicArn=topic_arn)
        
        # Delete the topic
        client.delete_topic(TopicArn=topic_arn)
        
        topic_name = topic_arn.split(":")[-1]
        return f"✅ Successfully deleted topic: {topic_name} ({topic_arn})"
        
    except client.exceptions.NotFoundError:
        return f"❌ Topic not found: {topic_arn}"
    except Exception as e:
        return f"❌ Error deleting topic: {str(e)}"


@tool
def list_topics() -> str:
    """List all SNS topics with formatted output.

    Returns:
        Formatted list of topic names and ARNs
    """
    client = boto3.client("sns")
    response = client.list_topics()
    topics = response["Topics"]
    
    if not topics:
        return "No SNS topics found"
    
    formatted_topics = []
    for topic in topics:
        arn = topic["TopicArn"]
        name = arn.split(":")[-1]
        formatted_topics.append(f"Name: {name}, ARN: {arn}")
    
    return "\n".join(formatted_topics)


@tool
def verify_topic_exists(topic_arn: str) -> str:
    """Verify that an SNS topic exists.

    Args:
        topic_arn: ARN of the topic to verify

    Returns:
        Verification result
    """
    try:
        client = boto3.client("sns")
        client.get_topic_attributes(TopicArn=topic_arn)
        return f"✅ Topic exists: {topic_arn}"
    except client.exceptions.NotFoundError:
        return f"❌ Topic not found: {topic_arn}"
    except Exception as e:
        return f"❌ Error verifying topic: {str(e)}"


@tool
def publish_message(topic_arn: str, message: str, subject: str = None) -> str:
    """Publish a message to an SNS topic after verifying it exists.

    Args:
        topic_arn: ARN of the topic
        message: Message to publish
        subject: Optional subject line

    Returns:
        Publication result with message ID
    """    
    # First verify topic exists
    client = boto3.client("sns")
    try:
        client.get_topic_attributes(TopicArn=topic_arn)
    except client.exceptions.NotFoundError:
        return f"❌ Cannot publish: Topic not found: {topic_arn}"
    except Exception as e:
        return f"❌ Error verifying topic: {str(e)}"
    
    # Publish message
    try:
        publish_args = {
            "TopicArn": topic_arn,
            "Message": message
        }
        if subject:
            publish_args["Subject"] = subject
            
        response = client.publish(**publish_args)
        message_id = response["MessageId"]
        
        return json.dumps({
            "status": "success",
            "message_id": message_id,
            "topic_arn": topic_arn,
            "subject": subject or "None",
            "message_preview": message[:50] + "..." if len(message) > 50 else message
        }, indent=2)
    except Exception as e:
        return f"❌ Error publishing message: {str(e)}"


@tool
def list_subscriptions(topic_arn: str = "") -> str:
    """List SNS subscriptions, optionally filtered by topic.

    Args:
        topic_arn: Optional topic ARN to filter subscriptions

    Returns:
        Formatted list of subscriptions
    """
    client = boto3.client("sns")
    
    try:
        if topic_arn:
            response = client.list_subscriptions_by_topic(TopicArn=topic_arn)
        else:
            response = client.list_subscriptions()
            
        subscriptions = response["Subscriptions"]
        
        if not subscriptions:
            return "No subscriptions found"
        
        formatted_subscriptions = []
        for sub in subscriptions:
            subscription_arn = sub["SubscriptionArn"]
            protocol = sub["Protocol"]
            endpoint = sub["Endpoint"]
            topic = sub["TopicArn"].split(":")[-1] if sub["TopicArn"] else "Unknown"
            
            formatted_subscriptions.append(
                f"Topic: {topic}, Protocol: {protocol}, Endpoint: {endpoint}, ARN: {subscription_arn}"
            )
        
        return "\n".join(formatted_subscriptions)
        
    except Exception as e:
        return f"❌ Error listing subscriptions: {str(e)}"


@tool
def create_subscription(topic_arn: str, protocol: str, endpoint: str) -> str:
    """Create a subscription to an SNS topic.

    Args:
        topic_arn: ARN of the topic to subscribe to
        protocol: Protocol for the subscription (email, sms, sqs, http, https, lambda)
        endpoint: Endpoint for the subscription (email address, phone number, queue ARN, etc.)

    Returns:
        Subscription creation result
    """
    client = boto3.client("sns")
    
    try:
        # First verify topic exists
        client.get_topic_attributes(TopicArn=topic_arn)
        
        # Create subscription
        response = client.subscribe(
            TopicArn=topic_arn,
            Protocol=protocol,
            Endpoint=endpoint
        )
        
        subscription_arn = response["SubscriptionArn"]
        
        result = {
            "status": "success",
            "topic_arn": topic_arn,
            "protocol": protocol,
            "endpoint": endpoint,
            "subscription_arn": subscription_arn,
            "pending_confirmation": subscription_arn == "pending confirmation"
        }
        
        return json.dumps(result, indent=2)
        
    except client.exceptions.NotFoundError:
        return f"❌ Topic not found: {topic_arn}"
    except Exception as e:
        return f"❌ Error creating subscription: {str(e)}"


@tool
def delete_subscription(subscription_arn: str) -> str:
    """Delete a subscription from SNS.

    Args:
        subscription_arn: ARN of the subscription to delete

    Returns:
        Deletion result
    """
    client = boto3.client("sns")
    
    try:
        # Delete the subscription
        client.unsubscribe(SubscriptionArn=subscription_arn)
        
        return f"✅ Successfully deleted subscription: {subscription_arn}"
        
    except client.exceptions.NotFoundError:
        return f"❌ Subscription not found: {subscription_arn}"
    except Exception as e:
        return f"❌ Error deleting subscription: {str(e)}"