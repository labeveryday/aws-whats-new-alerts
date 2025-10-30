#!/usr/bin/env python3
"""
Example usage of the Newsletter infrastructure

This script demonstrates how to interact with the deployed infrastructure
"""

import os
from deploy_utils import NewsletterClient, create_sample_newsletter, validate_email


def main():
    """Demonstrate newsletter functionality"""
    
    # Configuration (replace with your actual values)
    REGION = os.getenv('AWS_REGION', 'us-east-1')
    TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:newsletter-demo-newsletter-topic')
    QUEUE_URL = os.getenv('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/newsletter-demo-tracking-queue')
    
    print(f"🚀 Newsletter Demo - Region: {REGION}")
    print("-" * 50)
    
    # Initialize client
    client = NewsletterClient(region=REGION)
    
    # Example 1: List current subscriptions
    print("📋 Current Subscriptions:")
    try:
        subscriptions = client.list_subscriptions(TOPIC_ARN)
        if not subscriptions:
            print("  No subscriptions found")
    except Exception as e:
        print(f"  ❌ Could not list subscriptions: {e}")
    
    print()
    
    # Example 2: Send a sample newsletter
    print("📧 Sending Sample Newsletter:")
    try:
        newsletter = create_sample_newsletter()
        message_id = client.send_newsletter(
            topic_arn=TOPIC_ARN,
            subject=newsletter['subject'],
            message=newsletter['message']
        )
        print(f"  Message ID: {message_id}")
    except Exception as e:
        print(f"  ❌ Could not send newsletter: {e}")
    
    print()
    
    # Example 3: Check delivery status
    print("📊 Checking Delivery Status:")
    try:
        status_reports = client.check_delivery_status(QUEUE_URL, limit=5)
        if not status_reports:
            print("  No delivery reports found (messages may take a few moments)")
        else:
            for report in status_reports:
                print(f"  📬 {report['message_id']}: {report['status']}")
    except Exception as e:
        print(f"  ❌ Could not check delivery status: {e}")
    
    print()
    
    # Example 4: Get queue statistics
    print("📈 Queue Statistics:")
    try:
        stats = client.get_queue_stats(QUEUE_URL)
        if stats:
            print(f"  Available Messages: {stats['available_messages']}")
            print(f"  In-Flight Messages: {stats['in_flight_messages']}")
    except Exception as e:
        print(f"  ❌ Could not get queue stats: {e}")
    
    print()
    
    # Example 5: Interactive email subscription
    print("➕ Interactive Email Subscription:")
    email = input("Enter email to subscribe (or press Enter to skip): ").strip()
    
    if email:
        if validate_email(email):
            try:
                subscription_arn = client.subscribe_email(TOPIC_ARN, email)
                print(f"  ✅ Subscribed! Check {email} for confirmation.")
                print(f"  Subscription ARN: {subscription_arn}")
            except Exception as e:
                print(f"  ❌ Could not subscribe email: {e}")
        else:
            print(f"  ❌ Invalid email format: {email}")
    
    print()
    print("✨ Demo completed!")
    print("\nNext steps:")
    print("1. Check your email for subscription confirmations")
    print("2. Monitor CloudWatch for metrics")
    print("3. Customize the newsletter content")
    print("4. Scale to more subscribers")


def send_custom_newsletter():
    """Send a custom newsletter with user input"""
    REGION = os.getenv('AWS_REGION', 'us-east-1')
    TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')
    
    if not TOPIC_ARN:
        print("❌ SNS_TOPIC_ARN environment variable not set")
        return
    
    client = NewsletterClient(region=REGION)
    
    print("📝 Custom Newsletter Composer")
    print("-" * 30)
    
    subject = input("Newsletter Subject: ").strip()
    if not subject:
        subject = "AWS Newsletter Update"
    
    print("Newsletter Message (press Enter twice to finish):")
    message_lines = []
    while True:
        line = input()
        if line == "" and len(message_lines) > 0 and message_lines[-1] == "":
            break
        message_lines.append(line)
    
    message = "\\n".join(message_lines).strip()
    if not message:
        message = "Hello! This is a test newsletter from AWS SNS."
    
    print(f"\\n📧 Sending newsletter...")
    print(f"Subject: {subject}")
    print(f"Message length: {len(message)} characters")
    
    try:
        message_id = client.send_newsletter(
            topic_arn=TOPIC_ARN,
            subject=subject,
            message=message
        )
        print(f"✅ Newsletter sent! Message ID: {message_id}")
    except Exception as e:
        print(f"❌ Failed to send newsletter: {e}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Newsletter Demo Examples')
    parser.add_argument('--custom', action='store_true', help='Send custom newsletter')
    parser.add_argument('--topic-arn', help='SNS Topic ARN')
    parser.add_argument('--queue-url', help='SQS Queue URL')
    parser.add_argument('--region', default='us-east-1', help='AWS Region')
    
    args = parser.parse_args()
    
    # Set environment variables from arguments
    if args.topic_arn:
        os.environ['SNS_TOPIC_ARN'] = args.topic_arn
    if args.queue_url:
        os.environ['SQS_QUEUE_URL'] = args.queue_url
    if args.region:
        os.environ['AWS_REGION'] = args.region
    
    if args.custom:
        send_custom_newsletter()
    else:
        main()