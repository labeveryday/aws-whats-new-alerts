"""
AWS Daily Newsletter Agent
Creates daily email newsletters in professional format with numbered announcements
"""
import os
import sys
import json
import logging
import uuid
import base64
from typing import Optional

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

# Third-party imports
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.memory import MemoryClient
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands import Agent
from strands_tools import current_time

# Local imports
from secrets_loader import load_secrets
from memory_hooks import LongTermMemoryHookProvider

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
AWS_REGION = os.getenv("AWS_REGION")
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
ACTOR_ID = os.getenv("AGENT_ACTOR_ID")
# Session ID for memory persistence (remembering name, preferences, etc.)
# Set via AGENT_SESSION_ID env var or Secrets Manager
SESSION_ID = os.getenv("AGENT_SESSION_ID")
AGENT_NAME = os.getenv("AGENT_NAME")

# Print configuration for verification (exclude sensitive keys if any)
logger.info(f"Configuration Loaded: SNS_TOPIC_ARN={SNS_TOPIC_ARN}, MEMORY_ID={MEMORY_ID}")

SYSTEM_PROMPT = f"""
You are an AWS Newsletter Agent that creates professional daily email newsletters about AWS announcements.

CORE MISSION: Generate intelligent, ranked newsletters focused on **Agentic AI** and AI/ML-related AWS announcements.

════════════════════════════════════════════════
PERSONALIZATION & MEMORY
════════════════════════════════════════════════

Your messages may include a `=== MEMORY CONTEXT ===` section with information from previous conversations.

- If you see user information (like their name), address them personally
- If the user tells you their name, remember it for future conversations
- Be warm and personable - greet returning users by name
- If no name is found, you can ask for it naturally during conversation

SELF-DISCOVERY & SCHEDULING:
You are an autonomous agent. If the user asks you to schedule yourself or create a recurring task:
1. **CHECK IDENTITY**: You likely do not know your own `AgentRuntimeArn` yet.
2. **DISCOVER**: Call `find_agent_id(agent_name="{AGENT_NAME}")` to retrieve it.
3. **ACT**: Use the discovered ARN to call `manage_eventbridge_schedule`.

════════════════════════════════════════════════
WORKFLOW
════════════════════════════════════════════════

**IMPORTANT: DISTINGUISH BETWEEN BROWSING vs PUBLISHING**

- "What's new?" / "Any news today?" / "Show me updates" → BROWSE ONLY (do NOT send email)
- "Generate a newsletter" / "Send newsletter" / "Email me" / "Publish" → FULL WORKFLOW (send email)

════════════════════════════════════════════════
BROWSE MODE (No email - just show information)
════════════════════════════════════════════════

When user asks to SEE news (not send):
1. Use current_time tool to get today's date
2. Use fetch_aws_news tool to fetch latest news from {AWS_URL}
3. Filter and rank the content (see filtering rules below)
4. Present a summary in chat - DO NOT send email
5. DO NOT call extract_links_from_page or read_blog_for_links (save resources for publishing)
6. Ask if they'd like you to send it as a newsletter (deep link extraction happens then)

════════════════════════════════════════════════
PUBLISH MODE (Full newsletter workflow)
════════════════════════════════════════════════

When user explicitly asks to GENERATE/SEND/PUBLISH a newsletter:

1. Use current_time tool to get today's date

2. Use fetch_aws_news tool to fetch latest news from {AWS_URL}

3. RESPECT USER'S TIME FRAME:
   - "last week" or "7 days" → process last 7 days
   - "last month" → process last 30 days
   - "yesterday" → process last 24 hours
   - "last 3 days" → process last 3 days
   - DEFAULT (no time specified): last 24 hours
   - Always filter: Only articles published >= {CUTOFF_DATE}

4. CONTENT FILTERING (applies to both modes):

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

7. ENHANCE ANNOUNCEMENTS (Multi-Agent Pattern):
   For each relevant announcement, extract additional resources:

   a. Call `extract_links_from_page` with the announcement URL
      → Returns: documentation links, GitHub links, blog links

   b. If blog posts or github.io pages are found, call `read_blog_for_links` on them
      → The sub-agent extracts valuable GitHub repos and code samples that regex missed

   c. Combine all extracted links (from regex tool + sub-agent) in the newsletter entry

8. NEWSLETTER GENERATION:
   - If NO new articles: Send "Nothing new today" version
   - If new articles: Create formatted newsletter with ranked announcements
   - Generate intelligent TLDR highlighting key themes/trends (especially Agentic AI)
   - Create concise subject line capturing main theme

9. Send email via the `publish_to_newsletter_topic` tool with:
   - subject: Your email subject line
   - message: Your newsletter content

10. CONFIRM DELIVERY with explicit details for memory tracking:
    - "Newsletter sent on [FULL DATE AND TIME IN EST/EDT]" - ALWAYS use Eastern Time, never UTC
    - Example: "Newsletter sent on November 27, 2025 at 3:45 PM EST"
    - Subject line used
    - Number of articles included
    - Recipient email address

11. List processed article URLs in your response (for automatic memory extraction)

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

   🔗 Announcement: [FULL ANNOUNCEMENT URL]
   📚 Docs: [DOCUMENTATION URL if found]
   💻 GitHub: [GITHUB REPO URL if found]

2. **[NEXT ANNOUNCEMENT]** | [DATE]

   [Summary...]

   🔗 Announcement: [URL]
   📚 Docs: [if found]
   💻 GitHub: [if found]

[Continue for all announcements, numbered in descending priority order...]
[Only include 📚 Docs and 💻 GitHub lines if links were actually found]

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
✓ Include full announcement URLs
✓ **ENHANCE** (PUBLISH only): Use `extract_links_from_page` and `read_blog_for_links` to find docs/GitHub links
✓ Only include 📚 Docs and 💻 GitHub lines if links were actually extracted
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

def get_user_id_from_jwt() -> Optional[str]:
    """
    Extract user ID (sub claim) from the validated JWT in the Authorization header.

    AgentCore has already validated the JWT signature before the request reaches
    this agent, so we can safely decode the payload to extract claims without
    re-validating. This provides secure per-user memory isolation.

    Returns:
        The Cognito user ID (sub claim) if present, None otherwise.
    """
    try:
        headers = BedrockAgentCoreContext.get_request_headers()
        if not headers:
            logger.debug("No request headers available in context")
            return None

        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.debug("No Bearer token in Authorization header")
            return None

        token = auth_header.split(" ")[1]

        # JWT structure: header.payload.signature
        # Decode payload (already validated by AgentCore)
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning("Invalid JWT structure")
            return None

        payload_b64 = parts[1]
        # Handle base64url encoding (replace - with +, _ with /)
        payload_b64 = payload_b64.replace("-", "+").replace("_", "/")
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)

        payload = json.loads(base64.b64decode(payload_b64))
        user_id = payload.get("sub")

        if user_id:
            logger.info(f"Extracted user ID from JWT: {user_id[:8]}...")
        return user_id

    except Exception as e:
        logger.warning(f"Failed to extract user ID from JWT: {e}")
        return None


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

        # Extract user ID from JWT for per-user memory isolation
        # AgentCore validates the JWT before the request reaches us, so the sub claim is trustworthy
        user_id = get_user_id_from_jwt()

        if user_id:
            # Per-user memory isolation: use Cognito sub as both actor and session
            # This ensures each authenticated user has their own memory namespace
            actor_id = user_id
            session_id = user_id  # Single session per user (Option 1)
            logger.info(f"User authenticated via JWT, using per-user memory: {user_id[:8]}...")
        else:
            # Fallback for CLI/EventBridge invocations (no JWT)
            # Uses static values from Secrets Manager for shared memory
            actor_id = ACTOR_ID
            session_id = SESSION_ID if SESSION_ID else str(uuid.uuid4())
            logger.info("No JWT found, using default actor/session (CLI or scheduled invocation)")

        # Initialize memory client and hooks (replaces buggy SessionManager)
        memory_client = MemoryClient(region_name=AWS_REGION)

        memory_hooks = LongTermMemoryHookProvider(
            memory_client=memory_client,
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
            top_k=50,
            relevance_score=0.7
        )

        # Larger window for more context during complex operations
        conversation_manager = SlidingWindowConversationManager(
            should_truncate_results=True,
            window_size=100,
        )

        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[current_time],
            load_tools_from_directory=True,  # Loads aws_news_tools.py, sns_tools.py, and create_events.py
            hooks=[memory_hooks],
            conversation_manager=conversation_manager
        )

        # CRITICAL: Stream the response
        # This loop runs for as long as needed - no timeout!
        tool_active = False
        current_tool_id = None

        async for item in agent.stream_async(prompt):
            if "event" in item:
                event = item["event"]

                # Tool invocation started
                if "contentBlockStart" in event and \
                   "toolUse" in event["contentBlockStart"].get("start", {}):
                    tool_active = True
                    tool_use = event["contentBlockStart"]["start"]["toolUse"]
                    current_tool_id = tool_use.get("toolUseId")
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

            # Handle message events (may contain tool_result content blocks)
            elif "message" in item:
                message = item["message"]
                if message.get("role") == "user" and "content" in message:
                    for content_block in message["content"]:
                        if content_block.get("type") == "tool_result":
                            # Stream tool result to frontend
                            tool_result = {
                                "tool_result": {
                                    "toolUseId": content_block.get("tool_use_id"),
                                    "content": content_block.get("content", "")
                                }
                            }
                            yield json.dumps(tool_result) + "\n"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Global handler exception: {error_msg}", exc_info=True)
        # Return error as a dict so it's serialized cleanly
        yield json.dumps({"error": f"Agent execution failed: {error_msg}"}) + "\n"

if __name__ == "__main__":
    app.run()
