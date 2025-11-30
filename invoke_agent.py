#!/usr/bin/env python3
"""
Interactive Chat Script for AWS Newsletter Agent (Datadog Tracing Demo)

This script provides a simple chat interface to interact with the deployed
AgentCore agent. It processes streaming responses in real-time.

Usage:
    python invoke_agent.py                          # Interactive chat mode
    python invoke_agent.py --prompt "Your message"  # Single prompt mode
"""

import argparse
import boto3
import json
import sys
import os
import uuid
from typing import Generator, Optional


def get_agent_arn() -> str:
    """Get agent ARN from config file or environment."""
    # Try environment variable first
    if os.environ.get("AGENT_ARN"):
        return os.environ["AGENT_ARN"]

    # Try reading from .bedrock_agentcore.yaml
    config_path = os.path.join(os.path.dirname(__file__), "agent", ".bedrock_agentcore.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            default_agent = config.get("default_agent")
            if default_agent and default_agent in config.get("agents", {}):
                arn = config["agents"][default_agent].get("bedrock_agentcore", {}).get("agent_arn")
                if arn:
                    return arn
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")

    raise ValueError(
        "Agent ARN not found. Set AGENT_ARN environment variable or ensure "
        "agent/.bedrock_agentcore.yaml exists with agent_arn configured."
    )


def get_region() -> str:
    """Get AWS region from config or environment."""
    if os.environ.get("AWS_REGION"):
        return os.environ["AWS_REGION"]

    config_path = os.path.join(os.path.dirname(__file__), "agent", ".bedrock_agentcore.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            default_agent = config.get("default_agent")
            if default_agent and default_agent in config.get("agents", {}):
                region = config["agents"][default_agent].get("aws", {}).get("region")
                if region:
                    return region
        except Exception:
            pass

    return "us-west-2"


# Fixed session ID for consistent tracing (must be at least 33 characters)
DEFAULT_SESSION_ID = "datadog-tracing-demo-session-0001"  # 34 chars


def parse_sse_data(content: str) -> Optional[str]:
    """Parse a single SSE data line and extract the text content."""
    try:
        # First parse: unwrap the outer JSON string
        outer = json.loads(content)

        if isinstance(outer, str):
            # It's a JSON-encoded string, parse again
            try:
                inner = json.loads(outer)
                if isinstance(inner, dict):
                    if "data" in inner:
                        return inner["data"]
                    # Skip event/tool messages
                    if "event" in inner or "toolUseId" in inner:
                        return None
                return outer
            except json.JSONDecodeError:
                return outer
        elif isinstance(outer, dict):
            if "data" in outer:
                return outer["data"]
            # Skip event/tool messages
            if "event" in outer or "toolUseId" in outer:
                return None
        return None
    except json.JSONDecodeError:
        return None


def stream_response(
    client,
    agent_arn: str,
    prompt: str,
    session_id: Optional[str] = None,
    show_tools: bool = True
) -> Generator[str, None, None]:
    """
    Invoke the agent and stream the response.

    Yields text chunks as they arrive.
    """
    if not session_id:
        session_id = DEFAULT_SESSION_ID

    payload = json.dumps({"prompt": prompt})

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        payload=payload.encode('utf-8'),
        runtimeSessionId=session_id,
        qualifier="DEFAULT"
    )

    tools_used = []

    # Process the streaming response - try both formats
    event_stream = response.get("responseStream") or response.get("response", [])

    # Buffer for incomplete lines
    buffer = ""

    for event in event_stream:
        # Handle EventStream format (responseStream)
        if isinstance(event, dict) and "chunk" in event:
            chunk_data = event["chunk"].get("bytes", b"")
            if chunk_data:
                try:
                    chunk_json = json.loads(chunk_data.decode('utf-8'))

                    # Handle text data
                    if "data" in chunk_json:
                        yield chunk_json["data"]

                    # Track tool usage for observability
                    if show_tools:
                        if "toolUseId" in chunk_json and "name" in chunk_json:
                            tool_name = chunk_json["name"]
                            if tool_name not in tools_used:
                                tools_used.append(tool_name)
                                print(f"\n[Tool: {tool_name}]", file=sys.stderr)

                except json.JSONDecodeError:
                    yield chunk_data.decode('utf-8')

        # Handle bytes format (response) - StreamingBody chunks
        elif isinstance(event, bytes):
            text = buffer + event.decode('utf-8')
            buffer = ""

            # Split by double newlines (SSE message separator)
            lines = text.split('\n')

            for i, line in enumerate(lines):
                line = line.strip()

                # If this is the last line and doesn't end properly, buffer it
                if i == len(lines) - 1 and line and not text.endswith('\n'):
                    buffer = line
                    continue

                if not line:
                    continue

                if line.startswith('data: '):
                    content = line[6:]
                    result = parse_sse_data(content)
                    if result is not None:
                        yield result


def print_header(agent_arn: str, session_id: str):
    """Print the chat header."""
    print("\n" + "=" * 70)
    print("  AWS Newsletter Agent - Datadog Tracing Demo")
    print("=" * 70)
    print(f"Agent ARN: {agent_arn}")
    print(f"Session:   {session_id}")
    print("-" * 70)
    print("Type your message and press Enter to chat with the agent.")
    print("Commands: 'quit' or 'exit' to end, 'clear' to reset session")
    print("=" * 70 + "\n")


def interactive_chat(client, agent_arn: str):
    """Run an interactive chat session."""
    session_id = DEFAULT_SESSION_ID
    print_header(agent_arn, session_id)

    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('quit', 'exit', 'q'):
                print("\nGoodbye!")
                break

            if user_input.lower() == 'clear':
                print(f"\nSession cleared. (Session ID remains: {session_id})")
                continue

            # Stream the response
            print("\nAgent: ", end="", flush=True)

            for chunk in stream_response(client, agent_arn, user_input, session_id):
                print(chunk, end="", flush=True)

            print()  # Newline after response

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue


def single_prompt(client, agent_arn: str, prompt: str):
    """Execute a single prompt and print the response."""
    session_id = DEFAULT_SESSION_ID

    print(f"Session: {session_id}")
    print(f"Prompt: {prompt}\n")
    print("Agent: ", end="", flush=True)

    for chunk in stream_response(client, agent_arn, prompt, session_id):
        print(chunk, end="", flush=True)

    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Chat with the AWS Newsletter Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive chat mode
    python invoke_agent.py

    # Single prompt
    python invoke_agent.py --prompt "What's new in AWS AI today?"

    # Generate and send newsletter
    python invoke_agent.py --prompt "Generate and send a newsletter about AWS AI news"

    # Schedule the agent
    python invoke_agent.py --prompt "Schedule yourself for 8 AM daily"
"""
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Single prompt to send (skips interactive mode)"
    )
    parser.add_argument(
        "--agent-arn",
        help="Override agent ARN (default: from config)"
    )
    parser.add_argument(
        "--region",
        help="AWS region (default: from config or us-west-2)"
    )

    args = parser.parse_args()

    # Get configuration
    try:
        agent_arn = args.agent_arn or get_agent_arn()
        region = args.region or get_region()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Create client
    client = boto3.client("bedrock-agentcore", region_name=region)

    print(f"Agent: {agent_arn}")
    print(f"Region: {region}")

    if args.prompt:
        # Single prompt mode
        single_prompt(client, agent_arn, args.prompt)
    else:
        # Interactive chat mode
        interactive_chat(client, agent_arn)


if __name__ == "__main__":
    main()
