"""
AWS Daily Newsletter Agent
Creates daily email newsletters in professional format with numbered announcements
"""
import os
import argparse
from datetime import date, datetime
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
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")  # Your memory ID
CUTOFF_DATE = "2022-10-01"

SYSTEM_PROMPT = f"""
You are an AWS Daily Newsletter Agent that creates professional daily email newsletters about AWS announcements.

CORE MISSION: Generate a daily newsletter focused on AI-related AWS announcements only (unless user asks for broader coverage).

WORKFLOW:
1. Use current_time tool to get today's date
2. Use http_request tool to fetch latest news from {AWS_URL}
3. FOLLOW USER'S TIME FRAME REQUEST:
   - If user says "last week" or "7 days" → process last 7 days
   - If user says "last month" → process last 30 days  
   - If user says "yesterday" → process last 24 hours
   - If user says "last 3 days" → process last 3 days
   - DEFAULT (no time specified): process last 24 hours for daily newsletter
4. Always filter: Only process articles published >= {CUTOFF_DATE}
5. FILTER FOR AI-RELATED CONTENT ONLY (unless user asks for "all announcements" or broader coverage):
   - AI, Artificial Intelligence, Machine Learning, ML
   - Agentic AI, autonomous agents, AI workflows
   - Bedrock, Claude, generative AI, LLMs
   - Strands agents, Kiro, AgentCore
   - SageMaker, AI/ML services, intelligent automation
   - Computer vision, natural language processing, NLP
   - AI model training, inference, fine-tuning
6. Check memory to avoid duplicate processing
7. Extract AI-RELATED articles from the USER-SPECIFIED time frame with: title, summary, link, publish_date
6. If NO new articles: Send "Nothing new today" newsletter
7. If new articles found: Create formatted newsletter with numbered announcements
8. Send email via publish_message tool to: {SNS_TOPIC_ARN}
9. Store processed articles in memory with today's date

NEWSLETTER FORMAT:
Subject: "🌟 AWS DAILY NEWSLETTER | [TODAY'S DATE] 🌟"

Message:
```
═══════════════════════════════════════════════════════════════
🌟 AWS DAILY NEWSLETTER | [FULL DATE] 🌟
═══════════════════════════════════════════════════════════════

Dear AWS Community,

[IF NO NEW ANNOUNCEMENTS]:
No new AWS announcements today. Check back tomorrow for the latest updates!

[IF NEW ANNOUNCEMENTS]:
Today brings [X] new AWS announcements! Here's your comprehensive roundup:

🤖 TODAY'S AI/ML ANNOUNCEMENTS
═══════════════════════════════════════════════════════════════

[FOR EACH AI-RELATED ANNOUNCEMENT - NUMBERED]:
[#]. **[TITLE]** | [ANNOUNCEMENT DATE]
    🔗 [FULL BLOG POST URL]
    📋 [2-3 sentence summary focusing on AI/ML implications and why this matters for AI developers]
    
[Continue numbering for each announcement...]

📊 BY THE NUMBERS TODAY
═══════════════════════════════════════════════════════════════

🤖 [X] Total AI/ML Announcements
🧠 [X] Bedrock/LLM Updates
🤖 [X] Agent/Agentic AI Features
📊 [X] SageMaker/ML Services
🔬 [X] AI Research/Innovation

═══════════════════════════════════════════════════════════════
📧 Questions? Visit aws.amazon.com
🔔 Subscribe to AWS What's New: aws.amazon.com/new/
═══════════════════════════════════════════════════════════════
This newsletter was generated on [TODAY'S DATE]
© 2025 Amazon Web Services, Inc.
═══════════════════════════════════════════════════════════════
```

MEMORY USAGE:
- Query yesterday's processed articles to avoid duplicates
- Store today's articles with date stamps
- Track categories for statistics (AI/ML, Security, etc.)

IMPORTANT RULES:
1. DEFAULT: Only include AI-related content (unless user asks for "all announcements")
2. LISTEN TO USER'S TIME FRAME - if they say "last week", process last week!
3. Always number announcements (1., 2., 3., etc.)
4. Include the actual announcement date from AWS (not today's date)
5. Include full blog post URLs for each announcement
6. If zero AI announcements found, send "No AI news today" version
7. Focus on AI/ML implications in summaries
8. Always use the exact ASCII border style shown above
9. DEFAULT to last 24 hours only when user doesn't specify a time frame
10. Override AI filter only if user specifically asks for "all announcements" or broader coverage
"""

