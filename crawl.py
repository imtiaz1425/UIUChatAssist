"""
UIU CSE Web Crawler - Main Execution Script

This script runs the Scrapy spider to crawl the UIU CSE website.

Usage:
    python crawl.py              # Run the crawler
    python crawl.py --help       # Show help

The crawler will:
1. Start from https://cse.uiu.ac.bd/
2. Follow internal links only
3. Extract titles, headings, and paragraphs
4. Save cleaned data to data/raw/cse_full_data.json
"""

import os
import sys
import logging
from pathlib import Path
import subprocess

# Get project root directory
project_root = Path(__file__).parent


def setup_logging():
    """Configure logging for the crawler"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('crawler.log', encoding='utf-8')
        ]
    )


def run_crawler():
    """
    Run the UIU CSE web crawler using Scrapy command line
    
    Steps:
    1. Change to scrapers directory
    2. Run scrapy crawl command
    3. Display results
    """
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("UIU CSE Web Crawler")
    logger.info("=" * 60)
    logger.info(f"Project Root: {project_root}")
    
    # Change to scrapers directory where Scrapy project is
    scrapers_dir = project_root / "scrapers"
    
    try:
        logger.info("Initializing Scrapy crawler...")
        logger.info("Starting spider: cse_spider")
        logger.info("Target URL: https://cse.uiu.ac.bd/")
        
        # Run Scrapy spider using command line
        logger.info("-" * 60)
        logger.info("Crawler running... (This may take several minutes)")
        logger.info("-" * 60)
        
        # Change to scrapers directory and run crawler
        os.chdir(str(scrapers_dir))
        result = subprocess.run(
            [sys.executable, "-m", "scrapy", "crawl", "cse_spider"],
            capture_output=False,
            text=True
        )
        
        # Change back to project root
        os.chdir(str(project_root))
        
        # Check output file
        output_file = project_root / "data" / "raw" / "cse_full_data.json"
        
        if output_file.exists():
            file_size = output_file.stat().st_size
            logger.info("-" * 60)
            logger.info("Crawler completed successfully!")
            logger.info(f"Output file: {output_file}")
            logger.info(f"File size: {file_size / 1024:.2f} KB")
            logger.info("-" * 60)
        else:
            logger.warning("Output file not found. Check crawler logs for details.")
        
        return result.returncode
        
    except Exception as e:
        logger.error(f"Error running crawler: {str(e)}")
        raise


def main():
    """Main entry point"""
    
    # Run the crawler
    return_code = run_crawler()
    sys.exit(return_code)


if __name__ == "__main__":
    main()