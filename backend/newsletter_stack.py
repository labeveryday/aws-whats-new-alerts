"""
CDK Stack for AWS Newsletter System (Datadog Tracing Demo)

Simplified stack for testing Datadog tracing with AgentCore agents.
No authentication or frontend - just the core agent infrastructure.

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
    aws_sqs as sqs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_sns_subscriptions as sns_subs,
    aws_scheduler as scheduler,
    CfnOutput,
    Duration,
    RemovalPolicy
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

        # Create Secrets Manager Secret for Agent Config
        self.secret = self._create_agent_secret()

        # Create AgentCore Runtime IAM role
        self.agentcore_runtime_role = self._create_agentcore_runtime_role()

        # Create EventBridge Scheduler Role and DLQ (needed for agent tool)
        self.scheduler_role, self.scheduler_dlq = self._create_scheduler_resources()

        # Grant permissions to AgentCore Runtime Role
        self._grant_scheduler_permissions()

        # Create default EventBridge Schedule (if enabled and agentcore_arn provided)
        self.schedule = None
        if enable_scheduler and agentcore_arn:
            self.schedule = self._create_default_schedule()

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

    def _create_agent_secret(self) -> secretsmanager.Secret:
        """Create Secrets Manager Secret for Agent Configuration"""
        secret = secretsmanager.Secret(
            self,
            "AgentConfigSecret",
            secret_name=f"{self._stack_name}/agent-config",
            description=f"Configuration for {self._stack_name} agent (SNS topic, Memory ID, etc.)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"_comment": "Placeholder"}),
                generate_string_key="_dummy"
            )
        )
        cdk.Tags.of(secret).add("Component", "AgentConfigSecret")
        return secret

    def _create_agentcore_runtime_role(self) -> iam.Role:
        """Create IAM role for AgentCore Runtime to publish to SNS"""
        role = iam.Role(
            self,
            "AgentCoreRuntimeRole",
            role_name=f"{self._stack_name}-agentcore-runtime-role",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
            ),
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
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                ],
                resources=["*"]
            )
        )

        # Add ECR permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetAuthorizationToken"
                ],
                resources=["*"]
            )
        )

        # Add X-Ray/Telemetry permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                resources=["*"]
            )
        )

        # Add CloudWatch Metric permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            )
        )

        # Add Code Interpreter permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateCodeInterpreter",
                    "bedrock-agentcore:StartCodeInterpreterSession",
                    "bedrock-agentcore:InvokeCodeInterpreter",
                    "bedrock-agentcore:StopCodeInterpreterSession",
                    "bedrock-agentcore:DeleteCodeInterpreter",
                    "bedrock-agentcore:ListCodeInterpreters",
                    "bedrock-agentcore:GetCodeInterpreter",
                    "bedrock-agentcore:GetCodeInterpreterSession",
                    "bedrock-agentcore:ListCodeInterpreterSessions"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:aws:code-interpreter/*",
                    f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:code-interpreter/*",
                    f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:code-interpreter-custom/*"
                ]
            )
        )

        # Add Identity/OAuth permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:GetResourceApiKey",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                resources=[
                     f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:token-vault/*",
                     f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:workload-identity-directory/*"
                ]
            )
        )

        # Add SecretsManager permissions (for identity and agent config)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:bedrock-agentcore-identity*",
                    "arn:aws:secretsmanager:*:*:secret:*"  # Broadened to avoid ARN mismatch issues
                ]
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
                    "bedrock-agentcore:RetrieveMemoryRecords",  # Required for semantic extraction/RAG
                    # "bedrock-agentcore:QueryMemory"  # This action is invalid
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

        # CRITICAL: Add TagSession permission for AgentCore
        # We need to override the AssumeRolePolicyDocument to add sts:TagSession
        cfn_role = role.node.default_child
        cfn_role.add_property_override(
            "AssumeRolePolicyDocument",
            {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": ["sts:AssumeRole", "sts:TagSession"]
                }]
            }
        )

        # Add tags
        cdk.Tags.of(role).add("Component", "AgentCoreRuntimeRole")

        return role

    def _create_scheduler_resources(self):
        """Create IAM role and DLQ for EventBridge Scheduler"""
        # Create SQS Dead Letter Queue for failed schedule invocations
        dlq = sqs.Queue(
            self,
            "SchedulerDLQ",
            queue_name=f"{self._stack_name}-scheduler-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED
            # description is not supported in L2 construct for SQS Queue
        )
        cdk.Tags.of(dlq).add("Component", "SchedulerDLQ")

        # Create IAM role for EventBridge to invoke AgentCore Runtime
        role = iam.Role(
            self,
            "EventBridgeRole",
            role_name=f"{self._stack_name}-eventbridge-role",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
            description=f"Role for EventBridge Scheduler to invoke {self._stack_name} AgentCore Runtime"
        )
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("BedrockAgentCoreFullAccess"))

        # Add policy to send messages to DLQ
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl"
                ],
                resources=[dlq.queue_arn]
            )
        )
        cdk.Tags.of(role).add("Component", "EventBridgeRole")

        return role, dlq

    def _grant_scheduler_permissions(self):
        """Grant permissions for Agent to manage schedules"""
        # Allow Agent to manage schedules
        self.agentcore_runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:DeleteSchedule",
                    "scheduler:ListSchedules",
                    "scheduler:GetSchedule"
                ],
                resources=["*"]  # Scope this down if possible, but * is often needed for creation
            )
        )

        # Allow Agent to pass the scheduler role
        self.agentcore_runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[self.scheduler_role.role_arn]
            )
        )

        # Allow Agent to list other agents (Self-Discovery Pattern)
        self.agentcore_runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:ListAgentRuntimes"],
                resources=["*"]
            )
        )

    def _create_default_schedule(self) -> scheduler.CfnSchedule:
        """Create default daily EventBridge Schedule"""
        schedule_name = f"{self._stack_name}-daily-newsletter"

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
            schedule_expression="cron(0 11 * * ? *)",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="FLEXIBLE",
                maximum_window_in_minutes=5
            ),
            state="ENABLED",
            target=scheduler.CfnSchedule.TargetProperty(
                arn="arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime",
                role_arn=self.scheduler_role.role_arn,
                input=json.dumps(input_payload),
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(
                    maximum_retry_attempts=3,
                    maximum_event_age_in_seconds=3600
                ),
                dead_letter_config=scheduler.CfnSchedule.DeadLetterConfigProperty(
                    arn=self.scheduler_dlq.queue_arn
                )
            )
        )
        return schedule

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
            "AgentConfigSecretName",
            value=self.secret.secret_name,
            description="Name of the Secrets Manager secret for agent configuration",
            export_name=f"{self._stack_name}-agent-config-secret-name"
        )

        CfnOutput(
            self,
            "AgentCoreRuntimeRoleArn",
            value=self.agentcore_runtime_role.role_arn,
            description="ARN of the AgentCore Runtime role",
            export_name=f"{self._stack_name}-agentcore-runtime-role-arn"
        )

        CfnOutput(
            self,
            "EventBridgeRoleArn",
            value=self.scheduler_role.role_arn,
            description="ARN of the EventBridge role for Scheduler",
            export_name=f"{self._stack_name}-eventbridge-role-arn"
        )

        CfnOutput(
            self,
            "SchedulerDLQArn",
            value=self.scheduler_dlq.queue_arn,
            description="ARN of the Scheduler Dead Letter Queue",
            export_name=f"{self._stack_name}-scheduler-dlq-arn"
        )

        # EventBridge Schedule outputs (if created)
        if self.schedule:
            CfnOutput(
                self,
                "EventBridgeScheduleName",
                value=self.schedule.name,
                description="Name of the EventBridge Schedule",
                export_name=f"{self._stack_name}-schedule-name"
            )
