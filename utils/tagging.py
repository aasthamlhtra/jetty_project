from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, SystemMessage
import json
import os
from dotenv import load_dotenv

load_dotenv()
def get_topic_tags(title, content_snippet):
    """
    Uses LangChain + GPT to extract 3-6 keywords from the content.
    We only send a short snippet to keep costs low.
    """

    # just use first 500 chars as a snippet, we don't need the whole thing
    snippet = content_snippet[:500] if content_snippet else ""

    prompt = f"""
Given this article title and content snippet, return 3 to 6 relevant topic keywords as a JSON array.
Only return the JSON array, nothing else.

Title: {title}
Content: {snippet}

Example output: ["machine learning", "neural networks", "computer vision"]
"""

    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        messages = [
            SystemMessage(content="You are a helpful topic tagger. Always respond with a JSON array of keywords only."),
            HumanMessage(content=prompt)
        ]
        response = llm.invoke(messages)
        tags = json.loads(response.content.strip())
        return tags if isinstance(tags, list) else []
    except Exception as e:
        print(f"Tagging failed: {e}")
        return []
