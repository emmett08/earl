# Reference checks

Primary sources consulted on 25 September 2026. The bibliography cites the publication metadata; author-hosted PDFs provide accessible full text where indicated. Claims are limited to the inspected material. No citation is used as evidence of an EAL experimental advantage.

| Key | Source and inspected location | Supported use |
| --- | --- | --- |
| `dung1995` | [Full paper](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/dung95acceptability.pdf), Definitions 6, 16 and 20; Theorem 25. DOI `10.1016/0004-3702(94)00041-X`, Artificial Intelligence 77(2), 321–357. | Abstract attack relations and grounded acceptance. The composed EAL rules are specified separately. |
| `modgil2014` | [Author tutorial](https://webspace.science.uu.nl/~prakk101/pubs/ASPICtutorial.pdf), introduction and Section 3.1; publication DOI `10.1080/19462166.2013.869766`, Argument & Computation 5(1), 31–62. Author draft dated December 2013, journal publication 2014. | Strict/defeasible rules, attacks and preferences; no assertion of full ASPIC+ conformance. |
| `omg2023` | [Official SACM 2.3 metadata](https://www.omg.org/spec/SACM/2.3/About-SACM) and [specification](https://www.omg.org/spec/SACM/2.3/PDF), Section 1, scope. October 2023, formal/23-05-08. | Assurance argument and evidence representation/interchange. No assertion that all SACM implementations lack execution. |
| `gao2023` | [PMLR record](https://proceedings.mlr.press/v202/gao23f.html) and [paper](https://proceedings.mlr.press/v202/gao23f/gao23f.pdf), introduction and method. PMLR 202, 10764–10799. | Generated-program delegation to an interpreter. No imported performance number. |
| `pan2023` | [ACL record](https://aclanthology.org/2023.findings-emnlp.248/) and [paper](https://aclanthology.org/2023.findings-emnlp.248.pdf), Section 3. DOI `10.18653/v1/2023.findings-emnlp.248`. | Formalisation, symbolic solving and interpretation; correctness remains conditional on representation. |
| `raspanti2025` | [ACL record](https://aclanthology.org/2025.acl-industry.34/) and [paper](https://aclanthology.org/2025.acl-industry.34.pdf), Sections 3–5. DOI `10.18653/v1/2025.acl-industry.34`, pp. 485–499. | Grammar-constrained logical parsing, distinguished from this pilot's fixed-source protocol. |
| `parr2009` | [Publisher record](https://pragprog.com/titles/tpdsl/language-implementation-patterns/) and [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf). ISBN 9781934356456. | Conventional separation of language implementation concerns. No endorsement or comparative empirical claim. |
| `mcp2025` | [Official Tools specification, revision 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). | Protocol tool interaction; EAL-specific assessment semantics are attributed to the implementation. |

Repository claims were checked against `docs/` and source/tests, rather than inferred from bibliography titles. Bibliographic identifiers and exact author lists for the two ACL papers and PAL were checked against their primary publication records. The reference set is deliberately limited to sources actually used; a broader literature review may be appropriate after an editor identifies the preferred JSS article category.

## Nano follow-up primary artefact

The later empirical claims use the supplied archive for [Actions run 36176588712](https://github.com/emmett08/earl/actions/runs/36176588712), attempt 1. SHA-256: `186adeb144ccaf4c77f5e36165999f3ad203a98bcfc24a7119c68d5c5eb206c5`. Its manifest pins plan 3.1.0 and source commit `8220e838a8d42922edc0496ff50927c672a1f87d`. The eight files in `analysis/nano_v3_original/` match the manifest's source digests. The curated projection retains case rows, all 240 assignments, response text, protocol errors, model-visible packets and complete tool receipts. Original provider object duplicates and replay handles are omitted.

`analysis/reproduce_nano.py` independently recomputes the reference and each attempted grade using the frozen oracle, verifies model-visible packets against raw rows and reproduces the original summary exactly. This verifies the numerical account against the retained artefact. It does not supply independent replication or identify the causal effect of changing prompts, transport or retry rules. No additional literature source is used to explain the observed nano failures.
