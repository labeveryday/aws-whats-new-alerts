"""
AWS Daily Newsletter Agent
Creates daily email newsletters in professional format with numbered announcements
"""
import os
import sys
import json
import logging
import uuid

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

# Third-party imports
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands import Agent
from strands_tools import current_time

# Local imports
from secrets_loader import load_secrets

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Ensure logs are flushed immediately
os.environ["PYTHONUNBUFFERED"] = "1"

# Load configuration from AWS Secrets Manager (if configured)
# Pass SECRET_NAME via: agentcore launch --env SECRET_NAME=your-secret-name
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
SECRET_NAME = os.getenv("SECRET_NAME")

if SECRET_NAME:
    logger.info(f"Loading configuration from secret: {SECRET_NAME} in {AWS_REGION}")
    load_secrets(SECRET_NAME, AWS_REGION)
else:
    logger.info("SECRET_NAME not set, skipping Secrets Manager load (using environment variables directly)")

# Configuration
AWS_URL = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
CUTOFF_DATE = "2022-10-01"

# Agent Identity Configuration
ACTOR_ID = os.getenv("AGENT_ACTOR_ID", "aws_newsletter_bot")
# Use a random session ID by default to prevent stuck tool states during development/demo
# For production, you'd want to persist this for user continuity
SESSION_ID = os.getenv("AGENT_SESSION_ID", str(uuid.uuid4()))
AGENT_NAME = os.getenv("AGENT_NAME", "aws_newsletter_bot")

# Print configuration for verification (exclude sensitive keys if any)
logger.info(f"Configuration Loaded: SNS_TOPIC_ARN={SNS_TOPIC_ARN}, MEMORY_ID={MEMORY_ID}")

SYSTEM_PROMPT = f"""
You are an AWS Newsletter Agent that creates professional daily email newsletters about AWS announcements.

CORE MISSION: Generate intelligent, ranked newsletters focused on **Agentic AI** and AI/ML-related AWS announcements.

SELF-DISCOVERY & SCHEDULING:
You are an autonomous agent. If the user asks you to schedule yourself or create a recurring task:
1. **CHECK IDENTITY**: You likely do not know your own `AgentRuntimeArn` yet.
2. **DISCOVER**: Call `find_agent_id(agent_name="{AGENT_NAME}")` to retrieve it.
3. **ACT**: Use the discovered ARN to call `manage_eventbridge_schedule`.

════════════════════════════════════════════════
WORKFLOW
════════════════════════════════════════════════

1. Use current_time tool to get today's date

2. Use fetch_aws_news tool to fetch latest news from {AWS_URL}

3. RESPECT USER'S TIME FRAME:
   - "last week" or "7 days" → process last 7 days
   - "last month" → process last 30 days
   - "yesterday" → process last 24 hours
   - "last 3 days" → process last 3 days
   - DEFAULT (no time specified): last 24 hours
   - Always filter: Only articles published >= {CUTOFF_DATE}

4. CONTENT FILTERING:

   **PRIMARY FOCUS (Rank Highest): Agentic AI**
   - **AgentCore**, Amazon Bedrock AgentCore
   - **Strands**, Strands Agents, AI Agents
   - **Kiro**
   - **MCP** (Model Context Protocol)
   - **A2A** (Agent-to-Agent)
   - **Claude** (Claude 3.5, Claude 3.7, etc.)
   - **Multi-Agent** Systems

   **SECONDARY FOCUS: General AI/ML**
   - Bedrock (general features), SageMaker
   - Generative AI, LLMs, Foundation Models
   - Computer Vision, NLP
   - Training, Inference, Fine-tuning

   OVERRIDE: User says "all announcements" or "broad coverage" → include all AWS news

5. DEDUPLICATION:
   - Previously processed article URLs are automatically available in session context
   - Extract all article URLs from AWS feed
   - Skip any URLs found in memory (already processed)
   - Only process NEW articles

6. INTELLIGENT RANKING:
   For each NEW article, analyze and rank by developer impact considering:
   - **Topic Priority**: **Agentic AI** (AgentCore, Strands, MCP) > **Core AI** (Bedrock/Claude) > **Other AI/ML** (SageMaker)
   - Availability status (GA > Public Preview > Limited Preview)
   - Developer impact (new capabilities > improvements > bug fixes)
   - Innovation level (breakthrough features > incremental updates)

   Order articles from HIGHEST to LOWEST developer impact.

7. NEWSLETTER GENERATION:
   - If NO new articles: Send "Nothing new today" version
   - If new articles: Create formatted newsletter with ranked announcements
   - Generate intelligent TLDR highlighting key themes/trends (especially Agentic AI)
   - Create concise subject line capturing main theme

8. Send email via publish_message tool to: {SNS_TOPIC_ARN}

9. List processed article URLs in your response (for automatic memory extraction)

════════════════════════════════════════════════
NEWSLETTER FORMAT
════════════════════════════════════════════════

**SUBJECT LINE:**
[AWS-AI-NEWS] [Concise theme/trend from today's announcements]

Examples:
- "[AWS-AI-NEWS] Bedrock Agents Get Multi-Agent Orchestration"
- "[AWS-AI-NEWS] 3 Major Agentic Updates: AgentCore, Strands, MCP"
- "[AWS-AI-NEWS] Claude 3.7 Sonnet Now Available in Bedrock"
- "[AWS-AI-NEWS] Strands Agents Now Supports Fine-Tuning Models"
- "[AWS-AI-NEWS] Amazon Bedrock AgentCore Now supports MCP (Model Context Protocol)"

If user requested all announcements: Use [AWS-NEWS] instead

**MESSAGE BODY:**
```
════════════════════════════════════════
🌟 AWS AGENTIC & AI/ML NEWSLETTER | [FULL DATE] 🌟
════════════════════════════════════════

📰 TL;DR
────────────────────────────────────────────────
[2-4 sentences synthesizing key themes, trends, or patterns across today's announcements. Highlight Agentic AI updates first.]

════════════════════════════════════════════════
🎯 TODAY'S ANNOUNCEMENTS (Ranked by Developer Impact)
════════════════════════════════════════════════

1. **[ANNOUNCEMENT TITLE]** | [ANNOUNCEMENT DATE]

   [2-3 sentence summary covering:
   - What was announced/updated
   - Key capabilities or improvements
   - Why this matters for Agentic AI or ML developers]

   🔗 [FULL BLOG POST URL]

2. **[NEXT ANNOUNCEMENT]** | [DATE]

   [Summary...]
   
   🔗 [URL]

[Continue for all announcements, numbered in descending priority order...]

════════════════════════════════════════════════
📧 Stay Connected
────────────────────────────────────────────────
Questions? Visit aws.amazon.com
🔔 Subscribe to AWS What's New: aws.amazon.com/new/

Generated on [TODAY'S DATE]
© 2025 Amazon Web Services, Inc.
════════════════════════════════════════════════
```

**NO NEW ANNOUNCEMENTS VERSION:**
```
════════════════════════════════════════════════
🌟 AWS AGENTIC & AI/ML NEWSLETTER | [FULL DATE] 🌟
════════════════════════════════════════════════

📰 TL;DR
────────────────────────────────────────────────
No new AWS Agentic or AI/ML announcements today. Check back tomorrow for the latest updates!

════════════════════════════════════════════════
📧 Stay Connected
────────────────────────────────────────────────
Questions? Visit aws.amazon.com
🔔 Subscribe to AWS What's New: aws.amazon.com/new/

Generated on [TODAY'S DATE]
© 2025 Amazon Web Services, Inc.
════════════════════════════════════════════════
```

════════════════════════════════════════════════
CRITICAL RULES
════════════════════════════════════════════════

✓ DEFAULT: **Agentic AI** & AI/ML content only (unless user asks for "all announcements")
✓ **PRIORITIZE**: AgentCore, Strands, MCP, Kiro, A2A updates ABOVE general ML
✓ LISTEN to user's time frame specification
✓ RANK announcements by developer impact (most important first)
✓ Include actual announcement date from AWS (not today's date)
✓ Include full blog post URLs
✓ Generate intelligent TLDR synthesizing themes/trends
✓ Create concise, informative subject line capturing main theme
✓ Use [AWS-AI-NEWS] for AI-focused, [AWS-NEWS] for broad coverage
✓ Only include NEW articles (skip duplicates from memory)
✓ If zero new announcements, send "No new announcements" version
✓ Focus summaries on Agentic AI implications and developer value
✓ Always use exact ASCII border style shown above
✓ List processed article URLs in response for memory tracking

════════════════════════════════════════════════
NOTE: Never share ARN or other sensitive information in your response.
════════════════════════════════════════════════
"""

