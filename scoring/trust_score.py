from datetime import datetime
import re
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()


DOMAIN_TIERS = {
    "tier1": ["nih.gov", "who.int", "cdc.gov", "pubmed.ncbi.nlm.nih.gov",
              "nature.com", "nejm.org", "harvard.edu", "mit.edu", "stanford.edu"],
    "tier2": ["healthline.com", "medicalnewstoday.com", "mayoclinic.org",
              "clevelandclinic.org", "webmd.com", "bbc.com", "reuters.com",
              "nytimes.com", "theguardian.com", "acefitness.org"],
    "tier3": ["medium.com", "mygov.in", "youtube.com"]
}
# In trust_score.py

CREDIBLE_CHANNELS = {
    # Tier 1 - academic / official institutions
    "3blue1brown": 0.95,
    "mit opencourseware": 0.95,
    "stanford": 0.95,
    "harvard": 0.95,
    "khan academy": 0.92,
    "nih": 0.95,
    "who": 0.95,
    "cdc": 0.95,
    "ted": 0.90,
    "tedx": 0.85,
    # Tier 2 - reputable tech/science orgs
    "ibm technology": 0.85,
    "ibm": 0.82,
    "google": 0.82,
    "microsoft": 0.80,
    "aws": 0.80,
    "deepmind": 0.88,
    "openai": 0.85,
    "numberphile": 0.88,
    "veritasium": 0.87,
    "kurzgesagt": 0.83,
    "two minute papers": 0.85,
    # Tier 3 - general but known
    "bbc": 0.80,
    "reuters": 0.80,
    "national geographic": 0.82,
}

def get_youtube_channel_score(author):
    if not author or author.lower() in ("unknown", ""):
        return 0.3
    
    author_lower = author.lower()
    
    # exact match first
    if author_lower in CREDIBLE_CHANNELS:
        return CREDIBLE_CHANNELS[author_lower]
    
    # partial match (e.g. "IBM Technology" matches "ibm")
    for channel, score in CREDIBLE_CHANNELS.items():
        if channel in author_lower or author_lower in channel:
            return score
    
    # has a real name but not in our list
    parts = author.strip().split()
    if len(parts) >= 2:
        return 0.55  # named individual, unknown credibility
    
    return 0.40  # single word / handle, likely informal

def get_domain_authority(url):
    for domain in DOMAIN_TIERS["tier1"]:
        if domain in url:
            return 0.95
    for domain in DOMAIN_TIERS["tier2"]:
        if domain in url:
            return 0.75
    for domain in DOMAIN_TIERS["tier3"]:
        if domain in url:
            return 0.55
    if ".edu" in url or ".gov" in url:
        return 0.85
    if ".org" in url:
        return 0.6
    return 0.35

# medical/health keywords to check for disclaimers
DISCLAIMER_KEYWORDS = [
    "not medical advice", "consult a doctor", "consult a physician",
    "consult your healthcare", "for informational purposes only",
    "seek professional advice", "this is not intended to"
]

CREDIBLE_ORGS = ["ibm", "google", "mit", "harvard", "stanford", "who", 
                 "cdc", "nih", "3blue1brown", "bbc", "reuters"]

def get_author_credibility(author, source_type):
    if not author or author.lower() in ("unknown", ""):
        return 0.2

    if source_type == "pubmed":
        return 0.9

    author_lower = author.lower()
    # check if author matches a known credible org/creator
    if any(org in author_lower for org in CREDIBLE_ORGS):
        return 0.85

    # has a plausible full name (First Last)?
    parts = author.strip().split()
    if len(parts) >= 2:
        return 0.65

    return 0.5  # single name / handle, better than unknown
def get_recency_score(published_date):
    if not published_date or published_date == "unknown":
        return 0.3  # we don't know, slight penalty

    # try to extract year
    year_match = re.search(r"(20\d{2}|19\d{2})", str(published_date))
    if not year_match:
        return 0.3

    year = int(year_match.group(1))
    current_year = datetime.now().year
    age = current_year - year

    if age <= 1:
        return 1.0
    elif age <= 2:
        return 0.85
    elif age <= 5:
        return 0.65
    elif age <= 10:
        return 0.4
    else:
        return 0.2


def get_citation_score(citation_count):
    # only relevant for pubmed
    if citation_count >= 100:
        return 1.0
    elif citation_count >= 50:
        return 0.85
    elif citation_count >= 20:
        return 0.7
    elif citation_count >= 5:
        return 0.5
    elif citation_count > 0:
        return 0.35
    else:
        return 0.2


