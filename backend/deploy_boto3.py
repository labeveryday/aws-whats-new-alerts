#!/usr/bin/env python3
"""
AWS SNS Newsletter with SQS Tracking - Boto3 Deployment Script

This script creates:
1. SNS topic for email newsletters
2. SQS queue for tracking delivery status
3. IAM policies and roles
4. SNS delivery status notifications
"""

import boto3
import json
import time
from typing import Dict, List, Optional
from botocore.exceptions import ClientError


class NewsletterDeployer:
    def __init__(self, region: str = 'us-east-1', stack_name: str = 'newsletter-demo'):
        self.region = region
        self.stack_name = stack_name
        
        # Initialize AWS clients
        self.sns = boto3.client('sns', region_name=region)
        self.sqs = boto3.client('sqs', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get account ID
        self.account_id = self.sts.get_caller_identity()['Account']
        
        # Resource names
        self.topic_name = f'{stack_name}-newsletter-topic'
        self.queue_name = f'{stack_name}-tracking-queue'
        self.dlq_name = f'{stack_name}-tracking-dlq'
        self.role_name = f'{stack_name}-sns-role'
        self.policy_name = f'{stack_name}-sns-policy'
        
        # Store created resources
        self.resources = {}

    def create_sqs_queues(self) -> Dict[str, str]:
        """Create SQS queues for tracking delivery status"""
        print("Creating SQS queues...")
        
        # Create Dead Letter Queue first
        try:
            dlq_response = self.sqs.create_queue(
                QueueName=self.dlq_name,
                Attributes={
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeoutSeconds': '60'
                }
            )
            dlq_url = dlq_response['QueueUrl']
            dlq_arn = self.sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']
            
            print(f"✓ Created DLQ: {dlq_arn}")
            
            # Create main tracking queue with DLQ
            redrive_policy = {
                "deadLetterTargetArn": dlq_arn,
                "maxReceiveCount": 3
            }
            
            queue_response = self.sqs.create_queue(
                QueueName=self.queue_name,
                Attributes={
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeoutSeconds': '60',
                    'RedrivePolicy': json.dumps(redrive_policy)
                }
            )
            queue_url = queue_response['QueueUrl']
            queue_arn = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']
            
            print(f"✓ Created tracking queue: {queue_arn}")
            
            self.resources['dlq_url'] = dlq_url
            self.resources['dlq_arn'] = dlq_arn
            self.resources['queue_url'] = queue_url
            self.resources['queue_arn'] = queue_arn
            
            return {
                'queue_arn': queue_arn,
                'queue_url': queue_url,
                'dlq_arn': dlq_arn,
                'dlq_url': dlq_url
            }
            
        except ClientError as e:
            print(f"Error creating SQS queues: {e}")
            raise

    def create_iam_role(self, queue_arn: str) -> str:
        """Create IAM role for SNS to write to SQS"""
        print("Creating IAM role...")
        
        # Trust policy for SNS
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sns.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Policy to allow SNS to write to SQS
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "sqs:SendMessage"
                    ],
                    "Resource": queue_arn
                }
            ]
        }
        
        try:
            # Create role
            role_response = self.iam.create_role(
                RoleName=self.role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for {self.stack_name} SNS to write to SQS"
            )
            role_arn = role_response['Role']['Arn']
            
            # Create and attach policy
            self.iam.create_policy(
                PolicyName=self.policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=f"Policy for {self.stack_name} SNS to SQS access"
            )
            
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{self.policy_name}"
            
            self.iam.attach_role_policy(
                RoleName=self.role_name,
                PolicyArn=policy_arn
            )
            
            print(f"✓ Created IAM role: {role_arn}")
            
            self.resources['role_arn'] = role_arn
            self.resources['policy_arn'] = policy_arn
            
            # Wait for role to be available
            time.sleep(10)
            
            return role_arn
            
        except ClientError as e:
            print(f"Error creating IAM role: {e}")
            raise

    def create_sns_topic(self, role_arn: str, queue_arn: str) -> str:
        """Create SNS topic with delivery status logging"""
        print("Creating SNS topic...")
        
        try:
            # Create topic
            topic_response = self.sns.create_topic(Name=self.topic_name)
            topic_arn = topic_response['TopicArn']
            
            # Configure delivery status logging
            delivery_status_attributes = {
                'DefaultSMSType': 'Transactional',
                'DeliveryStatusLogging': json.dumps({
                    'successFeedbackRoleArn': role_arn,
                    'successFeedbackSampleRate': '100',
                    'failureFeedbackRoleArn': role_arn
                })
            }
            
            # Set topic attributes for email delivery status
            self.sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPSuccessFeedbackRoleArn',
                AttributeValue=role_arn
            )
            self.sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPFailureFeedbackRoleArn', 
                AttributeValue=role_arn
            )
            self.sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPSuccessFeedbackSampleRate',
                AttributeValue='100'
            )
            
            print(f"✓ Created SNS topic: {topic_arn}")
            
            self.resources['topic_arn'] = topic_arn
            return topic_arn
            
        except ClientError as e:
            print(f"Error creating SNS topic: {e}")
            raise

    def setup_queue_policy(self, queue_arn: str, topic_arn: str):
        """Set up SQS queue policy to allow SNS to send messages"""
        print("Setting up SQS queue policy...")
        
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sns.amazonaws.com"
                    },
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": topic_arn
                        }
                    }
                }
            ]
        }
        
        try:
            self.sqs.set_queue_attributes(
                QueueUrl=self.resources['queue_url'],
                Attributes={
                    'Policy': json.dumps(queue_policy)
                }
            )
            print("✓ Set up queue policy for SNS access")
            
        except ClientError as e:
            print(f"Error setting queue policy: {e}")
            raise

    def subscribe_email(self, topic_arn: str, email: str) -> str:
        """Subscribe an email to the newsletter topic"""
        try:
            response = self.sns.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            subscription_arn = response['SubscriptionArn']
            print(f"✓ Subscribed {email} to newsletter (confirmation required)")
            return subscription_arn
            
        except ClientError as e:
            print(f"Error subscribing email: {e}")
            raise

    def deploy(self, test_email: Optional[str] = None) -> Dict[str, str]:
        """Deploy the complete newsletter infrastructure"""
        print(f"🚀 Deploying newsletter infrastructure: {self.stack_name}")
        print(f"Region: {self.region}")
        print("-" * 50)
        
        try:
            # Step 1: Create SQS queues
            queues = self.create_sqs_queues()
            
            # Step 2: Create IAM role
            role_arn = self.create_iam_role(queues['queue_arn'])
            
            # Step 3: Create SNS topic
            topic_arn = self.create_sns_topic(role_arn, queues['queue_arn'])
            
            # Step 4: Set up queue policy
            self.setup_queue_policy(queues['queue_arn'], topic_arn)
            
            # Step 5: Subscribe test email if provided
            if test_email:
                self.subscribe_email(topic_arn, test_email)
            
            print("-" * 50)
            print("✅ Deployment completed successfully!")
            print(f"Topic ARN: {topic_arn}")
            print(f"Queue ARN: {queues['queue_arn']}")
            
            if test_email:
                print(f"\n📧 Check {test_email} for subscription confirmation")
            
            return self.resources
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            print("Attempting cleanup...")
            self.cleanup()
            raise

    def send_test_newsletter(self, subject: str, message: str):
        """Send a test newsletter"""
        if 'topic_arn' not in self.resources:
            print("❌ Topic not found. Deploy first.")
            return
            
        try:
            response = self.sns.publish(
                TopicArn=self.resources['topic_arn'],
                Subject=subject,
                Message=message
            )
            print(f"✅ Newsletter sent! Message ID: {response['MessageId']}")
            return response['MessageId']
            
        except ClientError as e:
            print(f"Error sending newsletter: {e}")
            raise

    def check_delivery_status(self, limit: int = 10) -> List[Dict]:
        """Check delivery status messages from SQS"""
        if 'queue_url' not in self.resources:
            print("❌ Queue not found. Deploy first.")
            return []
            
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.resources['queue_url'],
                MaxNumberOfMessages=limit,
                WaitTimeSeconds=1
            )
            
            messages = response.get('Messages', [])
            status_reports = []
            
            for message in messages:
                try:
                    body = json.loads(message['Body'])
                    status_reports.append({
                        'message_id': body.get('MessageId'),
                        'status': body.get('delivery', {}).get('deliveryStatus'),
                        'timestamp': body.get('delivery', {}).get('timestamp'),
                        'destination': body.get('delivery', {}).get('destination'),
                        'receipt_handle': message['ReceiptHandle']
                    })
                except json.JSONDecodeError:
                    print(f"Invalid JSON in message: {message['Body']}")
            
            print(f"📊 Found {len(status_reports)} delivery status reports")
            return status_reports
            
        except ClientError as e:
            print(f"Error checking delivery status: {e}")
            return []

    def cleanup(self):
        """Clean up all created resources"""
        print("🧹 Cleaning up resources...")
        
        # Delete SNS topic
        if 'topic_arn' in self.resources:
            try:
                self.sns.delete_topic(TopicArn=self.resources['topic_arn'])
                print("✓ Deleted SNS topic")
            except ClientError as e:
                print(f"Error deleting topic: {e}")
        
        # Delete SQS queues
        for queue_key in ['queue_url', 'dlq_url']:
            if queue_key in self.resources:
                try:
                    self.sqs.delete_queue(QueueUrl=self.resources[queue_key])
                    print(f"✓ Deleted SQS queue: {queue_key}")
                except ClientError as e:
                    print(f"Error deleting queue: {e}")
        
        # Detach and delete IAM policy
        if 'policy_arn' in self.resources:
            try:
                self.iam.detach_role_policy(
                    RoleName=self.role_name,
                    PolicyArn=self.resources['policy_arn']
                )
                self.iam.delete_policy(PolicyArn=self.resources['policy_arn'])
                print("✓ Deleted IAM policy")
            except ClientError as e:
                print(f"Error deleting policy: {e}")
        
        # Delete IAM role
        if 'role_arn' in self.resources:
            try:
                self.iam.delete_role(RoleName=self.role_name)
                print("✓ Deleted IAM role")
            except ClientError as e:
                print(f"Error deleting role: {e}")
        
        print("✅ Cleanup completed")


def main():
    """Main deployment script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy SNS Newsletter with SQS Tracking')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--stack-name', default='newsletter-demo', help='Stack name prefix')
    parser.add_argument('--email', help='Test email to subscribe')
    parser.add_argument('--cleanup', action='store_true', help='Clean up resources')
    parser.add_argument('--send-test', nargs=2, metavar=('SUBJECT', 'MESSAGE'), 
                       help='Send test newsletter')
    parser.add_argument('--check-status', action='store_true', 
                       help='Check delivery status')
    
    args = parser.parse_args()
    
    deployer = NewsletterDeployer(region=args.region, stack_name=args.stack_name)
    
    try:
        if args.cleanup:
            deployer.cleanup()
        elif args.send_test:
            deployer.send_test_newsletter(args.send_test[0], args.send_test[1])
        elif args.check_status:
            status_reports = deployer.check_delivery_status()
            for report in status_reports:
                print(f"Message {report['message_id']}: {report['status']} at {report['timestamp']}")
        else:
            deployer.deploy(test_email=args.email)
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())