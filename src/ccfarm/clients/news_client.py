import os
import json
from typing import Dict, List, Optional
from common.utils import get_flow_aware_logger
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import trafilatura
from bs4 import BeautifulSoup

logger = get_flow_aware_logger("news-client")
CURDIR = os.path.dirname(os.path.realpath(__file__))
    
class NewsAPIClient:
    """Low-level client for interacting with NewsAPI"""
    with open(os.path.join(CURDIR, "skip_domains.json")) as f:
        DEFAULT_SKIP_DOMAINS = json.load(f)
    BASE_URL = "https://newsapi.org/v2"
    
    def __init__(
        self, 
        api_key: str,
        rate_limit: int = 100,
        skip_domains: Optional[List[str]] = None
    ):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.skip_domains = skip_domains if skip_domains else self.DEFAULT_SKIP_DOMAINS
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'User-Agent': 'AINewsBot/1.0'
        })
        self._setup_rate_limiter()

    def _setup_rate_limiter(self):
        """Initialize rate limiter for the session"""
        self._rate_limiter = NewsAPIRateLimiter(rate_limit=self.rate_limit)
        self.session.hooks['response'].append(self._rate_limiter)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_everything(
        self,
        query: str,
        *,
        page_size: int = 20,
        language: str = "en",
        sort_by: str = "popularity",
        exclude_domains: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict:
        params = {
            'q': query,
            'pageSize': min(page_size, 100),
            'language': language,
            'sortBy': sort_by
        }
        
        if exclude_domains:
            params['excludeDomains'] = ','.join(exclude_domains)
        elif self.skip_domains:
            params['excludeDomains'] = ','.join(self.skip_domains)
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date

        return self._make_request('everything', params)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_top_headlines(
        self,
        *,
        country: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 20
    ) -> Dict:
        params: dict[str, int|str] = {'pageSize': min(page_size, 100)}
        
        if country:
            params['country'] = country
        if category:
            params['category'] = category
        if query:
            params['q'] = query

        return self._make_request('top-headlines', params)

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make authenticated request to NewsAPI"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data: Dict = response.json()
            if data.get('status') != 'ok':
                error = data.get('message', 'Unknown error')
                raise NewsAPIError(f"API returned error: {error}")
            return data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise NewsAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise NewsAPIError(f"Invalid response format: {str(e)}")

    def fetch_article_content(self, url: str) -> Optional[str]:
        try:
            # Try to get the page content
            response = self.session.get(
                url,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            response.raise_for_status()
            
            # First try trafilatura
            content = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=False
            )
            
            # If trafilatura fails, try BeautifulSoup
            if not content:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove unwanted elements
                for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                
                # Try to find main content
                article = soup.find('article')
                if not article:
                    # Look for elements with class containing 'article' or 'content'
                    for element in soup.find_all(class_=True):
                        classes = element.get('class', [])
                        if any('article' in cls.lower() or 'content' in cls.lower() for cls in classes):
                            article = element
                            break
            else:
                print("Trafilatura worked!")
            
            return content.strip() if content else None
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None
        
class NewsAPIError(Exception):
    """Custom exception for NewsAPI errors"""
    pass

class NewsAPIRateLimiter:
    """Track and enforce NewsAPI rate limits"""
    
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self.call_count = 0
        
    def __call__(self, response: requests.Response, *args, **kwargs):
        """Called after each request to check rate limits"""
        self.call_count += 1
        
        # Check remaining requests
        remaining = int(response.headers.get('X-RateLimit-Remaining', self.rate_limit))
        if remaining < 5:
            logger.warning(f"NewsAPI rate limit approaching: {remaining} requests remaining")
            
        # Check if we hit the limit
        if remaining == 0:
            reset_time = response.headers.get('X-RateLimit-Reset')
            logger.error(f"NewsAPI rate limit exceeded. Resets at: {reset_time}")
            raise NewsAPIError("Rate limit exceeded")
