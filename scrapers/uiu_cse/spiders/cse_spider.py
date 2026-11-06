"""
UIU CSE Website Spider

This spider crawls the UIU CSE department website and extracts:
- Page titles
- Paragraph text
- Headings
- URLs

It automatically follows internal links only and avoids external websites.
"""

import scrapy
from urllib.parse import urljoin, urlparse
from typing import Optional


class CSESpider(scrapy.Spider):
    name = "cse_spider"
    allowed_domains = ["cse.uiu.ac.bd"]
    start_urls = ["https://cse.uiu.ac.bd/"]

    custom_settings = {
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ITEM_PIPELINES': {'uiu_cse.pipelines.CSEDataPipeline': 300},
    }

    visited_urls = set()

    def parse(self, response):
        if response.url in self.visited_urls:
            return

        self.visited_urls.add(response.url)
        self.logger.info(f"Crawling: {response.url}")

        page_title = self._extract_title(response)
        paragraphs = self._extract_paragraphs(response)
        headings = self._extract_headings(response)

        if any([page_title, paragraphs, headings]):
            yield {
                'url': response.url,
                'title': page_title or '',
                'headings': headings,
                'paragraphs': paragraphs,
            }

        for link in self._find_internal_links(response):
            if link not in self.visited_urls:
                yield response.follow(link, callback=self.parse, errback=self.errback)
    
    def _extract_title(self, response) -> Optional[str]:
        """
        Extract the page title
        
        Args:
            response: Scrapy response object
            
        Returns:
            Page title or None if not found
        """
        # Try to get title from <title> tag first
        title = response.xpath('//title/text()').get()
        
        # Clean up the title
        if title:
            title = title.strip()
            # Remove common suffixes like "| UIU CSE"
            if '|' in title:
                title = title.split('|')[0].strip()
        
        return title
    
    def _extract_headings(self, response) -> list:
        """
        Extract all headings from the page (H1-H6)
        
        Args:
            response: Scrapy response object
            
        Returns:
            List of heading texts
        """
        headings = []
        
        # Extract h1 through h6 tags
        for heading_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            heading_texts = response.xpath(f'//{heading_tag}/text()').getall()
            
            for text in heading_texts:
                # Clean and filter empty headings
                cleaned_text = self._clean_text(text)
                if cleaned_text and len(cleaned_text) > 2:
                    headings.append(cleaned_text)
        
        return headings
    
    def _extract_paragraphs(self, response) -> list:
        """
        Extract rich content from faculty profiles and normal pages using deep element paths.
        """
        content = []

        selectors = [
            '//p//text()',
            '//li//text()',
            '//td//text()',
            '//span//text()',
            '//div[contains(@class,"elementor-widget-container")]//text()',
            '//div[contains(@class,"entry-content")]//text()'
        ]

        for selector in selectors:
            texts = response.xpath(selector).getall()

            for text in texts:
                cleaned = self._clean_text(text)

                if cleaned and len(cleaned) > 2:
                    content.append(cleaned)

        return list(dict.fromkeys(content))
    
    def _find_internal_links(self, response) -> list:
        """
        Find all internal links on the page
        
        Args:
            response: Scrapy response object
            
        Returns:
            List of internal links (full URLs)
        """
        internal_links = []

        # Get all href attributes from <a> tags
        all_links = response.xpath('//a/@href').getall()

        # Skip common file types and non-http schemes
        skip_ext = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.zip', '.rar', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')

        for link in all_links:
            if not link:
                continue

            # Skip javascript:, mailto:, tel: links
            if any(link.startswith(s) for s in ('javascript:', 'mailto:', 'tel:')):
                continue

            absolute_url = urljoin(response.url, link)
            absolute_url = absolute_url.split('#')[0]

            # Skip non-http URLs
            parsed = urlparse(absolute_url)
            if parsed.scheme not in ('http', 'https'):
                continue

            # Skip common file extensions
            low = parsed.path.lower()
            if any(low.endswith(ext) for ext in skip_ext):
                continue

            if self._is_internal_link(absolute_url):
                if absolute_url not in internal_links:
                    internal_links.append(absolute_url)
        
        self.logger.info(f"Found {len(internal_links)} internal links on {response.url}")
        
        return internal_links
    
    def _is_internal_link(self, url: str) -> bool:
        """
        Check if a URL is internal (same domain)
        
        Args:
            url: URL to check
            
        Returns:
            True if internal, False if external
        """
        try:
            parsed_url = urlparse(url)
            parsed_domain = urlparse(self.start_urls[0])
            
            # Compare domains
            return parsed_url.netloc == parsed_domain.netloc
            
        except Exception as e:
            self.logger.warning(f"Error checking URL: {url} - {str(e)}")
            return False
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text while removing common boilerplate phrases.
        """
        text = text.strip()
        text = ' '.join(text.split())
        
        skip_texts = {
            "menu",
            "search",
            "submit",
            "home",
            "follow us",
            "news",
            "notices",
            "events",
            "about uiu",
            "departments",
            "admission",
            "important links",
            "quick links",
            "faculty members",
            "important contact",
            "apply online",
            "profile login",
            "uiu home",
            "dspace",
            "library",
            "degree verification"
        }
        
        if text.lower() in skip_texts:
            return ''
        
        return text
    
    def errback(self, failure):
        """
        Handle request errors gracefully
        
        Args:
            failure: Twisted failure object
        """
        self.logger.error(f"Request failed: {failure.request.url}")
        self.logger.error(f"Error: {failure.value}")