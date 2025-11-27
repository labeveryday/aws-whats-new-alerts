#!/usr/bin/env python3
"""
Deploy Frontend
Generates config.js from stack outputs and uploads frontend assets to S3.
"""
import boto3
import argparse
import os
import json
import mimetypes
import time

def get_stack_outputs(stack_name: str, region: str):
    cfn = boto3.client('cloudformation', region_name=region)
    response = cfn.describe_stacks(StackName=stack_name)
    outputs = {}
    for output in response['Stacks'][0].get('Outputs', []):
        outputs[output['OutputKey']] = output['OutputValue']
    return outputs

def find_agent_runtime_arn(agent_name, region):
    """Find agent ARN by name using Control Plane"""
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        paginator = client.get_paginator('list_agent_runtimes')
        for page in paginator.paginate():
            for agent in page.get('agentRuntimes', []):
                if agent_name in agent.get('agentRuntimeName', ''):
                    print(f"✅ Found agent runtime: {agent['agentRuntimeArn']}")
                    return agent['agentRuntimeArn']
    except Exception as e:
        print(f"⚠️ Could not auto-discover agent ARN: {e}")
    return None

def generate_config(outputs, region, agent_arn=None):
    # Extract short agent ID from ARN if available
    # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/NAME-AGENT_ID
    # We need just the alphanumeric AGENT_ID (last 10 chars after final hyphen)
    agent_id = "TSTALIASID" # Default fallback
    if agent_arn:
        try:
            runtime_name = agent_arn.split('/')[-1]  # e.g., "aws_newsletter_bot-Yu2RiP7GOJ"
            agent_id = runtime_name.split('-')[-1]   # e.g., "Yu2RiP7GOJ"
        except IndexError:
            print(f"⚠️ Could not extract agent ID from ARN: {agent_arn}")

    config = {
        "region": region,
        "userPoolId": outputs.get('UserPoolId'),
        "userPoolClientId": outputs.get('UserPoolClientId'),
        "identityPoolId": outputs.get('IdentityPoolId'),
        "agentRuntimeArn": agent_arn,
        "agentId": agent_id 
    }
    
    content = f"window.awsConfig = {json.dumps(config, indent=4)};"
    
    # Use absolute path relative to script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(script_dir, '../frontend')
    config_path = os.path.join(frontend_dir, 'config.js')

    with open(config_path, 'w') as f:
        f.write(content)
    print("✅ Generated frontend/config.js")

def upload_to_s3(bucket_name, region):
    s3 = boto3.client('s3', region_name=region)

    # Use absolute path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(script_dir, '../frontend')

    # Walk through all files including subdirectories (e.g., vendor/)
    for root, dirs, files in os.walk(frontend_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in files:
            if filename.startswith('.'):
                continue

            filepath = os.path.join(root, filename)
            # Create S3 key with relative path from frontend_dir
            relative_path = os.path.relpath(filepath, frontend_dir)
            s3_key = relative_path.replace(os.sep, '/')  # Ensure forward slashes for S3

            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'

            print(f"Uploading {s3_key} to s3://{bucket_name}/...")
            with open(filepath, 'rb') as f:
                s3.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=f,
                    ContentType=content_type
                )
    print("✅ Upload complete")

def invalidate_cloudfront(distribution_id, region):
    cf = boto3.client('cloudfront', region_name=region)
    print(f"Creating invalidation for {distribution_id}...")
    
    invalidation = cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(time.time())
        }
    )
    
    invalidation_id = invalidation['Invalidation']['Id']
    print(f"✅ Invalidation {invalidation_id} created. It may take a few minutes to propagate.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stack-name', default='aws-newsletter-prod')
    parser.add_argument('--region', default='us-west-2')
    args = parser.parse_args()
    
    print(f"Retrieving outputs from {args.stack_name}...")
    try:
        outputs = get_stack_outputs(args.stack_name, args.region)
        
        bucket_name = outputs.get('FrontendBucketName')
        if not bucket_name:
            print("❌ Error: FrontendBucketName not found in stack outputs.")
            return
            
        # Attempt to find Agent Runtime ARN
        agent_name = "aws_newsletter_bot" # Default name from agent.py
        agent_arn = find_agent_runtime_arn(agent_name, args.region)
        
        if not agent_arn:
            print(f"⚠️ Agent Runtime ARN not found for name '{agent_name}'. You may need to update config.js manually.")

        generate_config(outputs, args.region, agent_arn)
        upload_to_s3(bucket_name, args.region)
        
        distribution_id = outputs.get('CloudFrontDistributionId')
        if distribution_id:
            invalidate_cloudfront(distribution_id, args.region)
        else:
            print("⚠️ CloudFrontDistributionId not found in outputs. Skipping invalidation.")
        
        url = outputs.get('CloudFrontUrl')
        print(f"\n🚀 Frontend Deployed!")
        print(f"URL: {url}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()

