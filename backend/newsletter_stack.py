"""
CDK Stack for AWS Newsletter System

This stack creates:
1. SNS topic for email newsletters
2. AgentCore Memory for article deduplication
3. IAM role for AgentCore Runtime to publish to SNS
4. EventBridge Scheduler for autonomous operation (optional)
"""

from typing import Optional
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_sns as sns,
    aws_iam as iam,
    aws_sns_subscriptions as sns_subs,
    aws_scheduler as scheduler,
    CfnOutput,
    Duration
)
from aws_cdk import aws_bedrock_agentcore_alpha as agentcore
from aws_cdk import aws_bedrock_alpha as bedrock
from constructs import Construct
import json


class NewsletterStack(Stack):
    """CDK Stack for Newsletter Infrastructure"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stack_name: str,
        test_email: Optional[str] = None,
        agentcore_arn: Optional[str] = None,
        enable_scheduler: bool = False,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._stack_name = stack_name
        self.agentcore_arn = agentcore_arn

        # Create SNS topic
        self.newsletter_topic = self._create_sns_topic()

        # Create AgentCore Memory
        self.memory = self._create_agentcore_memory()

        # Create AgentCore Runtime IAM role
        self.agentcore_runtime_role = self._create_agentcore_runtime_role()

        # Create EventBridge Scheduler (if enabled and agentcore_arn provided)
        self.scheduler_resources = None
        if enable_scheduler and agentcore_arn:
            self.scheduler_resources = self._create_eventbridge_scheduler()

        # Subscribe test email if provided
        if test_email:
            self._subscribe_test_email(test_email)

        # Create outputs
        self._create_outputs()

    def _create_sns_topic(self) -> sns.Topic:
        """Create SNS topic for newsletters"""
        topic = sns.Topic(
            self,
            "NewsletterTopic",
            topic_name=f"{self._stack_name}-newsletter-topic",
            display_name=f"{self._stack_name} Newsletter"
        )

        # Add tags
        cdk.Tags.of(topic).add("Component", "NewsletterTopic")

        return topic

    def _create_agentcore_memory(self) -> agentcore.Memory:
        """Create AgentCore Memory with semantic and user preference strategies"""
        memory_name = f"{self._stack_name.replace('-', '_')}_agent_memory"

        memory = agentcore.Memory(
            self,
            "NewsletterMemory",
            memory_name=memory_name,
            description=f"Memory store for {self._stack_name} agent to track processed AWS articles and newsletter history",
            expiration_duration=Duration.days(30),  # Events expire after 30 days
            memory_strategies=[
                # Semantic strategy for intelligent content extraction
                agentcore.MemoryStrategy.using_semantic(
                    name="newsletter_facts",
                    namespaces=["/newsletter/articles"],
                    custom_extraction=agentcore.OverrideConfig(
                        model=bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_3_5_SONNET_V1_0,
                        append_to_prompt=(
                            "Extract facts for AWS article deduplication:\n"
                            "- Article URL (unique key for deduplication)\n"
                            "- Article title\n"
                            "- Publication date\n"
                            "- Processing timestamp (when included in newsletter)\n"
                            "Enable querying: 'Which article URLs have been processed?' to prevent duplicates."
                        )
                    )
                ),
                # User preference strategy for remembering user preferences
                agentcore.MemoryStrategy.using_user_preference(
                    name="user_prefs",
                    namespaces=["/newsletter/preferences"]
                )
            ]
        )

        # Add tags
        cdk.Tags.of(memory).add("Component", "AgentCoreMemory")

        return memory

    def _create_agentcore_runtime_role(self) -> iam.Role:
        """Create IAM role for AgentCore Runtime to publish to SNS"""
        role = iam.Role(
            self,
            "AgentCoreRuntimeRole",
            role_name=f"{self._stack_name}-agentcore-runtime-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=f"Role for {self._stack_name} AgentCore Runtime to publish to SNS"
        )

        # Add policy to publish to SNS topic
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[self.newsletter_topic.topic_arn]
            )
        )

        # Add CloudWatch logs permissions
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

        # Add AgentCore Memory permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:QueryMemory"
                ],
                resources=[self.memory.memory_arn]
            )
        )

        # Add Bedrock model permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]
            )
        )

        # Add tags
        cdk.Tags.of(role).add("Component", "AgentCoreRuntimeRole")

        return role

    def _create_eventbridge_scheduler(self) -> dict:
        """Create EventBridge Scheduler for autonomous daily execution"""
        if not self.agentcore_arn:
            return None

        # Create IAM role for EventBridge to invoke AgentCore Runtime
        eventbridge_role = iam.Role(
            self,
            "EventBridgeRole",
            role_name=f"{self._stack_name}-eventbridge-role",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
            description=f"Role for EventBridge Scheduler to invoke {self._stack_name} AgentCore Runtime",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("BedrockAgentCoreFullAccess")
            ]
        )

        # Create EventBridge Schedule
        schedule_name = f"{self._stack_name}-daily-newsletter"

        # Prepare the input payload for AgentCore Runtime (matching console format)
        input_payload = {
            "AgentRuntimeArn": self.agentcore_arn,
            "Payload": json.dumps({
                "prompt": "Generate daily AWS AI/ML newsletter for the last 24 hours. Check memory to avoid sending duplicate articles."
            })
        }

        schedule = scheduler.CfnSchedule(
            self,
            "DailySchedule",
            name=schedule_name,
            description=f"Daily trigger for {self._stack_name} newsletter agent",
            schedule_expression="cron(0 11 * * ? *)",  # 6 AM EST / 11 AM UTC daily
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="FLEXIBLE",
                maximum_window_in_minutes=5
            ),
            state="ENABLED",
            target=scheduler.CfnSchedule.TargetProperty(
                arn="arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime",
                role_arn=eventbridge_role.role_arn,
                input=json.dumps(input_payload),
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(
                    maximum_retry_attempts=3,
                    maximum_event_age_in_seconds=3600
                )
            )
        )

        # Add tags
        cdk.Tags.of(eventbridge_role).add("Component", "EventBridgeRole")

        return {
            "role": eventbridge_role,
            "schedule": schedule,
            "schedule_name": schedule_name
        }

    def _subscribe_test_email(self, email: str):
        """Subscribe a test email to the newsletter"""
        self.newsletter_topic.add_subscription(
            sns_subs.EmailSubscription(email)  # ✅ Uses correct import
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
            export_name=f"{self._stack_name}-newsletter-topic-arn"
        )

        CfnOutput(
            self,
            "MemoryId",
            value=self.memory.memory_id,
            description="ID of the AgentCore Memory",
            export_name=f"{self._stack_name}-memory-id"
        )

        CfnOutput(
            self,
            "MemoryArn",
            value=self.memory.memory_arn,
            description="ARN of the AgentCore Memory",
            export_name=f"{self._stack_name}-memory-arn"
        )

        CfnOutput(
            self,
            "AgentCoreRuntimeRoleArn",
            value=self.agentcore_runtime_role.role_arn,
            description="ARN of the AgentCore Runtime role",
            export_name=f"{self._stack_name}-agentcore-runtime-role-arn"
        )

        # EventBridge Scheduler outputs (if created)
        if self.scheduler_resources:
            CfnOutput(
                self,
                "EventBridgeScheduleName",
                value=self.scheduler_resources["schedule_name"],
                description="Name of the EventBridge Schedule",
                export_name=f"{self._stack_name}-schedule-name"
            )

            CfnOutput(
                self,
                "EventBridgeRoleArn",
                value=self.scheduler_resources["role"].role_arn,
                description="ARN of the EventBridge role",
                export_name=f"{self._stack_name}-eventbridge-role-arn"
            )
