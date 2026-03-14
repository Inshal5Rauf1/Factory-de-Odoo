"""E2E integration tests for DEBT-02: ChromaDB index pipeline.

These tests verify the ChromaDB embedding and index pipeline works end-to-end
WITHOUT sentence-transformers or torch. Tests that require GitHub API access
are skipped when GITHUB_TOKEN is not available.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

skip_no_token = pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set -- skipping e2e index tests",
)


@pytest.fixture(scope="module")
def e2e_index_db(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Build a real OCA index in a temporary directory (module-scoped).

    Calls build_oca_index() against the real OCA GitHub org.
    Returns the db_path string for tests to use.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set -- cannot build e2e index")

    from amil_utils.search.index import build_oca_index

    db_path = str(tmp_path_factory.mktemp("e2e_index_chromadb"))
    build_oca_index(token=token, db_path=db_path)
    return db_path


def test_sentence_transformers_not_installed() -> None:
    """Sentinel: verify sentence-transformers is NOT in the environment.

    Guards against accidental re-addition of the dependency. If this test
    fails, sentence-transformers was added back to [search] extras.
    """
    with pytest.raises(ImportError):
        import sentence_transformers  # noqa: F401


def test_chromadb_onnx_embedding_without_sentence_transformers(
    tmp_path: Path,
) -> None:
    """Verify ChromaDB's built-in ONNX embedding works without sentence-transformers.

    Creates a PersistentClient, creates a collection, upserts a document,
    queries it, and asserts results come back. This proves ChromaDB's ONNX
    all-MiniLM-L6-v2 model works independently of torch/sentence-transformers.
    """
    chromadb = pytest.importorskip("chromadb", reason="chromadb not installed")

    db_path = str(tmp_path / "test_onnx_chromadb")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name="test_onnx_collection",
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert some documents
    collection.upsert(
        ids=["doc1", "doc2", "doc3"],
        documents=[
            "Odoo sale order management and invoicing",
            "Warehouse stock inventory tracking",
            "Human resources employee management",
        ],
    )

    # Query for a related concept
    results = collection.query(
        query_texts=["sales invoice"],
        n_results=2,
    )

    assert results["ids"] is not None
    assert len(results["ids"][0]) > 0, "Expected at least one result from ONNX query"
    # The sale-related document should be returned
    assert "doc1" in results["ids"][0], (
        f"Expected doc1 (sale order) in top results, got {results['ids'][0]}"
    )


@skip_no_token
def test_build_index_creates_persistent_db(e2e_index_db: str) -> None:
    """Verify build_oca_index creates a persistent ChromaDB directory with files."""
    db_path = Path(e2e_index_db)
    assert db_path.exists(), f"Expected db_path to exist: {db_path}"

    # ChromaDB PersistentClient creates files in the directory
    files = list(db_path.rglob("*"))
    assert len(files) > 0, "Expected ChromaDB to create files in the db directory"


@skip_no_token
def test_index_status_after_build(e2e_index_db: str) -> None:
    """Verify get_index_status reports correct metadata after a real build."""
    from amil_utils.search.index import get_index_status

    status = get_index_status(db_path=e2e_index_db)
    assert status.exists is True, "Expected index to exist after build"
    assert status.module_count > 0, (
        f"Expected module_count > 0, got {status.module_count}"
    )
    assert status.last_built is not None, "Expected last_built timestamp to be set"
    assert status.size_bytes > 0, (
        f"Expected size_bytes > 0, got {status.size_bytes}"
    )


@skip_no_token
def test_search_relevance_ordering(e2e_index_db: str) -> None:
    """Verify search for 'sale order' returns sale-related modules ranked high."""
    from amil_utils.search.query import search_modules

    results = search_modules("sale order", db_path=e2e_index_db)
    assert len(results) > 0, "Expected at least one search result for 'sale order'"

    # The top result should be semantically related to sales
    top = results[0]
    sale_related = (
        "sale" in top.module_name.lower()
        or "sale" in top.summary.lower()
        or "sale" in top.document_text.lower()
    )
    assert sale_related, (
        f"Expected top result to be sale-related, got: "
        f"module_name={top.module_name!r}, summary={top.summary!r}"
    )
