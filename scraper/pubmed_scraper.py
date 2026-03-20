import requests
from bs4 import BeautifulSoup
from langdetect import detect
import re

PUBMED_API_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def extract_pmid(url):
    match = re.search(r"/(\d{6,})", url)
    if match:
        return match.group(1)
    return None


def scrape_pubmed(url):
    print(f"Scraping PubMed: {url}")

    pmid = extract_pmid(url)
    if not pmid:
        print("Could not extract PMID from URL")
        return None

    # use efetch to get article details as XML
    fetch_url = f"{PUBMED_API_BASE}/efetch.fcgi?db=pubmed&id={pmid}&rettype=abstract&retmode=xml"

    try:
        response = requests.get(fetch_url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch PubMed data: {e}")
        return None

    soup = BeautifulSoup(response.text, "xml")

    title = ""
    authors = []
    journal = ""
    abstract = ""
    pub_year = ""

    # extract title
    title_tag = soup.find("ArticleTitle")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # extract all authors
    for author_tag in soup.find_all("Author"):
        last = author_tag.find("LastName")
        first = author_tag.find("ForeName")
        if last:
            name = last.get_text(strip=True)
            if first:
                name = first.get_text(strip=True) + " " + name
            authors.append(name)

    # journal name
    journal_tag = soup.find("Title")
    if journal_tag:
        journal = journal_tag.get_text(strip=True)

    # abstract text
    abstract_tag = soup.find("AbstractText")
    if abstract_tag:
        abstract = abstract_tag.get_text(strip=True)

    # publication year
    year_tag = soup.find("PubDate")
    if year_tag:
        y = year_tag.find("Year")
        if y:
            pub_year = y.get_text(strip=True)

    # detect language
    try:
        language = detect(abstract) if abstract else "unknown"
    except:
        language = "unknown"

    # also try to get citation count using elink (rough estimate)
    citation_count = 0
    try:
        elink_url = f"{PUBMED_API_BASE}/elink.fcgi?dbfrom=pubmed&linkname=pubmed_pubmed_citedin&id={pmid}&retmode=json"
        elink_resp = requests.get(elink_url, timeout=8)
        elink_data = elink_resp.json()
        links = elink_data.get("linksets", [{}])[0].get("linksetdbs", [])
        for link in links:
            if link.get("linkname") == "pubmed_pubmed_citedin":
                citation_count = len(link.get("links", []))
    except Exception as e:
        print(f"Could not fetch citation count: {e}")

    return {
        "source_url": url,
        "source_type": "pubmed",
        "title": title,
        "author": ", ".join(authors) if authors else "unknown",
        "authors_list": authors,
        "published_date": pub_year if pub_year else "unknown",
        "journal": journal,
        "citation_count": citation_count,
        "language": language,
        "region": "",
        "content": abstract,
        "topic_tags": [],
        "trust_score": None,
        "content_chunks": []
    }
