import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from langdetect import detect
import re

def get_video_id(url):
    # extract video id from youtube url
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    return None


def scrape_youtube(url):
    print(f"Scraping YouTube: {url}")

    video_id = get_video_id(url)
    if not video_id:
        print("Could not extract video ID")
        return None

    # fetch youtube page for basic metadata
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch YouTube page: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    channel_name = ""
    published_date = ""
    description = ""

    # title is usually in og:title
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title:
        title = og_title.get("content", "")

    # channel from itemprop
    channel_tag = soup.find("link", attrs={"itemprop": "name"})
    if channel_tag:
        channel_name = channel_tag.get("content", "")

    # description from meta
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        description = desc_tag.get("content", "")

    # date from meta
    date_tag = soup.find("meta", attrs={"itemprop": "datePublished"})
    if date_tag:
        published_date = date_tag.get("content", "")

    # try to get transcript
    transcript_text = ""
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        transcript_text = " ".join(entry.text for entry in transcript)
        print("Transcript fetched successfully")
    except Exception as e:
        print(f"No transcript available, using description: {e}")
        transcript_text = description  # fallback

    # use transcript for language detection if available
    content_for_lang = transcript_text if transcript_text else description
    try:
        language = detect(content_for_lang) if content_for_lang else "unknown"
    except:
        language = "unknown"

    return {
        "source_url": url,
        "source_type": "youtube",
        "title": title,
        "author": channel_name if channel_name else "unknown",
        "published_date": published_date if published_date else "unknown",
        "language": language,
        "region": "",
        "content": transcript_text,
        "description": description,
        "topic_tags": [],
        "trust_score": None,
        "content_chunks": []
    }


def scrape_multiple_videos(urls):
    results = []
    for url in urls:
        data = scrape_youtube(url)
        if data:
            results.append(data)
    return results