# Global agent instance for lazy loading pattern
_newsletter_agent = None

def get_or_create_agent(actor_id: str, session_id: str) -> Agent:
    """
    Get existing agent or create new one with memory configuration.
    Uses lazy loading pattern as recommended in AgentCore documentation.
    """
    global _newsletter_agent
    
    if _newsletter_agent is None:
        if MEMORY_ID:
            # Configure memory with proper retrieval configs for newsletter data
            memory_config = AgentCoreMemoryConfig(
                memory_id=MEMORY_ID,
                session_id=session_id,
                actor_id=actor_id,
                retrieval_config={
                    f"/newsletter/{actor_id}/processed": RetrievalConfig(
                        top_k=50,
                        relevance_score=0.8,
                        initialization_query=f"What AWS articles have been processed in recent newsletters since {CUTOFF_DATE}?"
                    ),
                    f"/newsletter/{actor_id}/ai_patterns": RetrievalConfig(
                        top_k=10,
                        relevance_score=0.7
                    )
                }
            )
            
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=memory_config,
                region_name="us-east-1"
            )
            
            _newsletter_agent = Agent(
                system_prompt=SYSTEM_PROMPT,
                tools=[http_request, current_time],
                load_tools_from_directory=True,
                session_manager=session_manager
            )
        else:
            # No memory - for basic testing
            print("⚠️  No BEDROCK_AGENTCORE_MEMORY_ID found - running without persistent memory")
            _newsletter_agent = Agent(
                system_prompt=SYSTEM_PROMPT,
                tools=[http_request, current_time],
                load_tools_from_directory=True
            )
    
    return _newsletter_agent

# Instantiate Bedrock AgentCore
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke_agent(payload, context):
    """
    Handler for daily newsletter generation with proper memory integration
    """
    if not MEMORY_ID:
        return {"error": "Memory not configured. Set BEDROCK_AGENTCORE_MEMORY_ID environment variable."}
    
    # Extract session and actor information (following blog post pattern)
    actor_id = context.request_headers.get('X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id', 'aws-newsletter-bot') if context.request_headers else 'aws-newsletter-bot'
    session_id = context.session_id or f"aws-newsletter-{date.today().isoformat()}"
    
    # Get or create agent with proper memory configuration (lazy loading)
    agent = get_or_create_agent(actor_id, session_id)
    
    prompt = payload.get("prompt")
    
    # Add context about available tools and today's mission
    today = datetime.now().strftime("%B %d, %Y")
    enhanced_prompt = f"""
    {prompt}
    
    TODAY'S MISSION: Generate AWS Daily Newsletter for {today}
    
    AVAILABLE TOOLS:
    - current_time: Get current date/time
    - http_request: Fetch AWS news from {AWS_URL}
    - publish_message: Send newsletter email (topic: {SNS_TOPIC_ARN})
    - Memory: Track processed articles to avoid duplicates
    
    REQUIREMENTS:
    1. FOLLOW THE USER'S TIME FRAME REQUEST (they said "{prompt}" - extract time period from this!)
    2. Number each announcement (1., 2., 3., etc.)
    3. Include announcement date and full blog URL for each
    4. If no new announcements, send "nothing new" newsletter
    5. Use the exact ASCII border formatting style
    6. Categorize for statistics section
    """
    
    response = agent(enhanced_prompt)
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Daily Newsletter Agent")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the agent on")
    args = parser.parse_args()
    
    today = datetime.now().strftime("%B %d, %Y")
    print(f"📰 AWS Daily Newsletter Agent starting on port {args.port}")
    print(f"📅 Today's newsletter date: {today}")
    print(f"📧 Email delivery: {'✅ Configured' if SNS_TOPIC_ARN else '❌ Missing SNS_TOPIC_ARN'}")
    print(f"🧠 Memory: {'✅ Enabled' if MEMORY_ID else '❌ Disabled (set AGENTCORE_MEMORY_ID)'}")
    print(f"📅 Processing articles from: {CUTOFF_DATE} onwards (last 24h only)")
    
    app.run(port=args.port)