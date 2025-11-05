from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import editor, shell


model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    max_tokens=64000,
    additional_request_fields={
        "thinking": {
            "type": "disabled",
        }
    },
)


agentcore_mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="uvx",
        args=["awslabs.amazon-bedrock-agentcore-mcp-server@latest"],
        autoApprove=[
            "search_agentcore_docs",
            "fetch_agentcore_doc"
        ]
    )
))

strands_mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="uvx",
        args=["strands-agents-mcp-server"],
        autoApprove=[
            "search_docs",
            "fetch_doc"
        ]
    )
))


# Manual lifecycle management
with agentcore_mcp_client, strands_mcp_client:
    # Get the tools from the MCP server
    tools = agentcore_mcp_client.list_tools_sync() + strands_mcp_client.list_tools_sync()

    # Create an agent with these tools
    agent = Agent(
        tools=tools + [editor, shell],
        )
    while True:
        prompt = input("\nUser: ")

        if prompt == "exit":
            break
        agent(prompt) 