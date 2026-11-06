"""
Minimal pipeline: collect items and write final JSON as required.
"""

import json
import os
from typing import Dict, Any, List


class CSEDataPipeline:
    def __init__(self):
        self.seen_urls = set()
        self.items: List[Dict[str, Any]] = []
        # Write output to project-root 'data/raw/cse_full_data.json'
        self.output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw', 'cse_full_data.json'))

    def open_spider(self, spider):
        self.logger = spider.logger
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        self.logger.info(f"Output will be saved to: {self.output_file}")

    def close_spider(self, spider):
        # Save items as a JSON array with required structure
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(self.items)} pages to {self.output_file}")
            print(f"Total pages scraped: {len(self.items)}")
        except Exception as e:
            self.logger.error(f"Error saving JSON: {e}")

    def process_item(self, item, spider):
        url = item.get('url')
        if not url or url in self.seen_urls:
            return item

        self.seen_urls.add(url)

        # Combine headings and paragraphs into content
        parts = []
        title = item.get('title') or ''
        if title:
            parts.append(title.strip())

        headings = item.get('headings') or []
        for h in headings:
            if h:
                parts.append(h.strip())

        paragraphs = item.get('paragraphs') or []
        for p in paragraphs:
            if p:
                parts.append(p.strip())

        NOISE_TEXTS = [
            "Follow Us",
            "About UIU",
            "Departments",
            "Admission",
            "Important Links",
            "Quick Links",
            "UIU Home",
            "DSpace",
            "Library",
            "Degree Verification",
            "Apply Online",
            "Profile Login",
            "United City, Madani Ave, Dhaka 1212"
        ]

        cleaned_parts = []

        for part in parts:
            if part.strip() not in NOISE_TEXTS:
                cleaned_parts.append(part)

        content = "\n\n".join(cleaned_parts).strip()

        record = {
            'url': url,
            'title': title.strip() if title else '',
            'content': content,
        }

        self.items.append(record)
        self.logger.info(f"Scraped: {url}")
        print(f"Crawling: {url}")
        return item