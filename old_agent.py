"""
AWS News Agent with Email Notifications and Memory
Monitors AWS news for AI-related content and sends email alerts via SNS
"""
import os
import argparse
from datetime import date
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from strands import Agent
from strands_tools import http_request, current_time
from dotenv import load_dotenv

load_dotenv()

# Configuration
AWS_URL = "https://aws.amazon.com/new/"
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")  # Your email subscription topic
MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID")  # Your memory ID
CUTOFF_DATE = "2025-10-01"

SYSTEM_PROMPT = f"""
You are an AWS news monitoring agent that sends email notifications via SNS for AI-related content.

CORE MISSION: Monitor AWS news and email me about AI/ML developments with LinkedIn post suggestions.

WORKFLOW:
1. Use current_time tool to get today's date
2. Use http_request tool to fetch latest news from {AWS_URL}
3. Filter articles: Only process those published >= {CUTOFF_DATE} (unless user specifically asks for historical)
4. Check memory to avoid duplicate processing
5. For NEW articles, extract: title, summary, link, publish_date
6. Analyze for AI relevance using these keywords:
   - agentic AI, autonomous agents, AI workflows
   - bedrock agents, strands, agentcore  
   - multi-agent systems, AI orchestration
   - machine learning automation, generative AI
   - AI/ML services, intelligent automation
7. For AI-related articles:
   - Create engaging email content
   - Suggest LinkedIn post with insights
   - Send email via publish_message tool to: {SNS_TOPIC_ARN}
8. Store processed articles in memory

EMAIL FORMAT:
Subject: "🤖 AWS AI News Alert - [Article Title]"
Message:
```
🚀 NEW AWS AI DEVELOPMENT DETECTED!

📰 Article: [Title]
🔗 Link: [URL]  
📅 Published: [Date]

🤖 AI Relevance: [Explain why this matters for AI/ML community]

💼 Suggested LinkedIn Post:
[Write engaging post with emojis, insights, and relevant hashtags]

---
Sent by AWS News AI Agent
```

MEMORY USAGE:
- Query existing processed articles to prevent duplicate emails
- Store new article URLs and processing timestamps
- Remember AI detection patterns for improvement

IMPORTANT: Only send emails for genuinely AI-related content. Be selective but don't miss important developments.
"""

def create_aws_agent():
    """Create AWS news agent with memory and email capabilities"""
    
    # Skip memory setup if no memory ID provided (for testing)
    if MEMORY_ID:
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=f"aws-news-{date.today().isoformat()}",
            actor_id="aws-news-emailer",
            retrieval_config={
                "/articles/processed": RetrievalConfig(
                    top_k=50,
                    relevance_score=0.8,
                    initialization_query=f"What AWS articles published since {CUTOFF_DATE} have been processed and emailed?"
                ),
                "/detection/ai-patterns": RetrievalConfig(
                    top_k=10,
                    relevance_score=0.7
                )
            }
        )
        
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name="us-east-1"
        )
        
        return Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[http_request, current_time],
            load_tools_from_directory=True,
            session_manager=session_manager
        )
    else:
        # No memory - for basic testing
        print("⚠️  No AGENTCORE_MEMORY_ID found - running without persistent memory")
        return Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[http_request, current_time],
            load_tools_from_directory=True
        )

# Create the agent
aws_agent = create_aws_agent()

# Instantiate Bedrock AgentCore
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke_agent(payload):
    """
    Handler for agent invocation with email notifications
    """
    prompt = payload.get("prompt")
    
    # Add context about available tools
    enhanced_prompt = f"""
    {prompt}
    
    AVAILABLE TOOLS:
    - current_time: Get current date/time
    - http_request: Fetch web content from AWS news page
    - publish_message: Send email via SNS (use topic ARN: {SNS_TOPIC_ARN})
    - All SNS tools from tools directory
    
    Remember: Only email about genuinely AI-related AWS developments!
    """
    
    response = aws_agent(enhanced_prompt)
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS News AI Agent")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the agent on")
    args = parser.parse_args()
    
    print(f"🤖 AWS News AI Agent starting on port {args.port}")
    print(f"📧 Email notifications: {'✅ Configured' if SNS_TOPIC_ARN else '❌ Missing SNS_TOPIC_ARN'}")
    print(f"🧠 Memory: {'✅ Enabled' if MEMORY_ID else '❌ Disabled (set AGENTCORE_MEMORY_ID)'}")
    print(f"📅 Processing articles from: {CUTOFF_DATE} onwards")
    
    app.run(port=args.port)