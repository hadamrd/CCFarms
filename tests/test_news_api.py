from urllib.parse import urlparse
from ccfarm.clients.news_client import NewsAPIClient
from prefect.blocks.system import Secret

if __name__ == "__main__":
    api_key = Secret.load("news-api-key")
    client = NewsAPIClient(api_key)

    articles = client.get_everything(
        query="artificial intelligence",
        page_size=10,  # Get more since we'll skip some
        sort_by="popularity"
    )
    
    print("\nFound articles:")
    for idx, article in enumerate(articles.get('articles', []), 1):
        url = article.get('url', 'No URL')
        domain = urlparse(url).netloc if url != 'No URL' else 'No domain'
        print(f"{idx}. {article['title']}")
        print(f"   Source: {domain}")
        print(f"   URL: {url}")
        print()
    
    # Try articles until we successfully fetch content
    for article in articles.get('articles', []):
        url = article.get('url')
        if not url:
            continue
            
        domain = urlparse(url).netloc
        if domain in client.DEFAULT_SKIP_DOMAINS:
            print(f"Skipping {domain} (known paywall/restrictions)")
            continue
            
        print(f"\nAttempting to fetch: {article['title']}")
        content = client.fetch_article_content(url)
        if content:
            print("\nSuccessfully fetched content:")
            print("=" * 50)
            print(content[:2000] + "..." if len(content) > 500 else content)
        else:
            print(f"Failed to fetch content from {domain}, trying next article...")

