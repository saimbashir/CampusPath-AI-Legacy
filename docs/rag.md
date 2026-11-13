# Course-grounded retrieval

Document text is divided into located chunks; a long passage may overlap by 200 characters. Actual source locations are preserved. PPTX citations come from actual slide numbers; the sample A* content is on slide 18. Empty evidence yields an explicit no-evidence response.

Default retrieval is BM25-like lexical ranking. It is not an embedding model. Optional `CompatibleEmbeddings` and `QdrantStore` implement hosted vectors. Hybrid retrieval combines lexical and vector ranks with reciprocal-rank fusion. Qdrant receives an explicit authorized chunk-ID filter; returned IDs are checked against the SQL-authorized mapping a second time. Use a distinct collection for every database to prevent integer ID collisions across projects.

Generated tutoring is available through a configured compatible API. The Pydantic output schema requires an answer and existing source IDs. This validates structure and citation identity, not semantic faithfulness. A teacher must still assess educational correctness. Excerpts are framed as untrusted data in prompts, but prompt-injection robustness requires independent adversarial evaluation.

Semantic index errors do not lose uploaded text. Re-run `scripts/reindex_vectors.py`. The implementation performs indexing synchronously in the upload's worker thread; a durable background queue and index-health dashboard are not implemented.

`scripts/evaluate_retrieval.py` runs three labelled synthetic-course queries, reporting Precision@4, Recall@4 and latency. This is a reproducible smoke benchmark, not a statistically credible research evaluation. Real held-out course questions and manual relevance labels are required for research claims.

Provider API references: https://api.qdrant.tech/api-reference/points/upsert-points ; https://qdrant.tech/documentation/search/filtering/ ; https://developers.openai.com/api/reference/resources/embeddings/methods/create
