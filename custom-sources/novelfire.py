import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict, Optional
from urllib.parse import urlparse

from slugify import slugify

from lncrawl.core.crawler import Crawler
from lncrawl import constants as C

logger = logging.getLogger(__name__)

FULL_SCAN_INTERVAL_DAYS = int(os.getenv('FULL_SCAN_INTERVAL_DAYS', 7))


class NovelFireCrawler(Crawler):
    base_url = [
        "https://novelfire.net/",
    ]
    has_mtl = False
    has_mange = False

    def initialize(self) -> None:
        super().initialize()
        self.init_executor(ratelimit=3)

    def _get_source_meta_data_and_file_path(self) -> Tuple[Dict, Optional[Path]]:
        """
        Constructs the expected output path, loads source-specific metadata if available.
        Returns a tuple of the source metadata dictionary and the file path to the metadata file.
        """
        source_meta = {}
        source_meta_file = None

        try:
            # Manually construct the output path, mirroring app.py's logic
            host = urlparse(self.novel_url).netloc
            no_www = host.replace('www.', '')
            source_name = slugify(no_www)
            good_file_name = slugify(
                self.novel_title,
                max_length=50,
                separator=" ",
                lowercase=False,
                word_boundary=True,
            )

            output_path = Path(C.DEFAULT_OUTPUT_PATH) / source_name / good_file_name
            output_path.mkdir(parents=True, exist_ok=True)

            source_meta_file = output_path / "novelfire.meta"
            if source_meta_file.exists():
                source_meta = json.loads(source_meta_file.read_text(encoding="utf-8"))
                logger.debug(f"Loaded source-specific meta from {source_meta_file}: {source_meta}")
        except Exception as e:
            logger.warning(f"Error loading source-specific meta: {e}")

        return source_meta, source_meta_file

    def read_novel_info(self) -> None:
        soup = self.get_soup(self.novel_url)

        self.novel_title = soup.find("h1").text.strip().title()
        self.novel_author = soup.select_one('span[itemprop="author"]').text.strip()
        img = soup.select_one(".cover img")
        self.novel_cover = self.absolute_url(img["data-src"])
        tags = [tag.text.strip() for tag in soup.select("a.tag")]
        if tags:
            self.novel_tags = tags
        else:
            # Fallback to meta keywords if no tags found
            meta_keywords = soup.select_one('meta[itemprop="keywords"]')
            if meta_keywords and meta_keywords.get("content"):
                self.novel_tags = [tag.strip() for tag in meta_keywords["content"].split(",")]
            else:
                self.novel_tags = []
        self.novel_synopsis = soup.select_one('meta[itemprop="description"]')
        if self.novel_synopsis:
            self.novel_synopsis = self.novel_synopsis["content"].strip()
        else:
            # Fallback to div.summary if meta tab is not found
            self.novel_synopsis = soup.select_one("div.summary .content")
            if self.novel_synopsis:
                paragraphs = self.novel_synopsis.find_all("p", recursive=False)
                self.novel_synopsis = "\n".join(p.text.strip() for p in paragraphs).strip()
            else:
                self.novel_synopsis = ""

        source_meta, source_meta_file = self._get_source_meta_data_and_file_path()

        # Logic to determine if a full scan is needed
        force_full_scan = False
        last_full_scan_str = source_meta.get("last_full_scan_date")
        if not last_full_scan_str:
            force_full_scan = True
            logger.info("No 'last_full_scan_date' found, forcing full scan.")
        else:
            last_scan_date = datetime.fromisoformat(last_full_scan_str)
            if datetime.now() - last_scan_date > timedelta(days=FULL_SCAN_INTERVAL_DAYS):
                force_full_scan = True
                logger.info(f"last full scan was over {FULL_SCAN_INTERVAL_DAYS} days ago, forcing full scan.")

        # Determine starting URL
        if not force_full_scan:
            logger.info("Attempting to load chapter list from meta.json for incremental scan.")
            # Manually construct the path to the main meta.json file
            host = urlparse(self.novel_url).netloc
            good_file_name = slugify(self.novel_title, max_length=50, separator=" ", lowercase=False, word_boundary=True)
            output_path = Path(C.DEFAULT_OUTPUT_PATH) / slugify(host.replace('www.', '')) / good_file_name
            main_meta_file = output_path / C.META_FILE_NAME
            logger.info(f"Looking for main meta.json at '{main_meta_file}'")

            if main_meta_file.exists():
                try:
                    raw_meta_dict = json.loads(main_meta_file.read_text(encoding="utf-8"))
                    # check if necessary keys exist
                    if "novel" in raw_meta_dict and "chapters" in raw_meta_dict["novel"] and 'volumes' in raw_meta_dict["novel"]:
                        self.chapters = raw_meta_dict["novel"]["chapters"]
                        self.volumes = raw_meta_dict["novel"]["volumes"]
                        logger.info(f"Succesfully loaded {len(self.chapters)} chapters and {len(self.volumes)} volumes from main meta.json")
                    else:
                        raise KeyError("Required keys (novel, chapters, volumes) not found in meta.json")
                except Exception as e:
                    logger.warning(f"Failed to load chapters from main meta.json, forcing full scan. Error: {e}")
                    force_full_scan = True

        if force_full_scan:
            logger.info("Performing a full chapter list scan from the website...")
            self.chapters = []
            self.volumes = []

        existing_chapter_urls = {chapter["url"] for chapter in self.chapters}
        logger.info(f"Starting scan with {len(existing_chapter_urls)} existing chapters.")

        start_url = self.novel_url + "/chapters"  # Default to first page
        current_vol_id = 1
        if not force_full_scan and self.chapters:
            start_url = source_meta.get("last_chapter_url", start_url)
            current_vol_id = self.chapters[-1]["volume"]
            logger.info(f"Starting incremental scan from last known page: {start_url}")

        # Pagination loop
        page_url = start_url
        new_chapters_found = False

        # The loop now continues as long as there is a page to process
        while page_url:
            logger.debug(f"Processing chapter list page: {page_url}")
            soup = self.get_soup(self.absolute_url(page_url))
            chapters_on_page = soup.select("ul.chapter-list li a")

            source_meta["last_chapter_url"] = page_url  # Update last chapter URL in metadata

            for a in chapters_on_page:
                chapter_url = self.absolute_url(a["href"])
                if chapter_url in existing_chapter_urls:
                    continue  # Skip existing chapters

                # New chapter found
                new_chapters_found = True
                chapter_id = len(self.chapters) + 1
                self.chapters.append({
                    "id": chapter_id,
                    "volume": current_vol_id,
                    "title": a["title"],
                    "url": chapter_url,
                })
                logger.info(f"Discovered chapter: {a['title']} - {chapter_url}")

            # After processing a page, check for the next page link
            next_page_link = soup.select_one("a.page-link[rel='next']")
            if next_page_link:
                page_url = self.absolute_url(next_page_link['href'])
                current_vol_id += 1  # Increment volume ID for next set of chapters
            else:
                page_url = None  # No more pages to process

        # save metadata
        if (force_full_scan or new_chapters_found) and source_meta_file:
            # Update the scan date only on a full scan
            if force_full_scan:
                source_meta["last_full_scan_date"] = datetime.now().isoformat()
            try:
                source_meta_file.write_text(json.dumps(source_meta, indent=2), encoding="utf-8")
                logger.info(f"Saved source-specific metadata to {source_meta_file}")
            except Exception as e:
                logger.warning(f"Failed to save source-specific metadata: {e}")

    def download_chapter_body(self, chapter) -> str:
        soup = self.get_soup(chapter["url"])
        contents = soup.select_one("div#content")
        return self.cleaner.extract_contents(contents)
