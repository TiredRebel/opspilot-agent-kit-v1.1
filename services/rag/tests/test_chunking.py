from app.retrieval import chunk_text


def test_chunk_500_overlap_50_stable_ordering():
    words = [f"w{i}" for i in range(1100)]
    text = " ".join(words)

    chunks = chunk_text(text)

    assert all(chunk.strip() for chunk in chunks)  # no empty chunks
    parsed = [chunk.split() for chunk in chunks]
    assert parsed[0] == words[0:500]
    assert parsed[1] == words[450:950]
    assert parsed[2] == words[900:1100]


def test_chunk_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_short_text_returns_single_chunk():
    assert chunk_text("just a few words") == ["just a few words"]
