# Multi-Source Data Scraper & Trust Scoring System

## Project Overview

This project implements a multi-source web scraping pipeline that collects structured content from blogs, YouTube videos, and PubMed articles, then evaluates each source's reliability using a custom Trust Scoring algorithm. All results are stored as structured JSON for downstream processing.

---

## Project Structure

```
project/
├── main.py                  # Entry point: orchestrates scraping, tagging, chunking, scoring
├── requirements.txt         # Python dependencies
├── scraper/
│   ├── blog_scraper.py      # Blog scraping via requests + BeautifulSoup
│   ├── youtube_scraper.py   # YouTube metadata + transcript extraction
│   └── pubmed_scraper.py    # PubMed article extraction via NCBI eUtils API
├── scoring/
│   └── trust_score.py       # Trust scoring algorithm and LLM-based explanation generator
├── utils/
│   ├── tagging.py           # LLM-powered topic tag extraction
│   └── chunking.py          # Text chunking and semantic consistency scoring
└── output/
    └── scraped_data.json    # Final output with all 6 scraped records
```

---

## Tools and Libraries Used

| Library | Purpose |
|---|---|
| `requests` | HTTP requests for fetching web pages and APIs |
| `beautifulsoup4` + `lxml` | HTML/XML parsing for blog and PubMed content |
| `youtube-transcript-api` | Fetching auto-generated or manual YouTube transcripts |
| `langdetect` | Automatic language detection from content text |
| `langchain` + `langchain-openai` | LLM orchestration for topic tagging and trust explanations |
| `openai` (via LangChain) | GPT-3.5-turbo for tagging, scoring explanation generation |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` for intelligent content chunking |
| `numpy` | Cosine similarity computation for semantic consistency scoring |
| `python-dotenv` | Loading OpenAI API key from a `.env` file |
| NCBI eUtils API | Free, authentication-free API for PubMed article data and citation counts |

---

## Scraping Approach

### Blog Scraper (`scraper/blog_scraper.py`)
Fetches blog pages using `requests` with a browser-like User-Agent header. Metadata extraction uses a layered strategy:
- **Primary:** Parses `LD+JSON` (`application/ld+json`) structured data blocks before removing any script tags, ensuring author and date fields are captured from schema.org metadata.
- **Fallback chain:** Checks `<meta>` tags (`name="author"`, `property="article:published_time"`), CSS class patterns (e.g. `byline`, `entry-date`), and HTML5 `<time>` elements.
- **Content extraction:** Targets semantic HTML containers (`<article>`, `<main>`, `[role="main"]`, `.post-content`, `.entry-content`) and extracts `<p>` tags with meaningful length (>30 chars), filtering out navigation and boilerplate.

### YouTube Scraper (`scraper/youtube_scraper.py`)
Fetches the YouTube page HTML to extract `og:title`, channel name (`itemprop="name"`), description, and publish date (`itemprop="datePublished"`) from meta tags. Video transcripts are retrieved using `YouTubeTranscriptApi`; if no transcript is available, the video description is used as a fallback for content analysis.

### PubMed Scraper (`scraper/pubmed_scraper.py`)
Uses the **NCBI eUtils API** (no authentication required) rather than scraping the website directly. The PMID is extracted from the URL, then `efetch` is called to retrieve structured XML containing the title, author list, journal name, abstract, and publication year. Citation counts are estimated via the `elink` endpoint (`pubmed_pubmed_citedin` link set).

---

## Trust Score Design

The trust score is computed in `scoring/trust_score.py` and returns a value between **0.0 and 1.0**. The formula and weights vary by source type to reflect what credibility signals are actually available and meaningful for each platform.

### Scoring Formula

**Blog:**
```
Trust Score = 0.30 × author_credibility
            + 0.30 × domain_authority
            + 0.25 × recency_score
            + 0.15 × medical_disclaimer_score
```

**YouTube:**
```
Trust Score = 0.50 × channel_credibility
            + 0.30 × recency_score
            + 0.20 × medical_disclaimer_score
