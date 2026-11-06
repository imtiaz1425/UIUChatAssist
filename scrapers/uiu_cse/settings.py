"""
Scrapy Settings Configuration

This file configures Scrapy behavior:
- Bot settings (user agent, delays)
- Middleware and pipelines
- Data output settings
"""

# Bot name
BOT_NAME = 'uiu_cse_crawler'

# Spider modules
SPIDER_MODULES = ['uiu_cse.spiders']
NEWSPIDER_MODULE = 'uiu_cse.spiders'

# User agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Download delay (seconds between requests)
DOWNLOAD_DELAY = 1

# Concurrent requests
CONCURRENT_REQUESTS = 8

# Concurrent requests per domain
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Timeout for requests (seconds)
DOWNLOAD_TIMEOUT = 30

# Retry settings
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408]

# Disable cookies (not needed for static content crawling)
COOKIES_ENABLED = False

# Pipeline settings - process and save data
ITEM_PIPELINES = {
    'uiu_cse.pipelines.CSEDataPipeline': 300,
}

# Logging settings
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'

# Memory limit (auto drop items if memory usage exceeds this)
MEMDEBUG_ENABLED = False
