import json
import os
from scraper.blog_scraper import scrape_multiple_blogs
from scraper.youtube_scraper import scrape_multiple_videos
from scraper.pubmed_scraper import scrape_pubmed
from scoring.trust_score import compute_trust_score, generate_trust_explanation
from utils.tagging import get_topic_tags
from utils.chunking import chunk_text, compute_semantic_consistency, get_top_chunks

BLOG_URLS = [
    "https://www.healthline.com/nutrition/10-benefits-of-low-carb-ketogenic-diets",
    "https://www.medicalnewstoday.com/articles/no-link-between-mobile-phones-and-brain-cancer-who-backed-study-says",
    "https://harvardonline.harvard.edu/blog/why-your-best-ideas-come-from-unexpected-places"
]

YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=1bUy-1hGZpI",  # What is LangChain - IBM
    "https://www.youtube.com/watch?v=aircAruvnKk"   # But what is a neural network? - 3Blue1Brown
]

PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/16767798/"  

OUTPUT_FILE = "output/scraped_data.json"


def process_item(item):
    title = item.get("title", "")
    content = item.get("content", "")

    print(f"\nProcessing: {title[:60]}")

    # chunk the content
    chunks = chunk_text(content)
    item["content_chunks"] = chunks
    print(f"  Created {len(chunks)} chunks")

    # get topic tags via LangChain
    tags = get_topic_tags(title, content)
    item["topic_tags"] = tags
    print(f"  Tags: {tags}")

    # compute semantic consistency
    semantic_sim = compute_semantic_consistency(title, chunks)
    item["semantic_consistency"] = semantic_sim
    print(f"  Semantic consistency: {semantic_sim}")

    # compute trust score
    trust = compute_trust_score(item, semantic_similarity=semantic_sim)
    item["trust_score"] = trust
    print(f"  Trust score: {trust}")

    # find top relevant chunks
    top_chunks = get_top_chunks(title, chunks, top_n=3)

    # generate a human-readable explanation for the trust score
    explanation = generate_trust_explanation(item, trust, semantic_sim, top_chunks)
    item["trust_explanation"] = explanation
    print(f"  Explanation: {explanation}")

    return item


def build_output_record(item):
    """Strips internal fields and returns only the required output format."""
    return {
        "source_url": item.get("source_url", ""),
        "source_type": item.get("source_type", ""),
        "title": item.get("title", ""),
        "author": item.get("author", ""),
        "published_date": item.get("published_date", ""),
        "language": item.get("language", ""),
        "region": item.get("region", ""),
        "topic_tags": item.get("topic_tags", []),
        "trust_score": item.get("trust_score", None),
        "semantic_consistency": item.get("semantic_consistency", None),
        "trust_explanation": item.get("trust_explanation", ""),
        "content_chunks": item.get("content_chunks", [])
    }


def main():
    all_results = []

    # scrape blogs
    print("\nScraping Blogs")
    blogs = scrape_multiple_blogs(BLOG_URLS)
    for b in blogs:
        b = process_item(b)
        all_results.append(build_output_record(b))

    # scrape youtube
    print("\nScraping YouTube Videos")
    videos = scrape_multiple_videos(YOUTUBE_URLS)
    for v in videos:
        v = process_item(v)
        all_results.append(build_output_record(v))

    # scrape pubmed
    print("\nScraping PubMed Article")
    pubmed_item = scrape_pubmed(PUBMED_URL)
    if pubmed_item:
        pubmed_item = process_item(pubmed_item)
        all_results.append(build_output_record(pubmed_item))

    # save to json
    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n Done! {len(all_results)} records saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
