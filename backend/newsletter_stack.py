"""
CDK Stack for SNS Newsletter with SQS Tracking

This stack creates:
1. SNS topic for email newsletters
2. SQS queue for tracking delivery status  
3. Dead letter queue for failed messages
4. IAM roles and policies
5. SNS delivery status notifications
"""

from typing import Optional
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_iam as iam,
    aws_sns_subscriptions as sns_subs,
    CfnOutput,
    Duration
)
from constructs import Construct


class NewsletterStack(Stack):
    """CDK Stack for Newsletter Infrastructure"""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        stack_name: str,
        test_email: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.stack_name = stack_name
        
        # Create SQS queues
        self.dlq = self._create_dead_letter_queue()
        self.tracking_queue = self._create_tracking_queue()
        
        # Create IAM role for SNS
        self.sns_role = self._create_sns_role()
        
        # Create SNS topic
        self.newsletter_topic = self._create_sns_topic()
        
        # Configure delivery status notifications
        self._configure_delivery_status()
        
        # Subscribe test email if provided
        if test_email:
            self._subscribe_test_email(test_email)
        
        # Create outputs
        self._create_outputs()
    
    def _create_dead_letter_queue(self) -> sqs.Queue:
        """Create dead letter queue for failed tracking messages"""
        dlq = sqs.Queue(
            self,
            "TrackingDLQ",
            queue_name=f"{self.stack_name}-tracking-dlq",
            retention_period=Duration.days(14),
            visibility_timeout=Duration.seconds(60)
        )
        
        # Add tags
        cdk.Tags.of(dlq).add("Component", "DeadLetterQueue")
        
        return dlq
    
    def _create_tracking_queue(self) -> sqs.Queue:
        """Create SQS queue for tracking delivery status"""
        queue = sqs.Queue(
            self,
            "TrackingQueue",
            queue_name=f"{self.stack_name}-tracking-queue",
            retention_period=Duration.days(14),
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq
            )
        )
        
        # Add tags
        cdk.Tags.of(queue).add("Component", "TrackingQueue")
        
        return queue
    
    def _create_sns_role(self) -> iam.Role:
        """Create IAM role for SNS to write delivery status to SQS"""
        role = iam.Role(
            self,
            "SNSDeliveryRole",
            role_name=f"{self.stack_name}-sns-delivery-role",
            assumed_by=iam.ServicePrincipal("sns.amazonaws.com"),
            description="Role for SNS to write delivery status to SQS"
        )
        
        # Add policy to write to tracking queue
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sqs:SendMessage"],
                resources=[self.tracking_queue.queue_arn]
            )
        )
        
        # Add CloudWatch logs permissions for delivery status
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        # Add tags
        cdk.Tags.of(role).add("Component", "SNSRole")
        
        return role
    
    def _create_sns_topic(self) -> sns.Topic:
        """Create SNS topic for newsletters"""
        topic = sns.Topic(
            self,
            "NewsletterTopic",
            topic_name=f"{self.stack_name}-newsletter-topic",
            display_name=f"{self.stack_name} Newsletter",
            description="SNS topic for email newsletters with delivery tracking"
        )
        
        # Allow SQS queue to receive messages from this topic
        self.tracking_queue.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("sns.amazonaws.com")],
                actions=["sqs:SendMessage"],
                resources=[self.tracking_queue.queue_arn],
                conditions={
                    "ArnEquals": {
                        "aws:SourceArn": topic.topic_arn
                    }
                }
            )
        )
        
        # Add tags
        cdk.Tags.of(topic).add("Component", "NewsletterTopic")
        
        return topic
    
    def _configure_delivery_status(self):
        """Configure SNS delivery status notifications"""
        # Note: CDK doesn't directly support delivery status configuration
        # This would typically be done via CloudFormation custom resource
        # or post-deployment script
        
        # Create custom resource to configure delivery status
        delivery_config = cdk.CustomResource(
            self,
            "DeliveryStatusConfig",
            service_token=self._create_delivery_config_lambda().function_arn,
            properties={
                "TopicArn": self.newsletter_topic.topic_arn,
                "RoleArn": self.sns_role.role_arn,
                "QueueArn": self.tracking_queue.queue_arn
            }
        )
        
        # Ensure role is created before configuring delivery status
        delivery_config.node.add_dependency(self.sns_role)
        delivery_config.node.add_dependency(self.newsletter_topic)
    
    def _create_delivery_config_lambda(self):
        """Create Lambda function to configure SNS delivery status"""
        from aws_cdk import aws_lambda as lambda_
        
        # Lambda function to configure delivery status
        config_lambda = lambda_.Function(
            self,
            "DeliveryConfigLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    try:
        sns = boto3.client('sns')
        
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            topic_arn = event['ResourceProperties']['TopicArn']
            role_arn = event['ResourceProperties']['RoleArn']
            
            # Configure delivery status for email
            sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPSuccessFeedbackRoleArn',
                AttributeValue=role_arn
            )
            sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPFailureFeedbackRoleArn',
                AttributeValue=role_arn
            )
            sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='HTTPSuccessFeedbackSampleRate',
                AttributeValue='100'
            )
            
            logger.info(f"Configured delivery status for topic: {topic_arn}")
        
        # Send success response
        send_response(event, context, 'SUCCESS', {
            'Message': 'Delivery status configured successfully'
        })
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        send_response(event, context, 'FAILED', {
            'Message': str(e)
        })

