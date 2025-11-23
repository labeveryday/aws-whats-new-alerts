"""
Restricted AWS news fetching tool - only allows access to AWS What's New feed.

This tool replaces the general-purpose http_request tool with a security-restricted
version that can ONLY access the AWS What's New RSS feed. This prevents the agent
from accessing arbitrary URLs on the internet.
"""
from strands import tool
import requests
from typing import Any

# Whitelist of allowed URLs - ONLY AWS What's New feed
ALLOWED_URLS = [
    "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    "https://aws.amazon.com/new/",
]


@tool
def fetch_aws_news() -> str:
    """
    Fetch latest AWS announcements from the official AWS What's New RSS feed.

    This tool is restricted to only access the AWS What's New feed for security.
    No other URLs can be accessed through this tool.

    Returns:
        XML/RSS feed content with latest AWS announcements including:
        - Article titles
        - Publication dates
        - Article URLs
        - Brief descriptions

    Example usage:
        Call this tool to get the latest AWS announcements, then parse the XML/RSS
        content to extract individual articles.
    """
    url = ALLOWED_URLS[0]  # Use the RSS feed

    try:
        # Make direct HTTP request
        response = requests.get(
            url,
            headers={
                "User-Agent": "AWS-Newsletter-Agent/1.0",
                "Accept": "application/rss+xml, application/xml, text/xml"
            },
            verify=True,
            timeout=30
        )
        
        response.raise_for_status()  # Raise exception for bad status codes
        
        return f"✅ Successfully fetched AWS What's New feed\n\nStatus Code: {response.status_code}\nBody: {response.text}"

    except requests.RequestException as e:
        return f"❌ Failed to fetch AWS news: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error fetching AWS news: {str(e)}"


@tool
def get_allowed_urls() -> str:
    """
    Get the list of URLs that this agent is allowed to access.

    Returns:
        List of whitelisted URLs for transparency
    """
    return f"This agent can only access the following URLs:\n" + "\n".join(f"- {url}" for url in ALLOWED_URLS)
