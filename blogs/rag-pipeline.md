---
title: Building a RAG pipeline that doesn't hallucinate
date: 2026-06-12
tags: RAG, LLMs, Retrieval, Evals
description: The retrieval layer matters more than the prompt. How I structure chunking, reranking, and grounding checks.
---

Retrieval-augmented generation is deceptively easy to prototype and surprisingly hard to make trustworthy. The demo works on day one; the hallucinations show up in week three. Here's the architecture I've landed on for keeping a RAG system honest about what it actually knows.

## The problem with naive RAG

The default recipe — embed a query, pull the top **k** chunks, stuff them into the prompt — optimizes for *similarity*, not *relevance*. Those are not the same thing. A chunk can be semantically close to the question and still contain nothing that answers it, and the model will happily paper over the gap with something plausible.

> A model asked to answer from irrelevant context won't say "I don't know." It will invent. Your job is to make silence the easier path.

## The architecture

I treat retrieval as three distinct stages, each with a job the others can't do. Over-fetch broadly, then aggressively narrow before anything reaches the model.

- **Retrieve wide** — pull 8–12 candidates with hybrid (dense + keyword) search.
- **Rerank hard** — a cross-encoder scores each candidate against the query; keep the top 3–4.
- **Ground the answer** — verify every claim is supported before returning it.

## Grounding checks

The last stage is the one most pipelines skip. After generation, I check that the response is actually entailed by the retrieved context — if it isn't, the system abstains instead of guessing.

```python
def answer(query):
    docs = retriever.search(query, k=8)
    docs = reranker.rank(query, docs)[:4]
    resp = llm.generate(query, context=docs)

    if not grounded(resp, docs):
        return "I don't have enough context to answer."
    return resp
```

In practice, an abstention rate of 5–10% on hard queries is a feature, not a bug. Users trust a system that occasionally says "I'm not sure" far more than one that's confidently wrong.

## Takeaways

1. Similarity is a candidate generator, not a ranker.
2. Reranking buys you more than a bigger embedding model.
3. Let the system abstain. Honesty is the whole product.