```
*(Domain authority is not used for YouTube since all videos share the same domain, making it uninformative.)*

**PubMed:**
```
Trust Score = 0.25 × author_credibility
            + 0.20 × domain_authority
            + 0.15 × recency_score
            + 0.25 × citation_score
            + 0.15 × medical_disclaimer_score
```

### Signal Definitions

| Signal | How It Is Computed |
|---|---|
| `author_credibility` | Checks against a known credible organisations list (`ibm`, `harvard`, `who`, etc.); PubMed authors are automatically scored 0.9; unknown authors score 0.2 |
| `domain_authority` | Three-tier domain list: Tier 1 (`.gov`, `nih.gov`, `harvard.edu` → 0.95), Tier 2 (`healthline.com`, `bbc.com` → 0.75), Tier 3 (`medium.com`, `youtube.com` → 0.55); unknown domains score 0.35 |
| `channel_credibility` | YouTube-specific lookup against a curated channel dictionary (`3Blue1Brown → 0.95`, `IBM Technology → 0.85`, etc.) with partial-match support |
| `recency_score` | Year extracted from publish date; ≤1 year old → 1.0; ≤2 years → 0.85; ≤5 years → 0.65; ≤10 years → 0.4; older → 0.2; unknown → 0.3 |
| `citation_score` | Only for PubMed; ≥100 citations → 1.0; ≥50 → 0.85; ≥20 → 0.7; ≥5 → 0.5; >0 → 0.35; 0 → 0.2 |
| `medical_disclaimer_score` | Keyword search for phrases like *"not medical advice"*, *"consult a doctor"*, *"for informational purposes only"*; PubMed/NIH URLs are automatically exempt |
| `semantic_consistency` | Cosine similarity between OpenAI embeddings of the title and up to 5 content chunks; scores below 0.3 apply a 30% penalty; scores below 0.5 apply a 15% penalty |

### LLM-Generated Explanation
After scoring, `generate_trust_explanation()` sends the sub-scores and the top 3 most title-relevant content chunks to GPT-3.5-turbo, which produces a short, plain-English explanation of the score. A rule-based fallback is used if the LLM call fails.

---

## Limitations

- **OpenAI API Key Required:** Topic tagging, semantic consistency scoring, and trust explanations all depend on GPT-3.5-turbo and OpenAI Embeddings. Without a valid API key in `.env`, these features degrade gracefully (empty tags, no explanation, no semantic score).
- **YouTube Metadata Limits:** YouTube's page structure can change, and transcript availability depends on the video's captioning settings. If no transcript exists, the video description (usually brief) is used instead, reducing chunking and tagging quality.
- **Citation Count Approximation:** The NCBI `elink` endpoint returns citations indexed within PubMed only. Actual citation counts across all databases (e.g. Google Scholar) may be significantly higher.
- **Domain Tier Lists Are Static:** The domain and channel credibility lookups use hard-coded lists. New or unlisted domains default to low scores even if the source is credible.
- **Region Detection:** The `region` field is not currently populated. No IP geolocation or content-based region inference is implemented.
- **Rate Limiting:** No request throttling is implemented. Scraping many URLs in quick succession may trigger rate limits on target websites.

---

## How to Run the Project

### 1. Prerequisites
- Python 3.9+
- An OpenAI API key

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Run the Scraper
```bash
python main.py
```

### 5. Output
Results are saved to `output/scraped_data.json`. Each record includes source metadata, topic tags, content chunks, trust score, semantic consistency score, and a plain-English trust explanation.

---

## Output Schema

```json
{
  "source_url": "https://...",
  "source_type": "blog | youtube | pubmed",
  "title": "...",
  "author": "...",
  "published_date": "...",
  "language": "en",
  "region": "",
  "topic_tags": ["tag1", "tag2"],
  "trust_score": 0.742,
  "semantic_consistency": 0.6812,
  "trust_explanation": "Plain-English explanation...",
  "content_chunks": ["chunk 1 text...", "chunk 2 text..."]
}
```
