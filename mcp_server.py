"""
FastMCP Server with domain-specific search and web scraping tools
"""

import logging
import asyncio
import os
from typing import List, Optional

from fastmcp import FastMCP
from dotenv import load_dotenv

# Import the core functionality from existing tools
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(
    name="QAAgentMCPServer",
    instructions="""
    This server provides domain-specific search and web scraping tools for Q&A agents.
    Use search_documentation for fast searches across specific domains.
    Use scrape_website for comprehensive page content extraction when search is insufficient.
    """
)

class ServerClients:
    """Encapsulates all server clients and configuration"""
    
    def __init__(self):
        self.config = {
            "google_api_key": os.getenv("GOOGLE_API_KEY"),
            "tavily_api_key": os.getenv("TAVILY_API_KEY"),
            "max_results": int(os.getenv("MAX_RESULTS", "10")),
            "search_depth": os.getenv("SEARCH_DEPTH", "basic"),
            "max_content_size": int(os.getenv("MAX_CONTENT_SIZE", "10000")),
            "max_scrape_length": int(os.getenv("MAX_SCRAPE_LENGTH", "20000")),
            "enable_search_summarization": os.getenv("ENABLE_SEARCH_SUMMARIZATION", "false").lower() == "true"
        }
        
        self.tavily_client = None
        self.summarizer_llm = None
        
        # Initialize clients immediately
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Tavily client and summarizer LLM"""
        if not self.config["tavily_api_key"]:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        
        self.tavily_client = TavilyClient(api_key=self.config["tavily_api_key"])
        logger.info("🔍 Tavily client initialized")
        
        if self.config["enable_search_summarization"] and self.config["google_api_key"]:
            self.summarizer_llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-lite",
                temperature=0.1,
                max_tokens=1000,
                google_api_key=self.config["google_api_key"],
            )
            logger.info("🧠 Search result summarization enabled with Gemini Flash-Lite")
        else:
            logger.info("📝 Search result summarization disabled")

# Initialize server clients on module load
try:
    server_clients = ServerClients()
    logger.info("✅ MCP Server clients initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize MCP server clients: {e}")
    raise

# Helper functions
def get_default_tags() -> List[str]:
    """Get default HTML tags for web scraping"""
    return ["p", "li", "div", "a", "span", "h1", "h2", "h3", "h4", "h5", "h6"]

def format_search_results(results: List[dict], max_content_size: int) -> List[str]:
    """Format search results into readable strings"""
    formatted_results = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "No URL")
        content = result.get("content", "No content available")

        logger.info(f"📄 Processing result {i}: {title[:50]}...")

        if len(content) > max_content_size:
            content = content[:max_content_size] + "..."

        formatted_result = f"""
Result {i}:
Title: {title}
URL: {url}
Content: {content}
---
"""
        formatted_results.append(formatted_result)

    return formatted_results

def create_summary_prompt(search_results: str, original_query: str) -> str:
    """Create prompt for result summarization"""
    return f"""
You are a technical documentation summarizer. Your job is to extract and summarize only the most relevant information from search results.

Original User Query: "{original_query}"

Search Results to Summarize:
{search_results}

Instructions:
1. Focus ONLY on information directly relevant to answering the user's query
2. Remove redundant content, boilerplate text, and navigation elements  
3. Preserve specific technical details, code examples, and step-by-step instructions
4. Maintain source URLs for attribution
5. Keep the summary comprehensive but concise
6. Format clearly for easy reading