def check_medical_disclaimer(content, url):
    text = content.lower()
    for phrase in DISCLAIMER_KEYWORDS:
        if phrase in text:
            return 1.0
    # if it's a medical source like pubmed, don't penalize
    if "pubmed" in url or "nih.gov" in url:
        return 1.0
    return 0.5


def compute_trust_score(item, semantic_similarity=None):
    source_type = item.get("source_type", "")
    url = item.get("source_url", "")
    author = item.get("author", "unknown")
    published_date = item.get("published_date", "")
    content = item.get("content", "")
    citation_count = item.get("citation_count", 0)

    recency_score = get_recency_score(published_date)
    disclaimer_score = check_medical_disclaimer(content, url)

    if source_type == "pubmed":
        domain_score = get_domain_authority(url)
        author_score = get_author_credibility(author, source_type)
        citation_score = get_citation_score(citation_count)
        raw_score = (
            0.25 * author_score +
            0.20 * domain_score +
            0.15 * recency_score +
            0.25 * citation_score +
            0.15 * disclaimer_score
        )

    elif source_type == "youtube":
        # for youtube, channel credibility replaces both domain + author
        # since the platform is always youtube.com (domain is uninformative)
        channel_score = get_youtube_channel_score(author)
        raw_score = (
            0.50 * channel_score +   # who made it matters most
            0.30 * recency_score +
            0.20 * disclaimer_score
        )

    else:  # blog
        domain_score = get_domain_authority(url)
        author_score = get_author_credibility(author, source_type)
        raw_score = (
            0.30 * author_score +
            0.30 * domain_score +
            0.25 * recency_score +
            0.15 * disclaimer_score
        )

    if semantic_similarity is not None:
        if semantic_similarity < 0.3:
            raw_score *= 0.7
        elif semantic_similarity < 0.5:
            raw_score *= 0.85

    return round(max(0.0, min(1.0, raw_score)), 3)


def generate_trust_explanation(item, trust_score, semantic_similarity, top_chunks):
    """
    Uses the sub-scores and top relevant chunks to generate a short,
    human-readable explanation of why the trust score is what it is.
    """
    url = item.get("source_url", "")
    author = item.get("author", "unknown")
    published_date = item.get("published_date", "unknown")
    source_type = item.get("source_type", "")
    content = item.get("content", "")
    citation_count = item.get("citation_count", 0)

    # gather the signal values so the LLM has something concrete to work with
    domain_score = get_domain_authority(url)
    author_score = get_author_credibility(author, source_type)
    recency_score = get_recency_score(published_date)
    disclaimer_score = check_medical_disclaimer(content, url)

    # build a short context string from top chunks
    chunk_context = "\n".join(f"- {c[:200]}" for c in top_chunks) if top_chunks else "No content available."

    prompt = f"""You are reviewing a {source_type} source for trustworthiness.

Here are the scoring signals:
- Trust score: {trust_score} (out of 1.0)
- Domain authority score: {domain_score} (URL: {url})
- Author credibility score: {author_score} (Author: {author})
- Recency score: {recency_score} (Published: {published_date})
- Medical disclaimer present: {"yes" if disclaimer_score == 1.0 else "no"}
- Semantic consistency (title vs content): {semantic_similarity if semantic_similarity is not None else "not computed"}
{f"- Citation count: {citation_count}" if source_type == "pubmed" else ""}

Most relevant content chunks:
{chunk_context}

Write ONE short paragraph (2-3 sentences) explaining why this source received that trust score.
Mention recency, domain quality, author presence, and content consistency where relevant.
Be specific but concise. Do not repeat the numbers directly - use natural language like "recent", "well-known domain", "no clear author", etc.
"""

    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)
        messages = [
            SystemMessage(content="You explain trust scores for online sources in plain, clear English."),
            HumanMessage(content=prompt)
        ]
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        print(f"Could not generate trust explanation: {e}")
        # fallback to a basic rule-based explanation if LLM fails
        parts = []
        if recency_score >= 0.85:
            parts.append("the content is recent")
        elif recency_score <= 0.3:
            parts.append("the content may be outdated")
        if domain_score >= 0.8:
            parts.append("it comes from a reputable domain")
        elif domain_score <= 0.4:
            parts.append("the domain is not well-established")
        if author_score <= 0.2:
            parts.append("no clear author is listed")
        if disclaimer_score == 0.0:
            parts.append("no medical disclaimer was found")
        if semantic_similarity is not None and semantic_similarity < 0.4:
            parts.append("the title and content seem inconsistent")
        if not parts:
            return f"This source received a trust score of {trust_score}."
        return "Trust score reflects that " + ", and ".join(parts) + "."
