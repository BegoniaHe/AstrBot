import json
from types import SimpleNamespace

import pytest

from astrbot.core.db.vec_db.base import Result
from astrbot.core.knowledge_base.retrieval.rank_fusion import RankFusion
from astrbot.core.knowledge_base.retrieval.sparse_retriever import SparseResult


@pytest.mark.asyncio
async def test_rank_fusion_prefers_sparse_payload_when_identifier_overlaps():
    fusion = RankFusion(kb_db=SimpleNamespace(), k=60)
    dense_results = [
        Result(
            similarity=0.9,
            data={
                "doc_id": "chunk-1",
                "metadata": json.dumps(
                    {
                        "chunk_index": 9,
                        "kb_doc_id": "doc-dense",
                        "kb_id": "kb-dense",
                    }
                ),
                "text": "dense text",
            },
        )
    ]
    sparse_results = [
        SparseResult(
            chunk_id="chunk-1",
            chunk_index=1,
            doc_id="doc-sparse",
            kb_id="kb-sparse",
            content="sparse text",
            score=0.8,
        )
    ]

    fused_results = await fusion.fuse(dense_results, sparse_results, top_k=1)

    assert len(fused_results) == 1
    assert fused_results[0].doc_id == "doc-sparse"
    assert fused_results[0].kb_id == "kb-sparse"
    assert fused_results[0].content == "sparse text"


@pytest.mark.asyncio
async def test_rank_fusion_uses_dense_metadata_when_sparse_result_missing():
    fusion = RankFusion(kb_db=SimpleNamespace(), k=60)
    dense_results = [
        Result(
            similarity=0.9,
            data={
                "doc_id": "chunk-2",
                "metadata": json.dumps(
                    {
                        "chunk_index": 3,
                        "kb_doc_id": "doc-2",
                        "kb_id": "kb-2",
                    }
                ),
                "text": "dense fallback text",
            },
        )
    ]

    fused_results = await fusion.fuse(dense_results, [], top_k=1)

    assert len(fused_results) == 1
    assert fused_results[0].chunk_id == "chunk-2"
    assert fused_results[0].chunk_index == 3
    assert fused_results[0].doc_id == "doc-2"
    assert fused_results[0].kb_id == "kb-2"
    assert fused_results[0].content == "dense fallback text"
