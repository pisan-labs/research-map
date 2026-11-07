"""Vectors, layout, areas, labels and neighbours."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .text import STOP_WORDS, Doc

# Picked 2026-11-07 on the UW Bothell slice: ties the best English model on the
# curated-area check (48% of top-5 neighbours share an area) and is multilingual.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


# ---------------------------------------------------------------- embedding


class Embedder:
    """Sentence-transformer with an on-disk cache keyed by model and text."""

    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: Path | None = None):
        self.model_name = model_name
        self.cache_path = cache_dir / f"emb-{model_name.replace('/', '_')}.json" if cache_dir else None
        self.cache: dict[str, list[float]] = {}
        if self.cache_path and self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text())
        self._model = None

    def _prefix(self, text: str) -> str:
        # e5 models expect a "passage: " prefix for documents.
        return f"passage: {text}" if "e5" in self.model_name else text

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        keys = [hashlib.sha256(t.encode()).hexdigest()[:20] for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self.cache]
        if missing:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device="cpu")
            vecs = self._model.encode(
                [self._prefix(texts[i]) for i in missing],
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False,
            )
            for i, v in zip(missing, vecs):
                self.cache[keys[i]] = [round(float(x), 6) for x in v]
            if self.cache_path:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(self.cache))
        return np.array([self.cache[k] for k in keys], dtype=np.float32)


def person_vectors(docs: Sequence[Doc], embedder: Embedder) -> np.ndarray:
    """Weighted mean of each person's field vectors, L2-normalised."""
    flat: list[str] = []
    owners: list[tuple[int, float]] = []
    for i, d in enumerate(docs):
        for text, w in d.weighted:
            flat.append(text)
            owners.append((i, w))
    vecs = embedder.encode(flat)
    out = np.zeros((len(docs), vecs.shape[1]), dtype=np.float32)
    for (i, w), v in zip(owners, vecs):
        out[i] += w * v
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return out / norms


# ---------------------------------------------------------------- layout


def layout(vectors: np.ndarray, n_neighbors: int = 10, min_dist: float = 0.35, seed: int = 42) -> np.ndarray:
    """UMAP to 2-D, scaled into [0, 1] keeping the aspect ratio."""
    import umap

    n_neighbors = min(n_neighbors, len(vectors) - 1)
    xy = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric="cosine",
        random_state=seed,
        n_jobs=1,
    ).fit_transform(vectors)
    xy = xy - xy.min(axis=0)
    xy = xy / max(float(xy.max()), 1e-9)
    return xy


# ---------------------------------------------------------------- neighbours and areas


def similarity(vectors: np.ndarray) -> np.ndarray:
    sim = vectors @ vectors.T
    np.fill_diagonal(sim, -1.0)
    return sim


def nearest(sim: np.ndarray, k: int) -> list[list[tuple[int, float]]]:
    out = []
    for row in sim:
        idx = np.argsort(-row)[:k]
        out.append([(int(j), float(row[j])) for j in idx])
    return out


def leiden_areas(sim: np.ndarray, k: int = 8, resolution: float = 1.0, seed: int = 42) -> list[int]:
    """Leiden communities on a symmetric k-nearest-neighbour graph."""
    import igraph as ig
    import leidenalg

    edges: dict[tuple[int, int], float] = {}
    for i, nbrs in enumerate(nearest(sim, k)):
        for j, s in nbrs:
            a, b = min(i, j), max(i, j)
            edges[(a, b)] = max(edges.get((a, b), 0.0), max(s, 0.0))
    g = ig.Graph(n=sim.shape[0], edges=list(edges), directed=False)
    g.es["weight"] = list(edges.values())
    part = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=resolution,
        seed=seed,
    )
    return relabel_by_size(list(part.membership))


def relabel_by_size(labels: list[int]) -> list[int]:
    """Renumber clusters so 0 is the largest; ties broken by first appearance."""
    order = sorted(set(labels), key=lambda c: (-labels.count(c), labels.index(c)))
    remap = {c: i for i, c in enumerate(order)}
    return [remap[c] for c in labels]


# ---------------------------------------------------------------- labels and terms


