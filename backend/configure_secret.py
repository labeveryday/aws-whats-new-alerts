#!/usr/bin/env python3
"""
Configure Agent Secrets in AWS Secrets Manager
Updates the agent configuration secret with CloudFormation stack outputs.
"""

import boto3
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional

def get_stack_outputs(stack_name: str, region: str) -> Dict[str, str]:
    """Retrieve CloudFormation stack outputs"""
    cfn = boto3.client('cloudformation', region_name=region)
    response = cfn.describe_stacks(StackName=stack_name)
    
    if not response['Stacks']:
        raise Exception(f"Stack {stack_name} not found")

    stack = response['Stacks'][0]
    outputs = {}
    for output in stack.get('Outputs', []):
        outputs[output['OutputKey']] = output['OutputValue']
    
    return outputs


def update_secret(secret_name: str, config: Dict[str, str], region: str):
    """Update AWS Secrets Manager secret"""
    client = boto3.client('secretsmanager', region_name=region)
    
    print(f"Updating secret {secret_name}...")
    client.put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(config, indent=2)
    )
    print("✅ Secret updated successfully")


def write_minimal_env_file(config: Dict[str, str], secret_name: str, outputs: Dict[str, str], region: str, output_path: str = "../agent/agent_config.env"):
    """Write minimal .env file for local CLI deployment tools"""

    # Build JWT authorizer config for AgentCore
    user_pool_id = outputs.get('UserPoolId', '')
    user_pool_client_id = outputs.get('UserPoolClientId', '')
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration" if user_pool_id else ""

    # Create authorizer config JSON (single line for CLI)
    authorizer_config = json.dumps({
        "customJWTAuthorizer": {
            "discoveryUrl": discovery_url,
            "allowedClients": [user_pool_client_id]
        }
    }) if user_pool_id and user_pool_client_id else ""

    env_content = f"""# Deployment Configuration
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# This file is used by the local agentcore CLI for deployment.
# Runtime configuration is loaded from Secrets Manager.

AGENTCORE_RUNTIME_ROLE_ARN={config.get('AGENTCORE_RUNTIME_ROLE_ARN', '')}
AWS_REGION={config.get('AWS_REGION', 'us-west-2')}
AGENT_NAME={config.get('AGENT_NAME', 'aws_newsletter_bot')}
SECRET_NAME={secret_name}

# JWT Authorization Config (for per-user memory isolation)
# This enables AgentCore to validate Cognito JWTs and pass user identity to the agent
COGNITO_USER_POOL_ID={user_pool_id}
COGNITO_CLIENT_ID={user_pool_client_id}
COGNITO_DISCOVERY_URL={discovery_url}
AUTHORIZER_CONFIG='{authorizer_config}'
"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Generated minimal deployment config: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Configure Agent Secrets')
    parser.add_argument('--stack-name', default='aws-newsletter-prod')
    parser.add_argument('--region', default='us-west-2')
    parser.add_argument('--email', help='Newsletter email')
    parser.add_argument('--agent-dir', action='store_true', help='Deprecated flag (kept for compatibility)')
    
    args = parser.parse_args()

    try:
        print(f"🔍 Retrieving stack outputs from: {args.stack_name}")
        outputs = get_stack_outputs(args.stack_name, args.region)
        
        secret_name = outputs.get('AgentConfigSecretName')
        if not secret_name:
            raise Exception("AgentConfigSecretName not found in stack outputs. Ensure stack is deployed correctly.")

        # Build configuration dictionary
        config = {
            "AWS_REGION": args.region,
            "AWS_ACCOUNT_ID": boto3.client('sts').get_caller_identity()['Account'],
            "NEWSLETTER_EMAIL": args.email or outputs.get('TestEmailSubscription', ''),
            "SNS_TOPIC_ARN": outputs.get('NewsletterTopicArn', ''),
            "BEDROCK_AGENTCORE_MEMORY_ID": outputs.get('MemoryId', ''),
            "BEDROCK_AGENTCORE_MEMORY_ARN": outputs.get('MemoryArn', ''),
            "AGENTCORE_RUNTIME_ROLE_ARN": outputs.get('AgentCoreRuntimeRoleArn', ''),
            "SCHEDULER_ROLE_ARN": outputs.get('EventBridgeRoleArn', ''),
            "SCHEDULER_DLQ_ARN": outputs.get('SchedulerDLQArn', ''),
            "AGENT_ACTOR_ID": "aws_newsletter_bot",
            "AGENT_SESSION_ID": "aws-newsletter-main-session",
            "AGENT_NAME": "aws_newsletter_bot",
            "last_updated": datetime.now().isoformat()
        }

        # 1. Update Secret (for Runtime)
        update_secret(secret_name, config, args.region)
        
        # 2. Write Minimal Config (for CLI Deployment)
        # Determine path relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(os.path.dirname(script_dir), 'agent', 'agent_config.env')
        write_minimal_env_file(config, secret_name, outputs, args.region, env_path)
        
        print(f"\n📋 Configuration Updated:")
        print(f"   - Runtime Secret: {secret_name}")
        print(f"   - Local Config: {env_path}")
        return 0

    except Exception as e:
        print(f"\n❌ Failed to configure secrets: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

