import numpy as np

from research_map.model import cluster_labels, leiden_areas, nearest, relabel_by_size, similarity
from research_map.text import Doc


def _blobs():
    rng = np.random.default_rng(0)
    a = rng.normal([5, 0, 0], 0.3, (10, 3))
    b = rng.normal([0, 5, 0], 0.3, (10, 3))
    v = np.vstack([a, b])
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_leiden_separates_two_groups():
    labels = leiden_areas(similarity(_blobs()), k=5, resolution=1.0)
    assert len(set(labels[:10])) == 1 and len(set(labels[10:])) == 1
    assert labels[0] != labels[10]


def test_nearest_excludes_self():
    nb = nearest(similarity(_blobs()), 3)
    assert all(i not in [j for j, _ in row] for i, row in enumerate(nb))
    assert all(j < 10 for j, _ in nb[0])


def test_relabel_by_size():
    assert relabel_by_size([5, 5, 2, 9, 9, 9]) == [1, 1, 2, 0, 0, 0]


def test_cluster_labels_prefer_distinctive_bigrams():
    docs = [Doc(str(i), {"keywords": "machine learning, neural networks"}) for i in range(3)]
    docs += [Doc(str(i + 3), {"keywords": "plant ecology, soil microbes"}) for i in range(3)]
    labels = cluster_labels(docs, [0, 0, 0, 1, 1, 1], top=3)
    assert "machine learning" in labels[0]
    assert "learning" not in labels[0]
    assert any("ecology" in t for t in labels[1])


def test_labels_prefer_longer_phrase_and_skip_names():
    docs = [Doc(str(i), {"keywords": "applied machine learning, robotics"}) for i in range(3)]
    docs += [Doc(str(i + 3), {"keywords": "plant ecology", "bio": "Instructor at a company."}) for i in range(3)]
    labels = cluster_labels(docs, [0, 0, 0, 1, 1, 1], names=["Rob Otics"])
    assert labels[0][0] == "applied machine learning"
    assert all("instructor" not in t and "company" not in t for t in labels[1])


def test_person_terms_drop_own_names():
    from research_map.model import person_terms

    docs = [Doc("a", {"bio": "Pisan studies games."}), Doc("b", {"bio": "Lee studies plants."})]  # thin: bio fallback
    terms = person_terms(docs, names=["Yusuf Pisan", "Ann Lee"])
    assert "pisan" not in terms[0] and "games" in terms[0]