def send_response(event, context, status, data):
    import urllib3
    
    response_body = {
        'Status': status,
        'Reason': data.get('Message', 'See CloudWatch logs'),
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data
    }
    
    http = urllib3.PoolManager()
    response = http.request(
        'PUT',
        event['ResponseURL'],
        body=json.dumps(response_body).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    print(f"Response status: {response.status}")
            """),
            timeout=Duration.minutes(5),
            description="Lambda to configure SNS delivery status"
        )
        
        # Grant permissions to configure SNS
        config_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sns:SetTopicAttributes",
                    "sns:GetTopicAttributes"
                ],
                resources=[self.newsletter_topic.topic_arn]
            )
        )
        
        return config_lambda
    
    def _subscribe_test_email(self, email: str):
        """Subscribe a test email to the newsletter"""
        self.newsletter_topic.add_subscription(
            sns_subs.EmailSubscription(email)
        )
        
        # Output subscription info
        CfnOutput(
            self,
            "TestEmailSubscription",
            value=email,
            description="Test email subscribed to newsletter (requires confirmation)"
        )
    
    def _create_outputs(self):
        """Create CloudFormation outputs"""
        CfnOutput(
            self,
            "NewsletterTopicArn",
            value=self.newsletter_topic.topic_arn,
            description="ARN of the newsletter SNS topic",
            export_name=f"{self.stack_name}-newsletter-topic-arn"
        )
        
        CfnOutput(
            self,
            "TrackingQueueUrl",
            value=self.tracking_queue.queue_url,
            description="URL of the tracking SQS queue",
            export_name=f"{self.stack_name}-tracking-queue-url"
        )
        
        CfnOutput(
            self,
            "TrackingQueueArn",
            value=self.tracking_queue.queue_arn,
            description="ARN of the tracking SQS queue",
            export_name=f"{self.stack_name}-tracking-queue-arn"
        )
        
        CfnOutput(
            self,
            "DeadLetterQueueUrl",
            value=self.dlq.queue_url,
            description="URL of the dead letter queue",
            export_name=f"{self.stack_name}-dlq-url"
        )
        
        CfnOutput(
            self,
            "SNSRoleArn",
            value=self.sns_role.role_arn,
            description="ARN of the SNS delivery role",
            export_name=f"{self.stack_name}-sns-role-arn"
        )
    
    # Utility methods for post-deployment operations
    def get_topic_arn(self) -> str:
        """Get the newsletter topic ARN"""
        return self.newsletter_topic.topic_arn
    
    def get_queue_url(self) -> str:
        """Get the tracking queue URL"""
        return self.tracking_queue.queue_url