def _stop_words(extra: set[str] = frozenset()) -> frozenset[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    return frozenset(ENGLISH_STOP_WORDS | STOP_WORDS | LABEL_STOP | set(extra))


def phrase_analyzer(stop: frozenset[str], ngrams: tuple[int, int]):
    """N-grams within a clause that neither start nor end with a stop word.

    Unlike CountVectorizer's default, inner stop words are kept, so
    'internet of things' stays whole instead of becoming 'internet things'.
    """
    lo, hi = ngrams

    def analyze(text: str) -> list[str]:
        out: list[str] = []
        # "/" is not a clause break: "augmented/virtual reality" keeps "virtual reality".
        for clause in re.split(r"[,;:.()\[\]!?]+|\s-\s|\band\b", text.lower()):
            toks = re.findall(r"[a-z][a-z-]+", clause)
            for n in range(lo, hi + 1):
                for i in range(len(toks) - n + 1):
                    g = toks[i : i + n]
                    if g[0] in stop or g[-1] in stop:
                        continue
                    if n == 1 and len(g[0]) < 3:
                        continue
                    out.append(" ".join(g))
        return out

    return analyze


def _vectorizer(extra_stop: set[str] = frozenset(), ngrams: tuple[int, int] = (1, 2)):
    from sklearn.feature_extraction.text import CountVectorizer

    return CountVectorizer(analyzer=phrase_analyzer(_stop_words(extra_stop), ngrams), min_df=1)


def _overlaps(term: str, chosen: Sequence[str]) -> bool:
    """Same words, one inside the other, or a shared 6-letter stem (mathematics/mathematical)."""
    for c in chosen:
        if term in c or c in term:
            return True
        if any(a[:6] == b[:6] and min(len(a), len(b)) >= 6 for a in term.split() for b in c.split()):
            return True
    return False


# Abbreviations that duplicate a longer label, and filler that survives in keyword lines.
LABEL_STOP = {
    "ml", "etc", "e-g", "i-e", "general", "specifically", "particular", "especially",
    "conducts", "conduct", "conducting", "improve", "improving", "explore", "exploring",
    "understanding", "understand", "develop", "developing", "development", "investigate",
    "investigating", "interested", "passionate", "current", "recent", "primary", "primarily",
    "broad", "broadly", "wide", "variety", "range", "different", "key", "novel", "aspects",
    "issues", "problems", "techniques", "technology", "technologies", "analysis", "theory",
    "design", "modeling", "approach", "learning-",
}


def name_tokens(names: Sequence[str]) -> set[str]:
    """Lowercase name parts, so people's own names never become topic terms."""
    out: set[str] = set()
    for n in names:
        out |= {t for t in re.findall(r"[a-z][a-z-]+", n.lower()) if len(t) > 1}
    return out


def person_terms(docs: Sequence[Doc], top: int = 12, names: Sequence[str] = ()) -> list[list[str]]:
    """Each person's most distinctive terms (TF-IDF over everyone)."""
    from sklearn.feature_extraction.text import TfidfTransformer

    vec = _vectorizer(name_tokens(names))
    # Prefer the person's own short descriptions; fall back to the bio when they are thin.
    texts = [d.topic_text if len(d.topic_text.split()) >= 6 else d.all_text for d in docs]
    counts = vec.fit_transform(texts)
    tfidf = TfidfTransformer(sublinear_tf=True).fit_transform(counts).toarray()
    vocab = np.array(vec.get_feature_names_out())
    out = []
    for row in tfidf:
        idx = [j for j in np.argsort(-row)[: top * 2] if row[j] > 0]
        chosen: list[str] = []
        for j in idx:
            t = vocab[j]
            if _overlaps(t, chosen):
                continue
            chosen.append(t)
            if len(chosen) == top:
                break
        out.append(chosen)
    return out


def cluster_labels(
    docs: Sequence[Doc], labels: Sequence[int], top: int = 2, names: Sequence[str] = ()
) -> dict[int, list[str]]:
    """Class-based TF-IDF over each person's topic text (keywords and interests).

    Bios are left out: they bring words like 'instructor' or 'company'. A
    longer phrase that contains a chosen term and is nearly as common in the
    cluster replaces it, so 'machine learning' wins over 'learning'.
    """
    vec = _vectorizer(name_tokens(names), ngrams=(1, 3))
    counts = vec.fit_transform([d.topic_text for d in docs]).toarray()
    vocab = list(vec.get_feature_names_out())
    clusters = sorted(set(labels))
    lab = np.array(labels)
    # Count each term at most once per person so one long line cannot dominate.
    binary = (counts > 0).astype(float)
    per_cluster = np.array([binary[lab == c].sum(axis=0) for c in clusters])
    tf = per_cluster / np.maximum(per_cluster.sum(axis=1, keepdims=True), 1)
    avg = binary.sum(axis=0).mean() or 1.0
    idf = np.log(1 + avg / np.maximum(binary.sum(axis=0), 1))
    scores = tf * idf
    longer: dict[int, list[int]] = {j: [] for j in range(len(vocab))}
    for j, t in enumerate(vocab):
        for m, u in enumerate(vocab):
            if m != j and len(u) > len(t) and f" {t} " in f" {u} ":
                longer[j].append(m)
    out: dict[int, list[str]] = {}
    for ci, c in enumerate(clusters):
        size = int((lab == c).sum())
        need = min(2, size)
        chosen: list[str] = []
        for j in np.argsort(-scores[ci]):
            if scores[ci, j] <= 0:
                break
            if per_cluster[ci, j] < need:
                continue
            best = j
            for m in longer[j]:
                if per_cluster[ci, m] >= max(need, 0.7 * per_cluster[ci, j]) and (
                    len(vocab[m]) > len(vocab[best]) or per_cluster[ci, m] > per_cluster[ci, best]
                ):
                    best = m
            term = vocab[best]
            if _overlaps(term, chosen):
                continue
            chosen.append(term)
            if len(chosen) == top:
                break
        out[c] = chosen
    return out


# ---------------------------------------------------------------- checks


def listed_area_agreement(
    ids: Sequence[str], nbrs: list[list[tuple[int, float]]], listed: dict[str, list[str]], k: int = 5
) -> dict[str, float]:
    """How often a person's k nearest share a department-curated research area.

    Compared with the rate for all pairs, so 'lift' above 1 means the map puts
    people the department groups together closer than chance.
    """
    areas: dict[str, set[str]] = {}
    for name, members in listed.items():
        for m in members:
            areas.setdefault(m, set()).add(name)
    have = [i for i, pid in enumerate(ids) if pid in areas]
    if len(have) < 2:
        return {"people": len(have), "precision": 0.0, "chance": 0.0, "lift": 0.0}
    hits = total = 0
    for i in have:
        for j, _ in [x for x in nbrs[i] if ids[x[0]] in areas][:k]:
            total += 1
            hits += bool(areas[ids[i]] & areas[ids[j]])
    pairs = [(a, b) for ai, a in enumerate(have) for b in have[ai + 1 :]]
    chance = sum(bool(areas[ids[a]] & areas[ids[b]]) for a, b in pairs) / len(pairs)
    precision = hits / max(total, 1)
    return {"people": len(have), "precision": precision, "chance": chance, "lift": precision / max(chance, 1e-9)}
