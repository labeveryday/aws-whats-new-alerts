"""
Strands Agents tool that can:
Create, list, and manage Amazon SQS queues
Send, receive, and manage SQS messages
"""
import boto3
import json
from strands import tool


@tool
def create_queue(queue_name: str, visibility_timeout: int = 30, message_retention_period: int = 1209600) -> str:
    """Create a new SQS queue.

    Args:
        queue_name: Name for the new queue
        visibility_timeout: Visibility timeout in seconds (default: 30)
        message_retention_period: Message retention period in seconds (default: 14 days)

    Returns:
        Creation result with queue URL
    """
    sqs = boto3.client("sqs")
    
    try:
        attributes = {
            "VisibilityTimeoutSeconds": str(visibility_timeout),
            "MessageRetentionPeriod": str(message_retention_period)
        }
        
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes=attributes
        )
        
        queue_url = response["QueueUrl"]
        
        result = {
            "status": "success",
            "queue_name": queue_name,
            "queue_url": queue_url,
            "visibility_timeout": visibility_timeout,
            "message_retention_period": message_retention_period
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error creating queue: {str(e)}"


@tool
def delete_queue(queue_url: str) -> str:
    """Delete an SQS queue.

    Args:
        queue_url: URL of the queue to delete

    Returns:
        Deletion result
    """
    sqs = boto3.client("sqs")
    
    try:
        # Get queue name for confirmation message
        queue_name = queue_url.split("/")[-1]
        
        sqs.delete_queue(QueueUrl=queue_url)
        
        return f"✅ Successfully deleted queue: {queue_name} ({queue_url})"
        
    except sqs.exceptions.QueueDoesNotExist:
        return f"❌ Queue not found: {queue_url}"
    except Exception as e:
        return f"❌ Error deleting queue: {str(e)}"


@tool
def list_queues(queue_name_prefix: str = "") -> str:
    """List all SQS queues, optionally filtered by name prefix.

    Args:
        queue_name_prefix: Optional prefix to filter queue names

    Returns:
        Formatted list of queue URLs and names
    """
    sqs = boto3.client("sqs")
    
    try:
        list_args = {}
        if queue_name_prefix:
            list_args["QueueNamePrefix"] = queue_name_prefix
            
        response = sqs.list_queues(**list_args)
        queue_urls = response.get("QueueUrls", [])
        
        if not queue_urls:
            return "No SQS queues found"
        
        formatted_queues = []
        for queue_url in queue_urls:
            queue_name = queue_url.split("/")[-1]
            formatted_queues.append(f"Name: {queue_name}, URL: {queue_url}")
        
        return "\n".join(formatted_queues)
        
    except Exception as e:
        return f"❌ Error listing queues: {str(e)}"


@tool
def send_message(queue_url: str, message_body: str, delay_seconds: int = 0) -> str:
    """Send a message directly to an SQS queue.

    Args:
        queue_url: URL of the queue
        message_body: Message content to send
        delay_seconds: Delay before message becomes available (0-900 seconds)

    Returns:
        Send result with message ID
    """
    sqs = boto3.client("sqs")
    
    try:
        send_args = {
            "QueueUrl": queue_url,
            "MessageBody": message_body
        }
        
        if delay_seconds > 0:
            send_args["DelaySeconds"] = delay_seconds
            
        response = sqs.send_message(**send_args)
        message_id = response["MessageId"]
        
        result = {
            "status": "success",
            "message_id": message_id,
            "queue_url": queue_url,
            "delay_seconds": delay_seconds,
            "message_preview": message_body[:50] + "..." if len(message_body) > 50 else message_body
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error sending message: {str(e)}"


@tool
def receive_message(queue_url: str, max_messages: int = 1, visibility_timeout: int = 30, wait_time: int = 0) -> str:
    """Receive messages from an SQS queue.

    Args:
        queue_url: URL of the queue
        max_messages: Maximum number of messages to receive (1-10)
        visibility_timeout: Visibility timeout for received messages in seconds
        wait_time: Long polling wait time in seconds (0-20)

    Returns:
        Received messages with receipt handles
    """
    sqs = boto3.client("sqs")
    
    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            VisibilityTimeoutSeconds=visibility_timeout,
            WaitTimeSeconds=min(wait_time, 20),
            AttributeNames=['All']
        )
        
        messages = response.get("Messages", [])
        
        if not messages:
            return f"🔍 No messages available in queue: {queue_url}"
        
        formatted_messages = []
        for msg in messages:
            message_info = {
                "message_id": msg["MessageId"],
                "receipt_handle": msg["ReceiptHandle"],
                "body": msg["Body"],
                "attributes": msg.get("Attributes", {})
            }
            formatted_messages.append(message_info)
        
        result = {
            "queue_url": queue_url,
            "messages_received": len(formatted_messages),
            "messages": formatted_messages
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error receiving messages: {str(e)}"


@tool
def purge_queue(queue_url: str) -> str:
    """Delete all messages from an SQS queue.

    Args:
        queue_url: URL of the queue to purge

    Returns:
        Purge result
    """
    sqs = boto3.client("sqs")
    
    try:
        sqs.purge_queue(QueueUrl=queue_url)
        queue_name = queue_url.split("/")[-1]
        
        return f"✅ Successfully purged all messages from queue: {queue_name}"
        
    except sqs.exceptions.QueueDoesNotExist:
        return f"❌ Queue not found: {queue_url}"
    except Exception as e:
        return f"❌ Error purging queue: {str(e)}"


@tool
def verify_message_delivered(queue_url: str, message_id: str = "", timeout_seconds: int = 10) -> str:
    """Verify that a message was delivered to SQS from SNS.

    Args:
        queue_url: URL of the SQS queue to check
        message_id: Optional specific message ID to look for
        timeout_seconds: How long to wait for messages

    Returns:
        Verification result with message details
    """
    sqs = boto3.client("sqs")
    
    try:
        # Poll for messages
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=min(timeout_seconds, 20),
            AttributeNames=['All']
        )
        
        messages = response.get("Messages", [])
        
        if not messages:
            return f"🔍 No messages found in queue: {queue_url}"
        
        verified_messages = []
        target_found = False
        
        for msg in messages:
            try:
                # Parse SNS message from SQS body
                sns_message = json.loads(msg["Body"])
                
                msg_info = {
                    "sns_message_id": sns_message.get("MessageId"),
                    "timestamp": sns_message.get("Timestamp"),
                    "subject": sns_message.get("Subject"),
                    "message_preview": (sns_message.get("Message", "")[:100] + "..." 
                                      if len(sns_message.get("Message", "")) > 100 
                                      else sns_message.get("Message", "")),
                    "topic_arn": sns_message.get("TopicArn"),
                    "receipt_handle": msg["ReceiptHandle"]
                }
                
                verified_messages.append(msg_info)
                
                # Check if this is the specific message we're looking for
                if message_id and message_id.strip() and sns_message.get("MessageId") == message_id:
                    target_found = True
                    
            except json.JSONDecodeError:
                # Handle non-SNS messages
                verified_messages.append({
                    "raw_message": msg["Body"][:100] + "..." if len(msg["Body"]) > 100 else msg["Body"],
                    "receipt_handle": msg["ReceiptHandle"]
                })
        
        result = {
            "queue_url": queue_url,
            "total_messages_found": len(verified_messages),
            "messages": verified_messages
        }
        
        if message_id and message_id.strip():
            result["target_message_found"] = target_found
            if target_found:
                result["status"] = "✅ Message verification successful"
            else:
                result["status"] = f"⚠️ Target message {message_id} not found"
        else:
            result["status"] = f"✅ Found {len(verified_messages)} messages"
            
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error verifying messages: {str(e)}"


@tool 
def get_queue_message_count(queue_url: str) -> str:
    """Get the current message count in an SQS queue.

    Args:
        queue_url: URL of the SQS queue

    Returns:
        Message count information
    """
    import boto3
    import json
    
    sqs = boto3.client("sqs")
    
    try:
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        
        attrs = response["Attributes"]
        
        result = {
            "queue_url": queue_url,
            "visible_messages": int(attrs.get("ApproximateNumberOfMessages", 0)),
            "in_flight_messages": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "delayed_messages": int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
            "total_approximate": (int(attrs.get("ApproximateNumberOfMessages", 0)) + 
                                int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)) +
                                int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)))
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"❌ Error getting queue attributes: {str(e)}"


@tool
def cleanup_queue_messages(queue_url: str, receipt_handles: list) -> str:
    """Delete specific messages from SQS queue after verification.

    Args:
        queue_url: URL of the SQS queue
        receipt_handles: List of receipt handles to delete

    Returns:
        Cleanup result
    """
    sqs = boto3.client("sqs")
    
    if not receipt_handles:
        return "⚠️ No receipt handles provided for cleanup"
    
    deleted_count = 0
    errors = []
    
    for receipt_handle in receipt_handles:
        try:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            deleted_count += 1
        except Exception as e:
            errors.append(f"Failed to delete message: {str(e)}")
    
    result = f"✅ Successfully deleted {deleted_count} messages"
    if errors:
        result += f"\n❌ Errors: {'; '.join(errors)}"
    
    return result