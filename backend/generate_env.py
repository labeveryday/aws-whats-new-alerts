#!/usr/bin/env python3
"""
Generate .env file from CloudFormation stack outputs

Usage:
  python generate_env.py
  python generate_env.py --stack-name custom-newsletter --region us-west-2
"""

import boto3
import argparse
import os
from datetime import datetime
from typing import Dict, Optional


def get_stack_outputs(stack_name: str, region: str) -> Dict[str, str]:
    """Retrieve CloudFormation stack outputs"""
    cfn = boto3.client('cloudformation', region_name=region)

    try:
        response = cfn.describe_stacks(StackName=stack_name)

        if not response['Stacks']:
            raise Exception(f"Stack {stack_name} not found")

        stack = response['Stacks'][0]
        outputs = {}

        for output in stack.get('Outputs', []):
            key = output['OutputKey']
            value = output['OutputValue']
            outputs[key] = value

        return outputs

    except Exception as e:
        print(f"❌ Error retrieving stack outputs: {e}")
        raise


def generate_env_file(outputs: Dict[str, str], region: str, email: Optional[str] = None, output_path: str = ".env"):
    """Generate .env file from stack outputs"""

    # Get account ID
    sts = boto3.client('sts', region_name=region)
    account_id = sts.get_caller_identity()['Account']

    env_content = f"""# AWS Newsletter Configuration
# Auto-generated from CloudFormation stack outputs
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# AWS Configuration
AWS_REGION={region}
AWS_ACCOUNT_ID={account_id}

# Email Configuration
NEWSLETTER_EMAIL={email or ''}

# SNS Configuration
SNS_TOPIC_ARN={outputs.get('NewsletterTopicArn', '')}

# AgentCore Memory Configuration
BEDROCK_AGENTCORE_MEMORY_ID={outputs.get('MemoryId', '')}
BEDROCK_AGENTCORE_MEMORY_ARN={outputs.get('MemoryArn', '')}

# AgentCore Runtime Configuration
AGENTCORE_RUNTIME_ROLE_ARN={outputs.get('AgentCoreRuntimeRoleArn', '')}

# Agent Configuration (set after deployment)
# AGENTCORE_ARN=arn:aws:bedrock-agentcore:region:account:agent-runtime/runtime-id

# Agent Identity Configuration (for consistent memory)
AGENT_ACTOR_ID=aws-newsletter-bot
AGENT_SESSION_ID=aws-newsletter-main-session
"""

    # Add EventBridge Scheduler info if present
    if 'EventBridgeScheduleName' in outputs:
        env_content += f"""
# EventBridge Scheduler Configuration
EVENTBRIDGE_SCHEDULE_NAME={outputs.get('EventBridgeScheduleName', '')}
EVENTBRIDGE_ROLE_ARN={outputs.get('EventBridgeRoleArn', '')}
"""

    # Write to root directory (parent of backend) by default, or specified path
    if output_path == ".env":
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file_path = os.path.join(root_dir, output_path)
    else:
        env_file_path = output_path

    with open(env_file_path, 'w') as f:
        f.write(env_content)

    print(f"✅ Generated .env file: {env_file_path}")
    print(f"\n📋 Configuration Summary:")
    print(f"   SNS Topic ARN: {outputs.get('NewsletterTopicArn', 'N/A')}")
    print(f"   Memory ID: {outputs.get('MemoryId', 'N/A')}")
    print(f"   AgentCore Runtime Role: {outputs.get('AgentCoreRuntimeRoleArn', 'N/A')}")

    if 'EventBridgeScheduleName' in outputs:
        print(f"   EventBridge Schedule: {outputs.get('EventBridgeScheduleName', 'N/A')}")

    print(f"\n📌 Next Steps:")
    print(f"   1. Wait 2-5 minutes for AgentCore Memory to be fully provisioned")
    print(f"   2. Deploy your agent: cd ../agent && agentcore configure -e agent.py && agentcore launch")
    print(f"   3. Add AGENTCORE_ARN to .env file after agent deployment")
    if 'EventBridgeScheduleName' not in outputs:
        print(f"   4. (Optional) Enable scheduler: cdk deploy --context agentcore_arn=<arn> --context enable_scheduler=true")


def main():
    parser = argparse.ArgumentParser(
        description='Generate .env file from CloudFormation stack outputs',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--stack-name', default='aws-newsletter-prod',
                       help='CloudFormation stack name (default: aws-newsletter-prod)')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--email', 
                       help='Newsletter email address')
    parser.add_argument('--output', default='.env',
                       help='Output file path (default: .env in project root)')
    parser.add_argument('--agent-dir', action='store_true',
                       help='Place .env file in ../agent directory for agent access')

    args = parser.parse_args()

    # Handle agent directory option
    if args.agent_dir:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(os.path.dirname(backend_dir), 'agent', '.env')

    try:
        print(f"🔍 Retrieving stack outputs from: {args.stack_name}")
        outputs = get_stack_outputs(args.stack_name, args.region)

        print(f"📝 Generating .env file...")
        generate_env_file(outputs, args.region, args.email, args.output)

        return 0

    except Exception as e:
        print(f"\n❌ Failed to generate .env file: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
