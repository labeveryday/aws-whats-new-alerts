"""
Resource Analyzer Sub-Agent - Uses a Strands Agent to intelligently extract links from AWS content.

This demonstrates the "Agents as Tools" pattern - a specialized agent wrapped as a tool
for the orchestrator to call when deeper content analysis is needed.

Triggered when the orchestrator finds:
- Blog posts (aws.amazon.com/blogs/*) - often contain GitHub repos, code samples
- GitHub Pages docs (awslabs.github.io/*, aws.github.io/*) - contain repo links, examples
"""
from strands import Agent, tool
import requests


# Allowed URL patterns for the sub-agent
ALLOWED_PATTERNS = [
    "aws.amazon.com/blogs/",      # AWS blog posts
    "awslabs.github.io/",         # GitHub Pages docs (awslabs)
    "aws.github.io/",             # GitHub Pages docs (aws)
    "github.com/aws/",            # GitHub repos (aws)
    "github.com/awslabs/",        # GitHub repos (awslabs)
    "github.com/amazon/",         # GitHub repos (amazon)
    "github.com/aws-samples/",    # GitHub repos (aws-samples)
]


RESOURCE_ANALYZER_PROMPT = """You are a link extraction specialist. Your ONLY job is to extract useful links from AWS content pages.

When given page HTML content, extract:
1. **Documentation links**: Any links to docs.aws.amazon.com
2. **GitHub repository links**: Any links to github.com/aws*, github.com/awslabs*, github.com/amazon*
3. **GitHub Pages links**: Any links to *.github.io (documentation sites)
4. **Code samples**: Links to code repositories, sample projects, or quickstart guides

RULES:
- Output ONLY the extracted links in a structured format
- Do NOT summarize the content
- Do NOT add commentary
- If no relevant links found, say "No relevant links found"

FORMAT YOUR OUTPUT EXACTLY LIKE THIS:
📚 Documentation:
- [link1]
- [link2]

💻 GitHub:
- [link1]

If a category has no links, omit that category entirely.
"""


def fetch_page_content(url: str) -> str:
    """Fetch page HTML content."""
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "AWS-Newsletter-Agent/1.0",
                "Accept": "text/html"
            },
            timeout=30
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error fetching page: {str(e)}"


def is_allowed_url(url: str) -> bool:
    """Check if URL matches allowed patterns for sub-agent analysis."""
    return any(pattern in url for pattern in ALLOWED_PATTERNS)


# Create the sub-agent (initialized once, reused)
# Uses default model (Sonnet) - no memory needed for stateless link extraction
resource_analyzer_agent = Agent(
    system_prompt=RESOURCE_ANALYZER_PROMPT,
)


@tool
def read_blog_for_links(url: str) -> str:
    """
    Use an AI sub-agent to intelligently extract documentation and GitHub links from AWS content.

    This tool fetches the page content and uses a Strands Agent to find relevant links
    that may be embedded in the text, code blocks, or referenced contextually.

    Use this when extract_links_from_page finds:
    - Blog posts (aws.amazon.com/blogs/*) - often contain GitHub repos, code samples
    - GitHub Pages docs (awslabs.github.io/*, aws.github.io/*) - contain repo links, examples

    Args:
        url: The URL to analyze (blog post or GitHub Pages docs site).

    Returns:
        Extracted documentation and GitHub links found on the page.
    """
    # Validate URL
    if not is_allowed_url(url):
        allowed = ", ".join(ALLOWED_PATTERNS)
        return f"❌ URL not allowed: {url}. Allowed patterns: {allowed}"

    # Fetch the page content
    html_content = fetch_page_content(url)
    if html_content.startswith("Error"):
        return f"❌ {html_content}"

    # Truncate HTML to avoid token limits (keep first 50k chars)
    if len(html_content) > 50000:
        html_content = html_content[:50000] + "\n... [truncated]"

    # Use the sub-agent to extract links
    try:
        prompt = f"""Extract all documentation and GitHub links from this AWS content page.

Page URL: {url}

Page HTML Content:
{html_content}

Remember: ONLY output the extracted links, no summaries or commentary."""

        result = resource_analyzer_agent(prompt)

        # Extract the text response
        response_text = str(result)

        return f"✅ Sub-agent analysis complete for: {url}\n\n{response_text}"

    except Exception as e:
        return f"❌ Error analyzing page: {str(e)}"
