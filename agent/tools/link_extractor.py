"""
Link Extractor - Simple regex-based tool to extract documentation and GitHub links from a page.

This is a lightweight tool (no LLM) for quick extraction from announcement pages.
"""
from strands import tool
import requests
import re
from urllib.parse import urlparse


# Patterns for links we care about
DOCS_PATTERNS = [
    r'https?://docs\.aws\.amazon\.com[^\s"\'<>]*',
    r'https?://aws\.amazon\.com/documentation[^\s"\'<>]*',
]

GITHUB_PATTERNS = [
    r'https?://github\.com/aws/[^\s"\'<>]*',           # GitHub repos (aws)
    r'https?://github\.com/awslabs/[^\s"\'<>]*',       # GitHub repos (awslabs)
    r'https?://github\.com/amazon/[^\s"\'<>]*',        # GitHub repos (amazon)
    r'https?://github\.com/aws-samples/[^\s"\'<>]*',   # GitHub repos (aws-samples)
    r'https?://awslabs\.github\.io[^\s"\'<>]*',        # GitHub Pages (awslabs)
    r'https?://aws\.github\.io[^\s"\'<>]*',            # GitHub Pages (aws)
]

BLOG_PATTERNS = [
    r'https?://aws\.amazon\.com/blogs/[^\s"\'<>]*',
]

# URLs we're allowed to fetch
ALLOWED_DOMAINS = [
    "aws.amazon.com",
    "docs.aws.amazon.com",
]


def is_allowed_url(url: str) -> bool:
    """Check if URL is in our allowed domains."""
    try:
        parsed = urlparse(url)
        return any(parsed.netloc == domain or parsed.netloc.endswith(f".{domain}")
                   for domain in ALLOWED_DOMAINS)
    except Exception:
        return False


def clean_url(url: str) -> str:
    """Clean up extracted URL (remove trailing punctuation, escaped chars, etc.)."""
    # Remove trailing punctuation
    url = re.sub(r'[.,;:!?\'")\]}>\\]+$', '', url)
    # Remove escaped characters like \u003d
    url = re.sub(r'\\u[0-9a-fA-F]{4}.*$', '', url)
    # Remove trailing backslashes
    url = url.rstrip('\\')
    return url


def is_useful_url(url: str) -> bool:
    """Filter out generic navigation links that aren't useful."""
    # Skip generic nav links with tracking params
    if '?nc2' in url:
        return False
    # Skip root domain links
    if url.rstrip('/') in ['https://docs.aws.amazon.com', 'https://aws.amazon.com/blogs']:
        return False
    return True


def extract_urls_by_pattern(html: str, patterns: list[str]) -> list[str]:
    """Extract unique URLs matching any of the given patterns."""
    urls = set()
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            cleaned = clean_url(match)
            if cleaned and is_useful_url(cleaned):
                urls.add(cleaned)
    return sorted(urls)


@tool
def extract_links_from_page(url: str) -> str:
    """
    Extract documentation and GitHub links from an AWS announcement or blog page.

    This tool fetches the page content and uses regex to find:
    - AWS Documentation links (docs.aws.amazon.com)
    - GitHub repository links (github.com/aws*, github.com/awslabs*)
    - Blog post links (aws.amazon.com/blogs/*)

    Args:
        url: The AWS announcement or page URL to extract links from.

    Returns:
        Extracted links categorized by type, or an error message if the fetch fails.
    """
    if not is_allowed_url(url):
        return f"❌ URL not allowed: {url}. Only AWS domains are permitted."

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
        html = response.text

        # Extract links by category
        docs_links = extract_urls_by_pattern(html, DOCS_PATTERNS)
        github_links = extract_urls_by_pattern(html, GITHUB_PATTERNS)
        blog_links = extract_urls_by_pattern(html, BLOG_PATTERNS)

        # Filter out the source URL from blog links
        blog_links = [link for link in blog_links if link != url]

        # Format as readable output
        output_lines = [f"✅ Extracted links from: {url}", ""]

        if docs_links:
            output_lines.append("📚 Documentation:")
            for link in docs_links[:5]:
                output_lines.append(f"   - {link}")

        if github_links:
            output_lines.append("💻 GitHub:")
            for link in github_links[:5]:
                output_lines.append(f"   - {link}")

        if blog_links:
            output_lines.append("📝 Related Blogs:")
            for link in blog_links[:3]:
                output_lines.append(f"   - {link}")

        if not docs_links and not github_links and not blog_links:
            output_lines.append("ℹ️ No documentation, GitHub, or blog links found on this page.")

        return "\n".join(output_lines)

    except requests.RequestException as e:
        return f"❌ Failed to fetch page: {str(e)}"
    except Exception as e:
        return f"❌ Error extracting links: {str(e)}"
