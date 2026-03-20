import requests
from bs4 import BeautifulSoup
from datetime import datetime
from langdetect import detect
import json
import re


def scrape_blog(url):
    print(f"Scraping blog: {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    author = ""
    published_date = ""
    content = ""

    # --- title ---
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    # --- LD+JSON: must read BEFORE removing script tags ---
    for script_tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            ld = json.loads(script_tag.string or "")
            # unwrap list first, then read fields
            if isinstance(ld, list):
                ld = ld[0]
            if not isinstance(ld, dict):
                continue
            if not published_date:
                published_date = ld.get("datePublished", "") or ld.get("dateModified", "")
            if not author:
                author_field = ld.get("author", {})
                if isinstance(author_field, dict):
                    author = author_field.get("name", "")
                elif isinstance(author_field, list) and author_field:
                    author = ", ".join(
                        a.get("name", "") for a in author_field if isinstance(a, dict)
                    )
            if author and published_date:
                break  # no need to check more script tags
        except Exception:
            continue

    # --- NOW remove noise elements (after LD+JSON is read) ---
    for tag in soup(["nav", "footer", "script", "style", "aside", "header", "form"]):
        tag.decompose()

    # --- author fallbacks ---
    if not author:
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta:
            author = author_meta.get("content", "")
    if not author:
        for cls in ["author", "byline", "post-author", "entry-author",
                    "article-author", "contributor", "writer"]:
            tag = soup.find(class_=re.compile(cls, re.I))
            if tag:
                author = tag.get_text(strip=True)
                break
    if not author:
        # some sites use a <span> or <a> with rel="author"
        rel_author = soup.find(attrs={"rel": "author"})
        if rel_author:
            author = rel_author.get_text(strip=True)

    # --- date fallbacks ---
    if not published_date:
        date_meta = soup.find("meta", attrs={"property": "article:published_time"})
        if date_meta:
            published_date = date_meta.get("content", "")
    if not published_date:
        for cls in ["date", "publish-date", "entry-date", "post-date",
                    "article-date", "published", "timestamp"]:
            tag = soup.find(class_=re.compile(cls, re.I))
            if tag:
                published_date = tag.get_text(strip=True)
                break
    if not published_date:
        # <time> element is standard HTML5
        time_tag = soup.find("time")
        if time_tag:
            published_date = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

    # --- content extraction ---
    for selector in ["article", "main", '[role="main"]',
                     ".post-content", ".entry-content", ".article-body"]:
        container = soup.find(selector) if not selector.startswith(".") \
                    and not selector.startswith("[") else soup.select_one(selector)
        if container:
            paragraphs = container.find_all("p")
            break
    else:
        paragraphs = soup.find_all("p")

    content = " ".join(
        p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30
    )

    # --- language detection ---
    try:
        language = detect(content) if content else "unknown"
    except Exception:
        language = "unknown"

    if author and author.lower() != "unknown":
        author = re.sub(r"^(by|written by|posted by)\s+", "", author, flags=re.IGNORECASE).strip()

    return {
        "source_url": url,
        "source_type": "blog",
        "title": title,
        "author": author if author else "unknown",
        "published_date": published_date if published_date else "unknown",
        "language": language,
        "region": "",
        "content": content,
        "topic_tags": [],
        "trust_score": None,
        "content_chunks": []
    }


def scrape_multiple_blogs(urls):
    results = []
    for url in urls:
        data = scrape_blog(url)
        if data:
            results.append(data)
    return results