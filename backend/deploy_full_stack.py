#!/usr/bin/env python3
"""
AWS Newsletter Full Stack Deployment

This script creates:
1. SNS topic for email newsletters
2. SQS queue for tracking delivery status
3. Dead Letter Queue for failed messages
4. IAM policies and roles
5. AgentCore Memory for tracking processed articles
6. Outputs all configuration to .env file
"""

import boto3
import json
import time
import os
from typing import Dict, List, Optional
from botocore.exceptions import ClientError


class FullStackDeployer:
    def __init__(self, region: str = 'us-east-1', stack_name: str = 'aws-newsletter'):
        self.region = region
        self.stack_name = stack_name

        # Initialize AWS clients
        self.sns = boto3.client('sns', region_name=region)
        self.sqs = boto3.client('sqs', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        self.bedrock_agentcore = boto3.client('bedrock-agentcore-control', region_name=region)

        # Get account ID
        self.account_id = self.sts.get_caller_identity()['Account']

        # Resource names
        self.topic_name = f'{stack_name}-newsletter-topic'
        self.queue_name = f'{stack_name}-tracking-queue'
        self.dlq_name = f'{stack_name}-tracking-dlq'
        self.role_name = f'{stack_name}-sns-role'
        self.policy_name = f'{stack_name}-sns-policy'
        self.memory_name = f'{stack_name}-agent-memory'

        # Store created resources
        self.resources = {}

    def create_sqs_queues(self) -> Dict[str, str]:
        """Create SQS queues for tracking delivery status"""
        print("\n📦 Creating SQS queues...")

        try:
            # Create Dead Letter Queue first
            dlq_response = self.sqs.create_queue(
                QueueName=self.dlq_name,
                Attributes={
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeout': '60'
                }
            )
            dlq_url = dlq_response['QueueUrl']
            dlq_arn = self.sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']

            print(f"  ✓ Created DLQ: {dlq_arn}")

            # Create main tracking queue with DLQ
            redrive_policy = {
                "deadLetterTargetArn": dlq_arn,
                "maxReceiveCount": 3
            }

            queue_response = self.sqs.create_queue(
                QueueName=self.queue_name,
                Attributes={
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeout': '60',
                    'RedrivePolicy': json.dumps(redrive_policy)
                }
            )
            queue_url = queue_response['QueueUrl']
            queue_arn = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']

            print(f"  ✓ Created tracking queue: {queue_arn}")

            self.resources.update({
                'dlq_url': dlq_url,
                'dlq_arn': dlq_arn,
                'queue_url': queue_url,
                'queue_arn': queue_arn
            })

            return {
                'queue_arn': queue_arn,
                'queue_url': queue_url,
                'dlq_arn': dlq_arn,
                'dlq_url': dlq_url
            }

        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                print(f"  ⚠️  Queues already exist, retrieving...")
                queue_url = self.sqs.get_queue_url(QueueName=self.queue_name)['QueueUrl']
                queue_arn = self.sqs.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['QueueArn']
                )['Attributes']['QueueArn']
                dlq_url = self.sqs.get_queue_url(QueueName=self.dlq_name)['QueueUrl']
                dlq_arn = self.sqs.get_queue_attributes(
                    QueueUrl=dlq_url,
                    AttributeNames=['QueueArn']
                )['Attributes']['QueueArn']

                self.resources.update({
                    'dlq_url': dlq_url,
                    'dlq_arn': dlq_arn,
                    'queue_url': queue_url,
                    'queue_arn': queue_arn
                })

                return {
                    'queue_arn': queue_arn,
                    'queue_url': queue_url,
                    'dlq_arn': dlq_arn,
                    'dlq_url': dlq_url
                }
            else:
                print(f"  ❌ Error creating SQS queues: {e}")
                raise

    def create_iam_role(self, queue_arn: str) -> str:
        """Create IAM role for SNS to write to SQS"""
        print("\n🔐 Creating IAM role...")

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
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "*"
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
            policy_response = self.iam.create_policy(
                PolicyName=self.policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=f"Policy for {self.stack_name} SNS to SQS access"
            )
            policy_arn = policy_response['Policy']['Arn']

            self.iam.attach_role_policy(
                RoleName=self.role_name,
                PolicyArn=policy_arn
            )

            print(f"  ✓ Created IAM role: {role_arn}")

            self.resources['role_arn'] = role_arn
            self.resources['policy_arn'] = policy_arn

            # Wait for role to be available
            print("  ⏳ Waiting for role propagation (10s)...")
            time.sleep(10)

            return role_arn

        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"  ⚠️  Role already exists, retrieving...")
                role_arn = f"arn:aws:iam::{self.account_id}:role/{self.role_name}"
                policy_arn = f"arn:aws:iam::{self.account_id}:policy/{self.policy_name}"
                self.resources['role_arn'] = role_arn
                self.resources['policy_arn'] = policy_arn
                return role_arn
            else:
                print(f"  ❌ Error creating IAM role: {e}")
                raise

    def create_sns_topic(self, role_arn: str, queue_arn: str) -> str:
        """Create SNS topic with delivery status logging"""
        print("\n📧 Creating SNS topic...")

        try:
            # Create topic
            topic_response = self.sns.create_topic(
                Name=self.topic_name,
                Attributes={
                    'DisplayName': f'{self.stack_name} Newsletter'
                }
            )
            topic_arn = topic_response['TopicArn']

            # Configure delivery status logging
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

            print(f"  ✓ Created SNS topic: {topic_arn}")

            self.resources['topic_arn'] = topic_arn
            return topic_arn

        except ClientError as e:
            print(f"  ❌ Error creating SNS topic: {e}")
            raise

    def setup_queue_policy(self, queue_arn: str, topic_arn: str):
        """Set up SQS queue policy to allow SNS to send messages"""
        print("\n🔗 Setting up SQS queue policy...")

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
            print("  ✓ Set up queue policy for SNS access")

        except ClientError as e:
            print(f"  ❌ Error setting queue policy: {e}")
            raise

    def create_agentcore_memory(self) -> str:
        """Create AgentCore Memory for tracking processed articles"""
        print("\n🧠 Creating AgentCore Memory...")

        try:
            # Create memory with semantic strategy
            response = self.bedrock_agentcore.create_memory(
                name=self.memory_name,
                description=f"Memory store for {self.stack_name} agent to track processed AWS articles and newsletter history",
                # Use default configuration - memory will be created with standard settings
            )

            memory_id = response['memory']['id']
            memory_arn = response['memory']['arn']

            print(f"  ✓ Created AgentCore Memory: {memory_id}")
            print(f"  ⏳ Memory provisioning takes 2-5 minutes...")
            print(f"  💡 You can continue - the agent will wait for memory to be ready")

            self.resources['memory_id'] = memory_id
            self.resources['memory_arn'] = memory_arn

            return memory_id

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                print(f"  ⚠️  Memory already exists, retrieving...")
                # List memories and find ours
                memories = self.bedrock_agentcore.list_memories()
                for memory in memories.get('memories', []):
                    if memory['name'] == self.memory_name:
                        memory_id = memory['id']
                        memory_arn = memory['arn']
                        self.resources['memory_id'] = memory_id
                        self.resources['memory_arn'] = memory_arn
                        print(f"  ✓ Found existing memory: {memory_id}")
                        return memory_id
                raise Exception(f"Memory {self.memory_name} exists but couldn't be retrieved")
            else:
                print(f"  ❌ Error creating AgentCore Memory: {e}")
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
            print(f"  ✓ Subscribed {email} to newsletter (confirmation required)")
            return subscription_arn

        except ClientError as e:
            print(f"  ❌ Error subscribing email: {e}")
            raise

    def write_env_file(self, env_path: str = '.env'):
        """Write all configuration to .env file"""
        print(f"\n📝 Writing configuration to {env_path}...")

        env_content = f"""# AWS Newsletter Configuration
# Auto-generated by deploy_full_stack.py
# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

# AWS Configuration
AWS_REGION={self.region}
AWS_ACCOUNT_ID={self.account_id}

# SNS Configuration
SNS_TOPIC_ARN={self.resources.get('topic_arn', '')}

# SQS Configuration
SQS_QUEUE_URL={self.resources.get('queue_url', '')}
SQS_QUEUE_ARN={self.resources.get('queue_arn', '')}
SQS_DLQ_URL={self.resources.get('dlq_url', '')}
SQS_DLQ_ARN={self.resources.get('dlq_arn', '')}

# IAM Configuration
SNS_ROLE_ARN={self.resources.get('role_arn', '')}
SNS_POLICY_ARN={self.resources.get('policy_arn', '')}

# AgentCore Memory Configuration
BEDROCK_AGENTCORE_MEMORY_ID={self.resources.get('memory_id', '')}
BEDROCK_AGENTCORE_MEMORY_ARN={self.resources.get('memory_arn', '')}

# Stack Configuration
STACK_NAME={self.stack_name}

# Agent Configuration (set after deployment)
# AGENTCORE_ARN=arn:aws:bedrock-agentcore:region:account:agent-runtime/runtime-id
"""

        # Write to parent directory (project root)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file_path = os.path.join(parent_dir, env_path)

        with open(env_file_path, 'w') as f:
            f.write(env_content)

        print(f"  ✓ Configuration written to {env_file_path}")
        print(f"\n  📋 Summary:")
        print(f"     SNS Topic ARN: {self.resources.get('topic_arn', 'N/A')}")
        print(f"     SQS Queue URL: {self.resources.get('queue_url', 'N/A')}")
        print(f"     Memory ID: {self.resources.get('memory_id', 'N/A')}")

    def deploy(self, test_email: Optional[str] = None) -> Dict[str, str]:
        """Deploy the complete newsletter infrastructure"""
        print("=" * 70)
        print(f"🚀 Deploying Full Newsletter Stack: {self.stack_name}")
        print(f"📍 Region: {self.region}")
        print(f"🔑 Account: {self.account_id}")
        print("=" * 70)

        try:
            # Step 1: Create SQS queues
            queues = self.create_sqs_queues()

            # Step 2: Create IAM role
            role_arn = self.create_iam_role(queues['queue_arn'])

            # Step 3: Create SNS topic
            topic_arn = self.create_sns_topic(role_arn, queues['queue_arn'])

            # Step 4: Set up queue policy
            self.setup_queue_policy(queues['queue_arn'], topic_arn)

            # Step 5: Create AgentCore Memory
            memory_id = self.create_agentcore_memory()

            # Step 6: Subscribe test email if provided
            if test_email:
                print(f"\n📧 Subscribing test email...")
                self.subscribe_email(topic_arn, test_email)
                print(f"  💡 Check {test_email} for confirmation email")

            # Step 7: Write .env file
            self.write_env_file()

            print("\n" + "=" * 70)
            print("✅ DEPLOYMENT COMPLETED SUCCESSFULLY!")
            print("=" * 70)

            print("\n📌 Next Steps:")
            print("   1. Check your email for SNS subscription confirmation (if provided)")
            print("   2. Wait 2-5 minutes for AgentCore Memory to be ready")
            print("   3. Deploy your agent using: cd ../deployment && agentcore configure -e agent.py")
            print("   4. Launch your agent using: agentcore launch")
            print("   5. Update AGENTCORE_ARN in .env after agent deployment")

            return self.resources

        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            print("   Partial resources may have been created.")
            print("   Run with --cleanup to remove resources, or re-run to continue.")
            raise

    def cleanup(self):
        """Clean up all created resources"""
        print("\n" + "=" * 70)
        print("🧹 CLEANING UP RESOURCES")
        print("=" * 70)

        # Delete AgentCore Memory
        if 'memory_id' in self.resources:
            print("\n🧠 Deleting AgentCore Memory...")
            try:
                self.bedrock_agentcore.delete_memory(memoryId=self.resources['memory_id'])
                print("  ✓ Deleted AgentCore Memory")
            except ClientError as e:
                print(f"  ⚠️  Error deleting memory: {e}")

        # Delete SNS topic
        if 'topic_arn' in self.resources:
            print("\n📧 Deleting SNS topic...")
            try:
                self.sns.delete_topic(TopicArn=self.resources['topic_arn'])
                print("  ✓ Deleted SNS topic")
            except ClientError as e:
                print(f"  ⚠️  Error deleting topic: {e}")

        # Delete SQS queues
        print("\n📦 Deleting SQS queues...")
        for queue_key in ['queue_url', 'dlq_url']:
            if queue_key in self.resources:
                try:
                    self.sqs.delete_queue(QueueUrl=self.resources[queue_key])
                    print(f"  ✓ Deleted SQS queue: {queue_key}")
                except ClientError as e:
                    print(f"  ⚠️  Error deleting queue: {e}")

        # Detach and delete IAM policy
        if 'policy_arn' in self.resources:
            print("\n🔐 Deleting IAM resources...")
            try:
                self.iam.detach_role_policy(
                    RoleName=self.role_name,
                    PolicyArn=self.resources['policy_arn']
                )
                self.iam.delete_policy(PolicyArn=self.resources['policy_arn'])
                print("  ✓ Deleted IAM policy")
            except ClientError as e:
                print(f"  ⚠️  Error deleting policy: {e}")

        # Delete IAM role
        if 'role_arn' in self.resources:
            try:
                self.iam.delete_role(RoleName=self.role_name)
                print("  ✓ Deleted IAM role")
            except ClientError as e:
                print(f"  ⚠️  Error deleting role: {e}")

        print("\n" + "=" * 70)
        print("✅ CLEANUP COMPLETED")
        print("=" * 70)


