# Reviewed EAL/2 RAG candidate index

`RagCandidateIndex` ranks short, reviewed local source excerpts against a
question. It returns **family suggestions**, never an applicable case,
binding, claim, collection request or assessment. The host must bind the
original question and call `TaskApplicabilityRegistry.resolve_bound` for its
unique reviewed entry before it collects evidence. A high retrieval score cannot pass that
gate. A paraphrase of a reviewed question still requires a separate exact
task review entry.

The catalogue uses `eal2-rag-candidates/1`. Each document has an EAL
identifier and the exact fields shown below. The example digest is a
placeholder; generate it with `rag_review_digest` after creating and loading
the family and local source file.

```toml
schema = "eal2-rag-candidates/1"

[documents.field_note]
family_id = "rig"
case_review_contract_sha256 = "<reviewed family case digest>"
claim_id = "accepted"
source_path = "review-notes/field-rig.txt"
source_sha256 = "<SHA-256 of entire local UTF-8 source file>"
snippet = "Inspection of the field rig power breaker and contactor."
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "<rag_review_digest result>"

# Optional provider-neutral vector, generated and reviewed ahead of time:
# embedding_model_id = "selected-embedding-model/version"
# embedding = [0.12, -0.25, 0.31]
```

The snippet must occur byte-for-byte as Unicode text in the UTF-8 source
file. The catalogue must reside with that local source tree. Each source is
limited to 64 KiB; each excerpt is limited to 2 KiB and 256 searchable
words; the catalogue is limited to 128 documents. A source path cannot leave
the catalogue directory, including through a symbolic link. Loading and
searching verify the source digest, exact snippet, family case contract and
EAL artefact identity. The digest detects changed data; it does not prove
that the reviewer or source was trustworthy. The deployment must control
and authenticate the review process and corpus files.
The reviewer must also check that the excerpt concerns the pinned claim;
the digest cannot establish that semantic relation.

```python
from eal.rag import RagCandidateIndex

index = RagCandidateIndex.load(families, "reviewed/rag.toml")
candidates = index.search(
    original_task_text,
    authorised_families={"rig"},
    authorised_artifacts={"rig_field"},
    authorised_claims={"rig_field": {"accepted"}},
)
# Each result has a family_id, document_id, claim_id, source_path, reviewed_snippet,
# case review digest, advisory score and BM25/cosine signal values.

# The host can supply a query vector from its own embedding provider.
candidates = index.search(
    original_task_text,
    authorised_families={"rig"},
    authorised_artifacts={"rig_field"},
    authorised_claims={"rig_field": {"accepted"}},
    query_embedding=("selected-embedding-model/version", query_vector),
)
```

An application may instead inject an `embedder(question)` callback when
loading the index; it must return `(model_id, vector)` and keep provider
credentials in host configuration. The module itself makes no API calls.
An excerpt is returned only when the caller is granted its family, the
artefact selected by its exact reviewed case, and the document's pinned
claim on that artefact. The embedder is not called if no accessible vector
document exists.
Vectors have two to 512 finite components and a nonzero norm. A query vector
compares only with documents pinned to the same model identity and dimension.

## Optional OpenAI query embeddings

`OpenAIEmbeddingAdapter` is an opt-in synchronous callable using the official
[`POST /v1/embeddings` contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create).
It requests `encoding_format: "float"` and explicit `dimensions`; the API
supports the latter for `text-embedding-3` and later models. Construction,
module import and index loading make no request. The host invokes the adapter
only after it has found a document accessible under the caller's family,
artefact and claim grants.

```python
from eal.embeddings import OpenAIEmbeddingAdapter

def record_attempt(attempt):
    # Persist prompt_tokens, total_tokens and token_usage_complete, including
    # failed requests whose billed usage is unknown. Add configured pricing.
    usage_ledger.append(attempt)

embedder = OpenAIEmbeddingAdapter(
    model="text-embedding-3-small",
    dimensions=256,
    api_key_env="OPENAI_API_KEY",
    usage_callback=record_attempt,
)
index = RagCandidateIndex.load(families, "reviewed/rag.toml", embedder=embedder)
```

Set `OPENAI_API_KEY` in the host environment. The adapter reads it at call
time; it never puts the key or raw question into an accounting record. Each
sent request produces one `EmbeddingAttempt` with the model, dimension,
input SHA-256, outcome and measured token counts when the response supplied
valid usage. A failed HTTP request or malformed usage leaves token counts
unknown, not zero. A missing key fails before any request. The adapter checks
the returned model identity, single indexed float vector, requested dimension
and token usage. Its timeout, response size and input size are bounded;
redirects are disabled. A non-local endpoint requires HTTPS, and the URL
must end at `/v1/embeddings` without credentials or query parameters.

Generate and review corpus vectors ahead of deployment using the **same
explicit model and dimension**. Pin each vector and model ID in the RAG
manifest before use. A model name and digest of returned vector bytes do not
identify every internal model revision; retain the generation date and
original vector for a reproducible index. The command-line `--rag-catalogue`
route uses BM25 only; a Python host must inject this adapter explicitly.

Local BM25 uses word overlap; positive cosine similarity adds an optional
vector ranking. The index combines their **ranks** through reciprocal rank
fusion with constant 60, then returns the strongest document per authorised
family, with stable ties by document and family ID. An absent vector leaves
ordinary BM25 retrieval available. No lexical overlap and no positive cosine
similarity yield no candidate. A positive cosine value is not a calibrated
relevance probability; an unrelated vector may still nominate a document.
The returned excerpt is data for review, not an instruction to the host.
The host's task applicability gate remains decisive even for a sole or
apparently compelling suggestion.

For empirical evaluation, freeze the corpus, case reviews, query texts and
vector model; compare the existing lexical index, this BM25 index and the
BM25-plus-vector route on held-out questions. Record candidate recall at a
fixed limit, ambiguous and irrelevant candidates, abstentions, rank, latency,
embedding calls and cost. Run assessment outcomes separately through the
same exact-question gate and compare with an equivalently equipped JSON
route. These are proposed measurements, not results of this implementation.