# Instantiate Bedrock AgentCore
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke_agent(payload, context):
    """
    Handler for daily newsletter generation with proper memory integration.
    Creates a new agent instance per invocation (no lazy loading with memory).
    Supports direct invocation and streaming response.
    """
    if not MEMORY_ID:
        raise ValueError("Memory not configured. Set BEDROCK_AGENTCORE_MEMORY_ID environment variable.")

    try:
        # Handle payload parsing (Robust handling like AWS Samples)
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        prompt = None
        if isinstance(payload, dict):
            if "input" in payload and isinstance(payload["input"], dict):
                prompt = payload["input"].get("prompt")
            else:
                prompt = payload.get("prompt")
        
        if not prompt:
            prompt = "Generate daily AWS AI/ML newsletter for the last 24 hours"
            logger.info("No prompt found in payload, using default.")

        logger.info(f"Received prompt: {prompt}")

        # Use consistent actor and session IDs for persistent memory
        actor_id = ACTOR_ID
        # Force random session ID to avoid ValidationException from stuck tool states
        # This ensures every request starts with a clean slate for the demo
        session_id = str(uuid.uuid4())

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

        conversation_manager = SlidingWindowConversationManager(
            should_truncate_results=True,
            window_size=40,
        )

        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[current_time],
            load_tools_from_directory=True,  # Loads aws_news_tools.py and sns_tools.py automatically,
            #session_manager=session_manager,
            conversation_manager=conversation_manager
        )

        # CRITICAL: Stream the response
        # This loop runs for as long as needed - no timeout!
        tool_active = False

        async for item in agent.stream_async(prompt):
            if "event" in item:
                event = item["event"]

                # Tool invocation started
                if "contentBlockStart" in event and \
                   "toolUse" in event["contentBlockStart"].get("start", {}):
                    tool_active = True
                    yield json.dumps({"event": event}) + "\n"

                # Tool invocation completed
                elif "contentBlockStop" in event and tool_active:
                    tool_active = False
                    yield json.dumps({"event": event}) + "\n"

            # Stream tool execution details
            elif "current_tool_use" in item and tool_active:
                yield json.dumps(item["current_tool_use"]) + "\n"

            # Stream text response chunks
            elif "data" in item:
                yield json.dumps({"data": item["data"]}) + "\n"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Global handler exception: {error_msg}", exc_info=True)
        # Return error as a dict so it's serialized cleanly
        yield json.dumps({"error": f"Agent execution failed: {error_msg}"}) + "\n"

if __name__ == "__main__":
    app.run()
