"""
AWS Daily Newsletter Agent
Creates daily email newsletters in professional format with numbered announcements
"""
import os
import argparse
from datetime import datetime
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from strands import Agent
from strands_tools import http_request, current_time
import sys
import os
sys.path.append(os.path.dirname(__file__))
from dotenv import load_dotenv
from pprint import pprint


load_dotenv()

# Configuration
AWS_URL = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
CUTOFF_DATE = "2022-10-01"

# Agent Identity Configuration
ACTOR_ID = os.getenv("AGENT_ACTOR_ID", "aws-newsletter-bot")
SESSION_ID = os.getenv("AGENT_SESSION_ID", "aws-newsletter-main-session")

SYSTEM_PROMPT = f"""
You are an AWS Daily Newsletter Agent that creates professional daily email newsletters about AWS announcements.

CORE MISSION: Generate a daily newsletter focused on AI-related AWS announcements only (unless user asks for broader coverage).

WORKFLOW:
1. Use current_time tool to get today's date
2. Use http_request tool to fetch latest news from AWS RSS feed: {AWS_URL}
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
6. Memory check: Previously processed article URLs will be available in session context
7. Parse RSS feed XML to extract article entries with: title, link, pubDate, description
8. Cross-reference: Skip any article URLs found in memory (already processed)
9. Extract AI-RELATED articles (NEW ones only) with: title, summary, link, publish_date
10. If NO new articles: Send "Nothing new today" newsletter
11. If new articles found: Create formatted newsletter with casual style
12. Send email via publish_newsletter tool (automatically uses correct SNS topic)
13. Mention the processed article URLs in your response (memory will automatically extract them)

NEWSLETTER FORMAT:
Subject: "[AWSNews] [brief descriptive subject]"

Message (casual, conversational style):
```
[casual opening line about the day/news volume]

AWS News for [DATE RANGE]. We checked AWS What's New, AWS Blog, and AWS announcements for you.

[IF NO NEW ANNOUNCEMENTS]:
Not much happening in AWS AI/ML land today...

[IF NEW ANNOUNCEMENTS]:
[Brief editorial comment about the news/trends]

AWS AI/ML Updates
[Section organized by theme/service - NO numbering, use bullet format]

[SERVICE/THEME]: [Brief descriptive title]
[2-3 sentence summary in conversational tone]. [Technical details and implications]. See announcement from @AWSCloudNews or aws.amazon.com/new.

[Continue with other announcements...]

Additional AWS Updates
[Any non-AI announcements if relevant]

Notes and Links
• Full AWS announcements: aws.amazon.com/new/
• AWS AI/ML Blog: aws.amazon.com/blogs/machine-learning/
• Feedback: [your contact]

Stats: [X] announcements checked, [X] AI/ML relevant, [X] duplicates skipped.
```

STYLE GUIDELINES:
- Keep it conversational and brief
- Use bullet points, not numbered lists
- Group related announcements by service/theme
- Include casual editorial comments
- Add "See announcement from..." attributions
- Keep technical details accessible
- Use line breaks for readability
- No ASCII borders or formal formatting

MEMORY & DEDUPLICATION:
- Session automatically queries /newsletter/articles for previously processed articles
- Before creating newsletter, identify which article URLs are NEW vs ALREADY PROCESSED
- Only include NEW articles in the newsletter
- Explicitly mention processed article URLs in your response for future deduplication
- Example: "Processed 3 new articles: [url1], [url2], [url3]. Skipped 5 duplicates from memory."

IMPORTANT RULES:
1. DEFAULT: Only include AI-related content (unless user asks for "all announcements")
2. LISTEN TO USER'S TIME FRAME - if they say "last week", process last week!
3. Use bullet points and conversational style, NOT numbered lists
4. Include the actual announcement date from AWS (not today's date)
5. Include full blog post URLs for each announcement
6. If zero NEW AI announcements found, send casual "not much happening" version
7. Focus on AI/ML implications in summaries
8. Keep tone casual and accessible, like the smol.ai example
9. DEFAULT to last 24 hours only when user doesn't specify a time frame
10. Override AI filter only if user specifically asks for "all announcements" or broader coverage
11. Group announcements by service/theme, not chronologically
12. Add brief editorial comments about trends/significance
"""

# Instantiate Bedrock AgentCore
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke_agent(payload, context):
    """
    Handler for daily newsletter generation with proper memory integration.
    Creates a new agent instance per invocation (no lazy loading with memory).
    """
    if not MEMORY_ID:
        return {"error": "Memory not configured. Set BEDROCK_AGENTCORE_MEMORY_ID environment variable."}

    try:
        # Use consistent actor and session IDs for persistent memory
        actor_id = ACTOR_ID
        session_id = SESSION_ID

        # Create agent instance with memory configuration
        # Note: We create a new instance per invocation to ensure proper session isolation
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config={
                "/newsletter/articles": RetrievalConfig(
                    top_k=50,
                    relevance_score=0.8,
                    initialization_query=f"What AWS articles have been processed in recent newsletters since {CUTOFF_DATE}? List all article URLs and publication dates."
                ),
                "/newsletter/preferences": RetrievalConfig(
                    top_k=20,
                    relevance_score=0.7
                )
            }
        )

        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name=os.getenv("AWS_REGION", "us-west-2")
        )

        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[http_request, current_time],
            load_tools_from_directory=True,  # Loads the newsletter_tools automatically
            session_manager=session_manager
        )

        pprint(agent.messages)

        # Pass prompt directly to agent
        prompt = payload.get("prompt", "Generate daily AWS AI/ML newsletter for the last 24 hours")
        
        # Add retry logic for Bedrock calls
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = agent(prompt)
                return response
            except Exception as agent_error:
                if "serviceUnavailableException" in str(agent_error) and attempt < max_retries - 1:
                    import time
                    wait_time = (2 ** attempt) * 1  # Exponential backoff: 1s, 2s, 4s
                    print(f"Bedrock unavailable, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise agent_error

    except Exception as e:
        error_msg = str(e)
        
        # Provide more helpful error messages
        if "serviceUnavailableException" in error_msg:
            return {"error": "Bedrock service temporarily unavailable. EventBridge will retry this request automatically."}
        elif "throttlingException" in error_msg:
            return {"error": "Rate limit exceeded. Reduce request frequency or upgrade quota."}
        elif "validationException" in error_msg:
            return {"error": f"Configuration error: {error_msg}"}
        else:
            return {"error": f"Agent execution failed: {error_msg}"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Daily Newsletter Agent")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the agent on")
    args = parser.parse_args()

    today = datetime.now().strftime("%B %d, %Y")
    print(f"📰 AWS Daily Newsletter Agent starting on port {args.port}")
    print(f"📅 Today's newsletter date: {today}")
    print(f"📧 Email delivery: {'✅ Configured' if SNS_TOPIC_ARN else '❌ Missing SNS_TOPIC_ARN'}")
    print(f"🧠 Memory: {'✅ Enabled' if MEMORY_ID else '❌ Disabled (set BEDROCK_AGENTCORE_MEMORY_ID)'}")
    print(f"📅 Processing articles from: {CUTOFF_DATE} onwards")

    app.run(port=args.port)