Relevant Summary:
"""

@mcp.tool
async def search_documentation(
    query: str,
    sites: List[str],
    max_results: Optional[int] = None,
    depth: Optional[str] = None
) -> str:
    """Search documentation websites using Tavily web search.

    Args:
        query: Search query with relevant keywords - what you want to find
        sites: Website domains to search within (e.g., ['docs.langchain.com', 'fastapi.tiangolo.com'])
        max_results: Maximum number of search results to return (default: 10)
        depth: Search depth - 'basic' for quick searches or 'advanced' for comprehensive searches (default: 'basic')

    Usage Guidelines:
    1. Create keyword-rich search query from user's question
    2. Select relevant website domains based on technologies mentioned
    3. Use 'basic' depth for quick answers, 'advanced' for thorough research
    4. Adjust max_results based on how comprehensive you need the answer to be

    Examples:
    - Quick search: query="LangChain custom tools", sites=["docs.langchain.com"], depth="basic", max_results=5
    - Comprehensive search: query="FastAPI authentication middleware", sites=["fastapi.tiangolo.com"], depth="advanced", max_results=15

    Best Practices:
    - Include technical terms and framework names in queries
    - Choose appropriate domains for the question context
    - Prefer official documentation sites over third-party sources
    - Use specific queries rather than broad terms for better results
    """
    try:
        final_max_results = max_results or server_clients.config["max_results"]
        final_depth = depth or server_clients.config["search_depth"]

        logger.info(f"🔍 Searching: '{query}' on sites: {sites}")
        logger.info(f"📊 Parameters: max_results={final_max_results}, depth={final_depth}")

        # Execute search
        search_results = await asyncio.to_thread(
            server_clients.tavily_client.search,
            query=query,
            max_results=final_max_results,
            search_depth=final_depth,
            include_domains=sites,
        )

        logger.info(f"📥 Received {len(search_results.get('results', []))} results")

        if not search_results.get("results"):
            logger.warning("⚠️ No search results returned")
            return "No results found. Try a different search query or check if domains are accessible."

        formatted_results = format_search_results(
            search_results["results"][:final_max_results], server_clients.config["max_content_size"]
        )
        final_result = "\n".join(formatted_results)

        logger.info(f"✅ Processed {len(search_results['results'])} results, returning {len(final_result)} characters")

        # Summarize if enabled
        if server_clients.config["enable_search_summarization"] and server_clients.summarizer_llm:
            try:
                logger.info("🧠 Summarizing results...")
                prompt = create_summary_prompt(final_result, query)
                response = await asyncio.to_thread(server_clients.summarizer_llm.invoke, prompt)
                summarized_result = response.content
                reduction = round((1 - len(summarized_result) / len(final_result)) * 100)
                logger.info(f"📊 Summarization: {len(final_result)} → {len(summarized_result)} chars ({reduction}% reduction)")
                return summarized_result
            except Exception as e:
                logger.error(f"❌ Summarization failed: {e}. Returning original results.")

        return final_result

    except Exception as e:
        error_msg = f"❌ Search error: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool
async def scrape_website(
    url: str,
    tags_to_extract: Optional[List[str]] = None
) -> str:
    """Scrape complete website content using Chromium browser for comprehensive page extraction.

    Args:
        url: Complete URL to scrape (must include https:// or http://)
        tags_to_extract: HTML tags to extract content from 
            Default: ["p", "li", "div", "a", "span", "h1", "h2", "h3", "h4", "h5", "h6"]
            Custom examples: ["pre", "code"] for code examples, ["table", "tr", "td"] for tables

    When to Use:
    - Search results are incomplete or insufficient
    - Need complete page content including code examples
    - Page has dynamic JavaScript content that search missed
    - Need specific formatting or structure that search doesn't capture

    Examples:
    - Basic scraping: url="https://docs.langchain.com/docs/modules/agents"
    - Code-focused scraping: url="https://fastapi.tiangolo.com/tutorial/", tags_to_extract=["pre", "code", "p"]
    - Table extraction: url="https://docs.python.org/3/library/", tags_to_extract=["table", "tr", "td", "th"]

    Best Practices:
    - Only use after search_documentation provides insufficient information
    - Prefer URLs from previous search results for relevance
    - Use specific tag extraction for targeted content (faster processing)
    - Be aware: ~3-10x slower than search, use sparingly for performance

    Limitations:
    - Content truncated at configured limit to prevent excessive token usage
    - Some sites may block automated scraping
    - Slower than search - reserve for when search is inadequate
    """
    try:
        if tags_to_extract is None:
            tags_to_extract = get_default_tags()

        logger.info(f"🌐 Scraping: {url}")
        logger.info(f"🏷️ Tags to extract: {tags_to_extract}")

        loader = AsyncChromiumLoader([url])
        html_docs = await asyncio.to_thread(loader.load)

        if not html_docs:
            return f"Failed to load content from {url}"

        bs_transformer = BeautifulSoupTransformer()
        docs_transformed = await asyncio.to_thread(
            bs_transformer.transform_documents,
            html_docs,
            tags_to_extract=tags_to_extract,
        )

        if not docs_transformed:
            return f"No content extracted from {url}"

        content = docs_transformed[0].page_content

        if len(content) > server_clients.config["max_scrape_length"]:
            content = content[:server_clients.config["max_scrape_length"]] + "\n\n... (content truncated)"

        logger.info(f"✅ Scraped {len(content)} characters from {url}")

        return f"""
**Website Scraped:** {url}
**Content Extracted:**

{content}

**Note:** Complete website content for comprehensive analysis.
"""

    except Exception as e:
        error_msg = f"Web scraping error for {url}: {str(e)}"
        logger.error(error_msg)
        return error_msg

if __name__ == "__main__":
    try:
        # Get host and port from environment variables with defaults
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8001"))
        
        logger.info(f"🚀 Starting QA Agent MCP Server on {host}:{port}...")
        # Use streamable-http transport by default for better integration
        mcp.run(transport="streamable-http", host=host, port=port)
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        raise
