#!/usr/bin/env python3
"""
AWS Newsletter - EventBridge Scheduler Deployment

This script creates:
1. EventBridge Scheduler rule to trigger AgentCore Runtime daily
2. IAM role for EventBridge to invoke AgentCore Runtime
3. IAM role for AgentCore Runtime to publish to SNS topic
4. Automatic .env file updates with new resource ARNs
"""

import boto3
import json
import os
import time
from typing import Dict, Optional
from botocore.exceptions import ClientError
from datetime import datetime


class EventBridgeDeployer:
    def __init__(self, region: str = 'us-east-1', stack_name: str = 'aws-newsletter'):
        self.region = region
        self.stack_name = stack_name

        # Initialize AWS clients
        self.scheduler = boto3.client('scheduler', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)

        # Get account ID
        self.account_id = self.sts.get_caller_identity()['Account']

        # Resource names
        self.schedule_name = f'{stack_name}-daily-newsletter'
        self.eventbridge_role_name = f'{stack_name}-eventbridge-role'
        self.agentcore_role_name = f'{stack_name}-agentcore-runtime-role'

        # Store created resources
        self.resources = {}

        # Load .env file
        self.load_env()

    def load_env(self):
        """Load configuration from .env file"""
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

        if not os.path.exists(env_path):
            raise FileNotFoundError(
                f".env file not found at {env_path}\n"
                "Please run deploy_full_stack.py first to create infrastructure."
            )

        # Simple .env parser
        env_vars = {}
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value

        # Required variables
        self.agentcore_arn = env_vars.get('AGENTCORE_ARN')
        self.sns_topic_arn = env_vars.get('SNS_TOPIC_ARN')

        if not self.agentcore_arn:
            raise ValueError(
                "AGENTCORE_ARN not found in .env file.\n"
                "Please deploy your agent first:\n"
                "  cd ../deployment\n"
                "  agentcore configure -e agent.py\n"
                "  agentcore launch\n"
                "Then add AGENTCORE_ARN=... to .env"
            )

        if not self.sns_topic_arn:
            raise ValueError(
                "SNS_TOPIC_ARN not found in .env file.\n"
                "Please run deploy_full_stack.py first."
            )

        print(f"✓ Loaded configuration from .env")
        print(f"  AgentCore ARN: {self.agentcore_arn}")
        print(f"  SNS Topic ARN: {self.sns_topic_arn}")

    def create_eventbridge_role(self) -> str:
        """Create IAM role for EventBridge to invoke AgentCore Runtime"""
        print("\n🔐 Creating IAM role for EventBridge Scheduler...")

        # Trust policy for EventBridge Scheduler
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "scheduler.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        # Policy to allow invoking AgentCore Runtime
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:InvokeAgentRuntime"
                    ],
                    "Resource": self.agentcore_arn
                }
            ]
        }

        try:
            # Create role
            role_response = self.iam.create_role(
                RoleName=self.eventbridge_role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for EventBridge Scheduler to invoke {self.stack_name} AgentCore Runtime"
            )
            role_arn = role_response['Role']['Arn']

            # Create inline policy
            self.iam.put_role_policy(
                RoleName=self.eventbridge_role_name,
                PolicyName=f'{self.eventbridge_role_name}-policy',
                PolicyDocument=json.dumps(policy_document)
            )

            print(f"  ✓ Created EventBridge role: {role_arn}")

            self.resources['eventbridge_role_arn'] = role_arn

            # Wait for role to be available
            print("  ⏳ Waiting for role propagation (10s)...")
            time.sleep(10)

            return role_arn

        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"  ⚠️  Role already exists, retrieving...")
                role_arn = f"arn:aws:iam::{self.account_id}:role/{self.eventbridge_role_name}"

                # Update policy in case it changed
                try:
                    self.iam.put_role_policy(
                        RoleName=self.eventbridge_role_name,
                        PolicyName=f'{self.eventbridge_role_name}-policy',
                        PolicyDocument=json.dumps(policy_document)
                    )
                    print(f"  ✓ Updated policy for existing role")
                except Exception as update_error:
                    print(f"  ⚠️  Could not update policy: {update_error}")

                self.resources['eventbridge_role_arn'] = role_arn
                return role_arn
            else:
                print(f"  ❌ Error creating EventBridge role: {e}")
                raise

    def create_agentcore_runtime_role(self) -> str:
        """Create IAM role for AgentCore Runtime to publish to SNS"""
        print("\n🔐 Creating IAM role for AgentCore Runtime...")

        # Trust policy for Bedrock AgentCore
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock-agentcore.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        # Policy to allow publishing to SNS topic
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "sns:Publish"
                    ],
                    "Resource": self.sns_topic_arn
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "arn:aws:logs:*:*:*"
                }
            ]
        }

        try:
            # Create role
            role_response = self.iam.create_role(
                RoleName=self.agentcore_role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for {self.stack_name} AgentCore Runtime to publish to SNS"
            )
            role_arn = role_response['Role']['Arn']

            # Create inline policy
            self.iam.put_role_policy(
                RoleName=self.agentcore_role_name,
                PolicyName=f'{self.agentcore_role_name}-policy',
                PolicyDocument=json.dumps(policy_document)
            )

            print(f"  ✓ Created AgentCore Runtime role: {role_arn}")
            print(f"  💡 Note: You may need to update your AgentCore Runtime configuration")
            print(f"     to use this role ARN for SNS publishing permissions")

            self.resources['agentcore_runtime_role_arn'] = role_arn

            return role_arn

        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"  ⚠️  Role already exists, retrieving...")
                role_arn = f"arn:aws:iam::{self.account_id}:role/{self.agentcore_role_name}"

                # Update policy in case it changed
                try:
                    self.iam.put_role_policy(
                        RoleName=self.agentcore_role_name,
                        PolicyName=f'{self.agentcore_role_name}-policy',
                        PolicyDocument=json.dumps(policy_document)
                    )
                    print(f"  ✓ Updated policy for existing role")
                except Exception as update_error:
                    print(f"  ⚠️  Could not update policy: {update_error}")

                self.resources['agentcore_runtime_role_arn'] = role_arn
                return role_arn
            else:
                print(f"  ❌ Error creating AgentCore Runtime role: {e}")
                raise

    def create_schedule(self, schedule_expression: str = "cron(0 8 * * ? *)") -> str:
        """Create EventBridge Scheduler rule"""
        print(f"\n📅 Creating EventBridge Scheduler...")
        print(f"  Schedule: {schedule_expression}")

        # Prepare the input payload for AgentCore Runtime
        input_payload = {
            "agentRuntimeArn": self.agentcore_arn,
            "payload": json.dumps({
                "prompt": "Generate daily AWS AI/ML newsletter"
            })
        }

        try:
            # Create schedule
            response = self.scheduler.create_schedule(
                Name=self.schedule_name,
                Description=f"Daily trigger for {self.stack_name} newsletter agent",
                ScheduleExpression=schedule_expression,
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                State='ENABLED',
                Target={
                    'Arn': 'arn:aws:scheduler:::aws-sdk:bedrock-agentcore:invokeAgentRuntime',
                    'RoleArn': self.resources['eventbridge_role_arn'],
                    'Input': json.dumps(input_payload),
                    'RetryPolicy': {
                        'MaximumRetryAttempts': 3,
                        'MaximumEventAge': 3600
                    }
                }
            )

            schedule_arn = response['ScheduleArn']
            print(f"  ✓ Created schedule: {schedule_arn}")
            print(f"  ✓ Schedule is ENABLED and will trigger based on expression")

            self.resources['schedule_arn'] = schedule_arn
            self.resources['schedule_name'] = self.schedule_name
            self.resources['schedule_expression'] = schedule_expression

            return schedule_arn

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConflictException':
                print(f"  ⚠️  Schedule already exists, updating...")
                try:
                    response = self.scheduler.update_schedule(
                        Name=self.schedule_name,
                        ScheduleExpression=schedule_expression,
                        FlexibleTimeWindow={'Mode': 'OFF'},
                        State='ENABLED',
                        Target={
                            'Arn': 'arn:aws:scheduler:::aws-sdk:bedrock-agentcore:invokeAgentRuntime',
                            'RoleArn': self.resources['eventbridge_role_arn'],
                            'Input': json.dumps(input_payload),
                            'RetryPolicy': {
                                'MaximumRetryAttempts': 3,
                                'MaximumEventAge': 3600
                            }
                        }
                    )
                    schedule_arn = response['ScheduleArn']
                    print(f"  ✓ Updated schedule: {schedule_arn}")

                    self.resources['schedule_arn'] = schedule_arn
                    self.resources['schedule_name'] = self.schedule_name
                    self.resources['schedule_expression'] = schedule_expression

                    return schedule_arn
                except Exception as update_error:
                    print(f"  ❌ Error updating schedule: {update_error}")
                    raise
            else:
                print(f"  ❌ Error creating schedule: {e}")
                raise

    def update_env_file(self):
        """Update .env file with new resource ARNs"""
        print("\n📝 Updating .env file...")

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

        # Read existing .env
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Remove old EventBridge entries
        lines = [line for line in lines if not any(
            key in line for key in [
                'EVENTBRIDGE_SCHEDULE_NAME',
                'EVENTBRIDGE_SCHEDULE_ARN',
                'EVENTBRIDGE_ROLE_ARN',
                'AGENTCORE_RUNTIME_ROLE_ARN',
                'SCHEDULE_EXPRESSION'
            ]
        )]

        # Add new entries
        new_entries = [
            "\n# EventBridge Scheduler Configuration\n",
            f"# Auto-updated by deploy_eventbridge.py on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"EVENTBRIDGE_SCHEDULE_NAME={self.resources.get('schedule_name', '')}\n",
            f"EVENTBRIDGE_SCHEDULE_ARN={self.resources.get('schedule_arn', '')}\n",
            f"EVENTBRIDGE_ROLE_ARN={self.resources.get('eventbridge_role_arn', '')}\n",
            f"AGENTCORE_RUNTIME_ROLE_ARN={self.resources.get('agentcore_runtime_role_arn', '')}\n",
            f"SCHEDULE_EXPRESSION={self.resources.get('schedule_expression', '')}\n"
        ]

        # Write back
        with open(env_path, 'w') as f:
            f.writelines(lines)
            f.writelines(new_entries)

        print(f"  ✓ Updated {env_path}")
        print(f"  📋 Added:")
        print(f"     EVENTBRIDGE_SCHEDULE_NAME={self.resources.get('schedule_name')}")
        print(f"     EVENTBRIDGE_SCHEDULE_ARN={self.resources.get('schedule_arn')}")
        print(f"     EVENTBRIDGE_ROLE_ARN={self.resources.get('eventbridge_role_arn')}")
        print(f"     AGENTCORE_RUNTIME_ROLE_ARN={self.resources.get('agentcore_runtime_role_arn')}")

    def deploy(self, schedule_expression: str = "cron(0 8 * * ? *)"):
        """Deploy EventBridge Scheduler automation"""
        print("=" * 70)
        print(f"🚀 Deploying EventBridge Scheduler: {self.stack_name}")
        print(f"📍 Region: {self.region}")
        print(f"🔑 Account: {self.account_id}")
        print("=" * 70)

        try:
            # Step 1: Create EventBridge role
            eventbridge_role_arn = self.create_eventbridge_role()

            # Step 2: Create AgentCore Runtime role
            agentcore_role_arn = self.create_agentcore_runtime_role()

            # Step 3: Create EventBridge schedule
            schedule_arn = self.create_schedule(schedule_expression)

            # Step 4: Update .env file
            self.update_env_file()

            print("\n" + "=" * 70)
            print("✅ EVENTBRIDGE DEPLOYMENT COMPLETED SUCCESSFULLY!")
            print("=" * 70)

            print("\n📌 Next Steps:")
            print("   1. Your agent will run automatically based on the schedule")
            print(f"   2. Schedule: {schedule_expression}")
            print(f"   3. Check CloudWatch Logs: /aws/bedrock-agentcore/runtimes/")
            print("   4. Test manually: python deploy_eventbridge.py --trigger-now")
            print("   5. Monitor: aws scheduler get-schedule --name", self.schedule_name)

            return self.resources

        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            print("   Partial resources may have been created.")
            print("   Run with --cleanup to remove resources.")
            raise

    def trigger_now(self):
        """Manually trigger the schedule for testing"""
        print("\n🎯 Manually triggering agent execution...")

        # Use boto3 to invoke the agent directly
        bedrock_agentcore = boto3.client('bedrock-agentcore', region_name=self.region)

        try:
            response = bedrock_agentcore.invoke_agent_runtime(
                agentRuntimeArn=self.agentcore_arn,
                runtimeSessionId=f"manual-trigger-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                payload=json.dumps({"prompt": "Generate daily AWS AI/ML newsletter"})
            )

            print("  ✓ Agent invocation started")
            print("  📊 Check CloudWatch Logs for execution details")
            print(f"  📍 Log group: /aws/bedrock-agentcore/runtimes/")

        except Exception as e:
            print(f"  ❌ Error triggering agent: {e}")
            raise

    def get_status(self):
        """Get schedule status"""
        print("\n📊 Checking EventBridge Scheduler status...")

        try:
            response = self.scheduler.get_schedule(Name=self.schedule_name)

            print(f"  Schedule Name: {response['Name']}")
            print(f"  State: {response['State']}")
            print(f"  Schedule Expression: {response['ScheduleExpression']}")
            print(f"  Schedule ARN: {response['Arn']}")
            print(f"  Target ARN: {response['Target']['Arn']}")

            return response

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"  ❌ Schedule '{self.schedule_name}' not found")
                print(f"     Run: python deploy_eventbridge.py to create it")
            else:
                print(f"  ❌ Error getting schedule status: {e}")
            return None

    def disable_schedule(self):
        """Disable the schedule"""
        print("\n⏸️  Disabling schedule...")

        try:
            self.scheduler.update_schedule(
                Name=self.schedule_name,
                State='DISABLED',
                FlexibleTimeWindow={'Mode': 'OFF'}
            )
            print(f"  ✓ Schedule '{self.schedule_name}' disabled")

        except Exception as e:
            print(f"  ❌ Error disabling schedule: {e}")
            raise

    def enable_schedule(self):
        """Enable the schedule"""
        print("\n▶️  Enabling schedule...")

        try:
            self.scheduler.update_schedule(
                Name=self.schedule_name,
                State='ENABLED',
                FlexibleTimeWindow={'Mode': 'OFF'}
            )
            print(f"  ✓ Schedule '{self.schedule_name}' enabled")

        except Exception as e:
            print(f"  ❌ Error enabling schedule: {e}")
            raise

    def cleanup(self):
        """Clean up all EventBridge resources"""
        print("\n" + "=" * 70)
        print("🧹 CLEANING UP EVENTBRIDGE RESOURCES")
        print("=" * 70)

        # Delete schedule
        print("\n📅 Deleting EventBridge schedule...")
        try:
            self.scheduler.delete_schedule(Name=self.schedule_name)
            print(f"  ✓ Deleted schedule: {self.schedule_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"  ⚠️  Schedule not found (already deleted)")
            else:
                print(f"  ⚠️  Error deleting schedule: {e}")

        # Delete EventBridge IAM role
        print("\n🔐 Deleting EventBridge IAM role...")
        try:
            # Delete inline policy first
            self.iam.delete_role_policy(
                RoleName=self.eventbridge_role_name,
                PolicyName=f'{self.eventbridge_role_name}-policy'
            )
            # Delete role
            self.iam.delete_role(RoleName=self.eventbridge_role_name)
            print(f"  ✓ Deleted EventBridge role: {self.eventbridge_role_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                print(f"  ⚠️  Role not found (already deleted)")
            else:
                print(f"  ⚠️  Error deleting EventBridge role: {e}")

        # Delete AgentCore Runtime IAM role
        print("\n🔐 Deleting AgentCore Runtime IAM role...")
        try:
            # Delete inline policy first
            self.iam.delete_role_policy(
                RoleName=self.agentcore_role_name,
                PolicyName=f'{self.agentcore_role_name}-policy'
            )
            # Delete role
            self.iam.delete_role(RoleName=self.agentcore_role_name)
            print(f"  ✓ Deleted AgentCore Runtime role: {self.agentcore_role_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                print(f"  ⚠️  Role not found (already deleted)")
            else:
                print(f"  ⚠️  Error deleting AgentCore Runtime role: {e}")

        print("\n" + "=" * 70)
        print("✅ CLEANUP COMPLETED")
        print("=" * 70)


def main():
    """Main deployment script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Deploy EventBridge Scheduler for AWS Newsletter Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy with default schedule (8 AM UTC daily)
  python deploy_eventbridge.py

  # Deploy with custom schedule
  python deploy_eventbridge.py --schedule "cron(0 12 * * ? *)"  # Noon UTC
  python deploy_eventbridge.py --schedule "rate(2 hours)"        # Every 2 hours

  # Test manual trigger
  python deploy_eventbridge.py --trigger-now

  # Check status
  python deploy_eventbridge.py --status

  # Disable/enable
  python deploy_eventbridge.py --disable
  python deploy_eventbridge.py --enable

  # Cleanup
  python deploy_eventbridge.py --cleanup
        """
    )
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--stack-name', default='aws-newsletter',
                       help='Stack name prefix (default: aws-newsletter)')
    parser.add_argument('--schedule', default='cron(0 8 * * ? *)',
                       help='Schedule expression (default: cron(0 8 * * ? *))')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up all EventBridge resources')
    parser.add_argument('--trigger-now', action='store_true',
                       help='Manually trigger agent execution for testing')
    parser.add_argument('--status', action='store_true',
                       help='Check schedule status')
    parser.add_argument('--disable', action='store_true',
                       help='Disable the schedule')
    parser.add_argument('--enable', action='store_true',
                       help='Enable the schedule')

    args = parser.parse_args()

    deployer = EventBridgeDeployer(region=args.region, stack_name=args.stack_name)

    try:
        if args.cleanup:
            deployer.cleanup()
        elif args.trigger_now:
            deployer.trigger_now()
        elif args.status:
            deployer.get_status()
        elif args.disable:
            deployer.disable_schedule()
        elif args.enable:
            deployer.enable_schedule()
        else:
            deployer.deploy(schedule_expression=args.schedule)

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
