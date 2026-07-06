import numpy as np

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embedding(title, clean_content):
    """
    Generates an embedding vector for clustering.

    We intentionally center the embedding on the title because RSS summaries tend
    to repeat broad cybersecurity language that makes unrelated stories look
    artificially similar. The body snippet is kept only as a fallback when a
    title is missing.
    """
    title_text = title.strip() if title else ""
    content_text = clean_content.strip() if clean_content else ""

    if title_text:
        combined = title_text
    elif content_text:
        combined = content_text
    else:
        combined = "No title"

    vector = _get_model().encode(combined)
    return vector.tolist()

def cosine_similarity(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0  # avoid division by zero
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
