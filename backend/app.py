#!/usr/bin/env python3
"""
CDK App entry point for SNS Newsletter with SQS Tracking
"""

import aws_cdk as cdk
from newsletter_stack import NewsletterStack

app = cdk.App()

# Get configuration from context
stack_name = app.node.try_get_context("stack_name") or "newsletter-demo"
email = app.node.try_get_context("email")
environment = app.node.try_get_context("environment") or "dev"

# Create the stack
newsletter_stack = NewsletterStack(
    app,
    f"{stack_name}-{environment}",
    stack_name=stack_name,
    test_email=email,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1"
    )
)

# Add tags
cdk.Tags.of(newsletter_stack).add("Project", "Newsletter Demo")
cdk.Tags.of(newsletter_stack).add("Environment", environment)

app.synth()