def main():
    """Main deployment script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Deploy Full AWS Newsletter Stack (SNS + SQS + AgentCore Memory)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy full stack
  python deploy_full_stack.py --email your-email@example.com

  # Deploy to specific region
  python deploy_full_stack.py --region us-west-2 --email your-email@example.com

  # Custom stack name
  python deploy_full_stack.py --stack-name my-newsletter --email your-email@example.com

  # Cleanup all resources
  python deploy_full_stack.py --cleanup
        """
    )
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--stack-name', default='aws-newsletter',
                       help='Stack name prefix (default: aws-newsletter)')
    parser.add_argument('--email',
                       help='Email address to subscribe to newsletter')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up all resources')

    args = parser.parse_args()

    deployer = FullStackDeployer(region=args.region, stack_name=args.stack_name)

    try:
        if args.cleanup:
            # Try to load existing resources from .env if available
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
            if os.path.exists(env_path):
                print("📄 Loading resources from .env file...")
                from dotenv import dotenv_values
                env_vars = dotenv_values(env_path)
                deployer.resources = {
                    'topic_arn': env_vars.get('SNS_TOPIC_ARN', ''),
                    'queue_url': env_vars.get('SQS_QUEUE_URL', ''),
                    'queue_arn': env_vars.get('SQS_QUEUE_ARN', ''),
                    'dlq_url': env_vars.get('SQS_DLQ_URL', ''),
                    'dlq_arn': env_vars.get('SQS_DLQ_ARN', ''),
                    'role_arn': env_vars.get('SNS_ROLE_ARN', ''),
                    'policy_arn': env_vars.get('SNS_POLICY_ARN', ''),
                    'memory_id': env_vars.get('BEDROCK_AGENTCORE_MEMORY_ID', ''),
                    'memory_arn': env_vars.get('BEDROCK_AGENTCORE_MEMORY_ARN', '')
                }
            deployer.cleanup()
        else:
            deployer.deploy(test_email=args.email)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
