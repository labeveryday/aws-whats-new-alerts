#!/usr/bin/env python3
"""
Utility functions for both boto3 and CDK deployments
"""

import boto3
import json
from typing import Dict, List, Optional
from botocore.exceptions import ClientError


class NewsletterClient:
    """Client for interacting with deployed newsletter infrastructure"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.sns = boto3.client('sns', region_name=region)
        self.sqs = boto3.client('sqs', region_name=region)
    
    def send_newsletter(self, topic_arn: str, subject: str, message: str) -> str:
        """Send a newsletter to all subscribers"""
        try:
            response = self.sns.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message
            )
            message_id = response['MessageId']
            print(f"✅ Newsletter sent! Message ID: {message_id}")
            return message_id
            
        except ClientError as e:
            print(f"❌ Error sending newsletter: {e}")
            raise
    
    def subscribe_email(self, topic_arn: str, email: str) -> str:
        """Subscribe an email to the newsletter"""
        try:
            response = self.sns.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            subscription_arn = response['SubscriptionArn']
            print(f"✅ Subscribed {email} (confirmation required)")
            return subscription_arn
            
        except ClientError as e:
            print(f"❌ Error subscribing email: {e}")
            raise
    
    def unsubscribe_email(self, subscription_arn: str):
        """Unsubscribe an email from the newsletter"""
        try:
            self.sns.unsubscribe(SubscriptionArn=subscription_arn)
            print(f"✅ Unsubscribed from newsletter")
            
        except ClientError as e:
            print(f"❌ Error unsubscribing: {e}")
            raise
    
    def list_subscriptions(self, topic_arn: str) -> List[Dict]:
        """List all subscriptions for a topic"""
        try:
            response = self.sns.list_subscriptions_by_topic(TopicArn=topic_arn)
            subscriptions = response['Subscriptions']
            
            print(f"📋 Found {len(subscriptions)} subscriptions:")
            for sub in subscriptions:
                status = "✅ Confirmed" if sub['SubscriptionArn'] != 'PendingConfirmation' else "⏳ Pending"
                print(f"  {sub['Endpoint']} ({sub['Protocol']}) - {status}")
            
            return subscriptions
            
        except ClientError as e:
            print(f"❌ Error listing subscriptions: {e}")
            raise
    
    def check_delivery_status(self, queue_url: str, limit: int = 10) -> List[Dict]:
        """Check delivery status messages from SQS"""
        try:
            response = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=limit,
                WaitTimeSeconds=2,
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            status_reports = []
            
            print(f"📊 Checking delivery status... Found {len(messages)} messages")
            
            for message in messages:
                try:
                    body = json.loads(message['Body'])
                    
                    # Handle SNS message format
                    if 'Message' in body:
                        sns_message = json.loads(body['Message'])
                        delivery_info = sns_message.get('delivery', {})
                    else:
                        delivery_info = body.get('delivery', {})
                    
                    status_report = {
                        'message_id': body.get('MessageId') or delivery_info.get('messageId'),
                        'status': delivery_info.get('deliveryStatus') or delivery_info.get('providerResponse'),
                        'timestamp': delivery_info.get('timestamp'),
                        'destination': delivery_info.get('destination'),
                        'provider_response': delivery_info.get('providerResponse'),
                        'receipt_handle': message['ReceiptHandle']
                    }
                    
                    status_reports.append(status_report)
                    
                    # Print status
                    status_emoji = "✅" if status_report['status'] == 'SUCCESS' else "❌"
                    print(f"  {status_emoji} {status_report['message_id']}: {status_report['status']}")
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  Invalid JSON in message: {e}")
                except Exception as e:
                    print(f"⚠️  Error parsing message: {e}")
            
            return status_reports
            
        except ClientError as e:
            print(f"❌ Error checking delivery status: {e}")
            return []
    
    def delete_processed_messages(self, queue_url: str, receipt_handles: List[str]):
        """Delete processed messages from the queue"""
        try:
            for receipt_handle in receipt_handles:
                self.sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
            print(f"🗑️  Deleted {len(receipt_handles)} processed messages")
            
        except ClientError as e:
            print(f"❌ Error deleting messages: {e}")
            raise
    
    def get_queue_stats(self, queue_url: str) -> Dict:
        """Get queue statistics"""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    'ApproximateNumberOfMessages',
                    'ApproximateNumberOfMessagesNotVisible',
                    'ApproximateNumberOfMessagesDelayed'
                ]
            )
            
            attrs = response['Attributes']
            stats = {
                'available_messages': int(attrs.get('ApproximateNumberOfMessages', 0)),
                'in_flight_messages': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
                'delayed_messages': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
            }
            
            print(f"📈 Queue Stats:")
            print(f"  Available: {stats['available_messages']}")
            print(f"  In Flight: {stats['in_flight_messages']}")
            print(f"  Delayed: {stats['delayed_messages']}")
            
            return stats
            
        except ClientError as e:
            print(f"❌ Error getting queue stats: {e}")
            return {}


def create_sample_newsletter() -> Dict[str, str]:
    """Create a sample newsletter for testing"""
    return {
        'subject': '🚀 AWS What\'s New - Weekly Update',
        'message': '''Hello AWS Enthusiasts!

Here's what's new in AWS this week:

🔥 New Features:
• Amazon ECS now supports ARM-based Graviton processors
• AWS Lambda introduces new runtime support for Python 3.11
• Amazon RDS adds enhanced monitoring capabilities

📚 Learn More:
• Check out the new AWS Well-Architected Framework updates
• Join our upcoming webinar on serverless best practices

🎯 Quick Tips:
• Use AWS Cost Explorer to optimize your spending
• Enable AWS CloudTrail for better security monitoring

Happy cloud building!
The AWS Team

---
Unsubscribe: Reply with "STOP" to opt out of future newsletters.
        '''
    }


def validate_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_topic_arn(region: str, account_id: str, topic_name: str) -> str:
    """Format SNS topic ARN"""
    return f"arn:aws:sns:{region}:{account_id}:{topic_name}"


def format_queue_arn(region: str, account_id: str, queue_name: str) -> str:
    """Format SQS queue ARN"""
    return f"arn:aws:sqs:{region}:{account_id}:{queue_name}"