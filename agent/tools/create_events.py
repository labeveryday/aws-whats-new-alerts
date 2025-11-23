from strands import tool
import boto3
import os
import json
from typing import Literal

# Get configuration from environment - lazily loaded in functions
# AGENT_RUNTIME_ARN = os.getenv("AGENT_RUNTIME_ARN") 
# SCHEDULER_ROLE_ARN = os.getenv("SCHEDULER_ROLE_ARN")
# AGENT_NAME = os.getenv("AGENT_NAME", "aws_newsletter_bot")

@tool
def find_agent_id(agent_name: str) -> str:
    """
    Find the ARN of an AgentCore Runtime agent by its name.
    Useful for self-discovery when the agent needs to know its own identity.
    
    Args:
        agent_name: Name or partial name of the agent to find
        
    Returns:
        The ARN of the matching agent, or an error message if not found
    """
    try:
        # Get region from environment or default to us-west-2
        region = os.getenv("AWS_REGION", "us-west-2")
        # Use the Control Plane client for listing runtimes
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        # List agents (paginated)
        paginator = client.get_paginator('list_agent_runtimes')
        
        for page in paginator.paginate():
            for agent in page.get('agentRuntimes', []):
                # Check against agentRuntimeName (API field)
                if agent_name in agent.get('agentRuntimeName', ''):
                    return agent['agentRuntimeArn']
                    
        return f"❌ No agent found matching name: {agent_name}"
        
    except Exception as e:
        return f"Error finding agent: {str(e)}"

@tool
def manage_eventbridge_schedule(
    action: Literal["create", "update", "delete", "list", "status"],
    schedule_name: str = "aws-news-alerts",
    frequency: Literal["hourly", "daily", "weekly", "monthly"] = "weekly",
    day_of_week: str = "FRI",
    time: str = "09:00",
    timezone: str = "America/Los_Angeles",
    agent_name: str = "aws_newsletter_bot"
) -> str:
    """
    Manage EventBridge Scheduler rules for automated newsletter delivery.
    
    Args:
        action: Operation to perform on the schedule
        schedule_name: Unique identifier for the schedule
        frequency: How often to send newsletters
        day_of_week: For weekly frequency (MON, TUE, WED, etc.)
        time: Time to send (HH:MM format)
        timezone: IANA timezone identifier
        agent_name: Name of the agent to invoke (for self-discovery)
    
    Returns:
        Status message about the schedule operation
    """
    # Get region from environment or default to us-west-2
    region = os.getenv("AWS_REGION", "us-west-2")
    scheduler = boto3.client('scheduler', region_name=region)
    
    # Load lazy configuration
    SCHEDULER_ROLE_ARN = os.getenv("SCHEDULER_ROLE_ARN")
    AGENT_RUNTIME_ARN = os.getenv("AGENT_RUNTIME_ARN")

    try:
        if action == "list":
            response = scheduler.list_schedules()
            schedules = [s['Name'] for s in response['Schedules']]
            return f"Active schedules: {', '.join(schedules)}"
        
        elif action == "status":
            response = scheduler.get_schedule(Name=schedule_name)
            return f"Schedule '{schedule_name}': {response['ScheduleExpression']}, State: {response['State']}"
        
        elif action in ["create", "update"]:
            if not SCHEDULER_ROLE_ARN:
                return "❌ Configuration Error: SCHEDULER_ROLE_ARN not set in environment."

            # Self-discovery of Agent ARN if not provided in env
            target_agent_arn = AGENT_RUNTIME_ARN
            if not target_agent_arn:
                # Try to find it dynamically
                discovery_result = find_agent_id(agent_name)
                if "arn:aws:" in discovery_result:
                    target_agent_arn = discovery_result
                else:
                    return f"❌ Could not determine Agent ARN. Environment variable missing and auto-discovery failed: {discovery_result}"

            cron_expression = _build_cron(frequency, day_of_week, time)
            
            # Generate context-aware prompt based on frequency
            prompt_map = {
                "hourly": "Generate hourly AWS newsletter covering announcements from the last hour. Focus on AI/ML updates.",
                "daily": "Generate a daily AWS newsletter covering announcements from the last 24 hours.",
                "weekly": "Generate a weekly AWS newsletter covering announcements from the last 7 days.",
                "monthly": "Generate a monthly AWS newsletter covering announcements from the last 30 days."
            }
            scheduled_prompt = prompt_map.get(frequency, "Generate newsletter based on schedule trigger")

            # Target configuration for AgentCore Runtime
            target_config = {
                'Arn': 'arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime',
                'RoleArn': SCHEDULER_ROLE_ARN,
                'Input': json.dumps({
                    "AgentRuntimeArn": target_agent_arn,
                    "Payload": json.dumps({
                        "prompt": scheduled_prompt
                    }),
                    "Qualifier": "DEFAULT"
                }),
                'RetryPolicy': {
                    'MaximumRetryAttempts': 3,
                    'MaximumEventAgeInSeconds': 3600
                }
            }

            if action == "create":
                scheduler.create_schedule(
                    Name=schedule_name,
                    ScheduleExpression=cron_expression,
                    ScheduleExpressionTimezone=timezone,
                    FlexibleTimeWindow={'Mode': 'OFF'},
                    Target=target_config
                )
                return f"Created schedule '{schedule_name}' for {frequency} delivery"
            
            else: # update
                scheduler.update_schedule(
                    Name=schedule_name,
                    ScheduleExpression=cron_expression,
                    ScheduleExpressionTimezone=timezone,
                    FlexibleTimeWindow={'Mode': 'OFF'},
                    Target=target_config
                )
                return f"Updated schedule '{schedule_name}' to {frequency} delivery"
        
        elif action == "delete":
            scheduler.delete_schedule(Name=schedule_name)
            return f"Deleted schedule '{schedule_name}'"
    
    except Exception as e:
        return f"Error managing schedule: {str(e)}"

def _build_cron(frequency: str, day_of_week: str, time: str) -> str:
    """Convert frequency to EventBridge cron expression."""
    hour, minute = time.split(':')
    
    if frequency == "hourly":
        return f"cron(0 * * * ? *)"
    elif frequency == "daily":
        return f"cron({minute} {hour} * * ? *)"
    elif frequency == "weekly":
        return f"cron({minute} {hour} ? * {day_of_week} *)"
    elif frequency == "monthly":
        return f"cron({minute} {hour} 1 * ? *)"