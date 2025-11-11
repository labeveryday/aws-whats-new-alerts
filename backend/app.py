#!/usr/bin/env python3
"""
CDK App entry point for AWS Newsletter System

Usage:
  # Deploy infrastructure only
  cdk deploy --context email=your-email@example.com

  # Deploy with EventBridge scheduler (requires agentcore_arn)
  cdk deploy --context email=your-email@example.com --context agentcore_arn=arn:aws:... --context enable_scheduler=true

  # Generate .env file after deployment
  python generate_env.py
"""

import aws_cdk as cdk
from newsletter_stack import NewsletterStack

app = cdk.App()

# Get configuration from context
stack_name = app.node.try_get_context("stack_name") or "aws-newsletter"
email = app.node.try_get_context("email")
environment = app.node.try_get_context("environment") or "prod"
agentcore_arn = app.node.try_get_context("agentcore_arn")
enable_scheduler = app.node.try_get_context("enable_scheduler") == "true"

# Create the stack (Gets region from environment)
newsletter_stack = NewsletterStack(
    app,
    f"{stack_name}-{environment}",
    stack_name=stack_name,
    test_email=email,
    agentcore_arn=agentcore_arn,
    enable_scheduler=enable_scheduler,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-west-2"
    )
)

# Add tags
cdk.Tags.of(newsletter_stack).add("Project", "AWS Newsletter System")
cdk.Tags.of(newsletter_stack).add("Environment", environment)
cdk.Tags.of(newsletter_stack).add("ManagedBy", "CDK")

app.synth()