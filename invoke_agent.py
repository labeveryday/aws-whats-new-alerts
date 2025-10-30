"""
AgentCore Runtime Invoker

Invokes a deployed AgentCore agent via AWS Bedrock AgentCore client.
Requires AGENTCORE_ARN environment variable to be set.

Usage:
  Single prompt: python invoke_agent.py --prompt "Your question here"
  Conversation: python invoke_agent.py
"""

import os
import json
import uuid
import boto3
import sys
from dotenv import load_dotenv

load_dotenv()

agent_arn = os.getenv("AGENTCORE_ARN", "")
if not agent_arn:
    raise ValueError("AGENTCORE_ARN not set in .env file")

agent_core_client = boto3.client('bedrock-agentcore', region_name="us-west-2")

def invoke_agent(prompt):
    payload = json.dumps({"prompt": prompt}).encode()
    response = agent_core_client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=payload,
        qualifier="DEFAULT"
    )
    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode('utf-8'))
    return json.loads(''.join(content))

if len(sys.argv) > 1 and sys.argv[1] == "--prompt":
    # Single prompt mode
    prompt = " ".join(sys.argv[2:])
    print(invoke_agent(prompt))
else:
    # Conversation mode
    print("Chat mode (type 'quit' to exit)")
    while True:
        prompt = input("You: ")
        if prompt.lower() in ['quit', 'exit', 'bye']:
            break
        print(f"Agent: {invoke_agent(prompt)}")