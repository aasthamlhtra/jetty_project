from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import math
import numpy as np
from dotenv import load_dotenv

load_dotenv()


def chunk_text(text, chunk_size=1500, chunk_overlap=150):
    """
    Split text into semantically meaningful chunks using LangChain's
    RecursiveCharacterTextSplitter. Splits by paragraph, sentence, then
    word, preserving natural boundaries before resorting to hard cuts.
    chunk_overlap retains context across chunk boundaries.
    """
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],  # priority order: paragraph -> sentence -> word
        length_function=len,
    )

    chunks = splitter.split_text(text)
    return chunks


def cosine_similarity(vec1, vec2):
    a, b = np.array(vec1), np.array(vec2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return 0.0 if denom == 0 else float(np.dot(a, b) / denom)


def get_top_chunks(title, chunks, top_n=3):
    """
    Embeds the title and all chunks, returns the top_n chunks
    most similar to the title. Used later for trust explanation.
    Embeddings are just stored in a plain list
    """

    # I didn't use a vector DB like chroma or FAISS to store the embeddings
    # vector DBs solve a persistence problem which we don't have.
    # We embed, score, grab the top chunks, and move on, nothing needs to stick around
    # between runs. Spinning up a Chroma collection just to sort 10-20 vectors and
    # immediately throw them away would be all overhead and no benefit.
    # If this grows into something where users query across saved articles,
    # that's when we'd use a vector DB. For now, I used a plain llist

    if not chunks or not title:
        return []

    try:
        embedder = OpenAIEmbeddings()

        # batch embed title and all chunks in one API call
        all_texts = [title] + chunks
        all_embeddings = embedder.embed_documents(all_texts)

        title_embedding = all_embeddings[0]
        chunk_embeddings = all_embeddings[1:]

        # score each chunk against the title
        scored = [
            (cosine_similarity(title_embedding, chunk_emb), chunk)
            for chunk, chunk_emb in zip(chunks, chunk_embeddings)
        ]

        # sort by similarity descending, return top N chunks
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [chunk for _, chunk in scored[:top_n]]
        return top_chunks

    except Exception as e:
        print(f"get_top_chunks failed: {e}")
        return chunks[:top_n]  # fallback to first N chunks


def compute_semantic_consistency(title, chunks):
    """
    Embeds the title and each content chunk, then computes
    average cosine similarity between title and chunks.
    Low score = possible clickbait or misleading title.
    """
    if not chunks or not title:
        return None

    try:
        embedder = OpenAIEmbeddings()

        # limit to first 5 chunks to save cost, then batch in one API call
        sampled_chunks = chunks[:5]
        all_texts = [title] + sampled_chunks
        all_embeddings = embedder.embed_documents(all_texts)

        title_embedding = all_embeddings[0]
        chunk_embeddings = all_embeddings[1:]

        # compute average similarity between title and each chunk
        similarities = [
            cosine_similarity(title_embedding, chunk_emb)
            for chunk_emb in chunk_embeddings
        ]

        if not similarities:
            return None

        avg_similarity = sum(similarities) / len(similarities)
        return round(avg_similarity, 4)

    except Exception as e:
        print(f"Semantic consistency check failed: {e}")
        return None
