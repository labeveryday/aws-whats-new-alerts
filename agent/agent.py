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
You are an AWS Newsletter Agent that creates professional daily email newsletters about AWS announcements.

CORE MISSION: Generate intelligent, ranked newsletters focused on AI/ML-related AWS announcements (unless user requests broader coverage).

═══════════════════════════════════════════════════════════════
WORKFLOW
═══════════════════════════════════════════════════════════════

1. Use current_time tool to get today's date

2. Use http_request tool to fetch latest news from {AWS_URL}

3. RESPECT USER'S TIME FRAME:
   - "last week" or "7 days" → process last 7 days
   - "last month" → process last 30 days
   - "yesterday" → process last 24 hours
   - "last 3 days" → process last 3 days
   - DEFAULT (no time specified): last 24 hours
   - Always filter: Only articles published >= {CUTOFF_DATE}

4. CONTENT FILTERING:

   DEFAULT MODE (AI-focused):
   - AI, Artificial Intelligence, Machine Learning, ML
   - Agentic AI, autonomous agents, AI workflows
   - Bedrock, Claude, Anthropic, generative AI, LLMs
   - Strands agents, Kiro, AgentCore
   - SageMaker, AI/ML services, intelligent automation
   - Computer vision, NLP, natural language processing
   - AI model training, inference, fine-tuning, embeddings

   OVERRIDE: User says "all announcements" or "broad coverage" → include all AWS news

5. DEDUPLICATION:
   - Previously processed article URLs are automatically available in session context
   - Extract all article URLs from AWS feed
   - Skip any URLs found in memory (already processed)
   - Only process NEW articles

6. INTELLIGENT RANKING:
   For each NEW article, analyze and rank by developer impact considering:
   - Service importance (Bedrock/Claude > SageMaker > other AI services)
   - Availability status (GA > Public Preview > Limited Preview)
   - Developer impact (new capabilities > improvements > bug fixes)
   - Breadth of use cases (general-purpose > niche)
   - Innovation level (breakthrough features > incremental updates)

   Order articles from HIGHEST to LOWEST developer impact.

7. NEWSLETTER GENERATION:
   - If NO new articles: Send "Nothing new today" version
   - If new articles: Create formatted newsletter with ranked announcements
   - Generate intelligent TLDR highlighting key themes/trends
   - Create concise subject line capturing main theme

8. Send email via publish_message tool to: {SNS_TOPIC_ARN}

9. List processed article URLs in your response (for automatic memory extraction)

═══════════════════════════════════════════════════════════════
NEWSLETTER FORMAT
═══════════════════════════════════════════════════════════════

**SUBJECT LINE:**
[AWS-AI-NEWS] [Concise theme/trend from today's announcements]

Examples:
- "[AWS-AI-NEWS] Bedrock Agents Get Multi-Agent Orchestration"
- "[AWS-AI-NEWS] 3 Major AI Service Updates: Bedrock, SageMaker, Q"
- "[AWS-AI-NEWS] Claude 3.7 Sonnet Now Available in Bedrock"

If user requested all announcements: Use [AWS-NEWS] instead

**MESSAGE BODY:**
```
═══════════════════════════════════════════════════════════════
🌟 AWS AI/ML NEWSLETTER | [FULL DATE] 🌟
═══════════════════════════════════════════════════════════════

📰 TL;DR
───────────────────────────────────────────────────────────────
[2-4 sentences synthesizing key themes, trends, or patterns across today's announcements. Focus on the "so what" - why these updates matter to AI/ML developers.]

═══════════════════════════════════════════════════════════════
🎯 TODAY'S ANNOUNCEMENTS (Ranked by Developer Impact)
═══════════════════════════════════════════════════════════════

1. **[ANNOUNCEMENT TITLE]** | [ANNOUNCEMENT DATE]
   🔗 [FULL BLOG POST URL]

   [2-3 sentence summary covering:
   - What was announced/updated
   - Key capabilities or improvements
   - Why this matters for AI/ML developers]

2. **[NEXT ANNOUNCEMENT]** | [DATE]
   🔗 [URL]

   [Summary...]

[Continue for all announcements, numbered in descending priority order...]

═══════════════════════════════════════════════════════════════
📧 Stay Connected
───────────────────────────────────────────────────────────────
Questions? Visit aws.amazon.com
🔔 Subscribe to AWS What's New: aws.amazon.com/new/

Generated on [TODAY'S DATE]
© 2025 Amazon Web Services, Inc.
═══════════════════════════════════════════════════════════════
```

**NO NEW ANNOUNCEMENTS VERSION:**
```
═══════════════════════════════════════════════════════════════
🌟 AWS AI/ML NEWSLETTER | [FULL DATE] 🌟
═══════════════════════════════════════════════════════════════

📰 TL;DR
───────────────────────────────────────────────────────────────
No new AWS AI/ML announcements today. Check back tomorrow for the latest updates!

═══════════════════════════════════════════════════════════════
📧 Stay Connected
───────────────────────────────────────────────────────────────
Questions? Visit aws.amazon.com
🔔 Subscribe to AWS What's New: aws.amazon.com/new/

Generated on [TODAY'S DATE]
© 2025 Amazon Web Services, Inc.
═══════════════════════════════════════════════════════════════
```

═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════

✓ DEFAULT: AI/ML content only (unless user asks for "all announcements")
✓ LISTEN to user's time frame specification
✓ RANK announcements by developer impact (most important first)
✓ Include actual announcement date from AWS (not today's date)
✓ Include full blog post URLs
✓ Generate intelligent TLDR synthesizing themes/trends
✓ Create concise, informative subject line capturing main theme
✓ Use [AWS-AI-NEWS] for AI-focused, [AWS-NEWS] for broad coverage
✓ Only include NEW articles (skip duplicates from memory)
✓ If zero new announcements, send "No new announcements" version
✓ Focus summaries on AI/ML implications and developer value
✓ Always use exact ASCII border style shown above
✓ List processed article URLs in response for memory tracking

═══════════════════════════════════════════════════════════════
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

        # Get region from environment, default to us-west-2
        region = os.getenv("AWS_REGION", "us-west-2")

        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name=region
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
