# Independent calibration-key review

The frozen key is internally intact and every documented coverage family is present. Twenty-two complete label pairs are uncontroversial under the embedded rubric. Two individual labels are potentially disputable, so this review cannot endorse the key as uniquely determined gold for a perfect 24/24 decision and 24/24 consistency qualification gate.

This judgement was reached before inspecting any coder answer or participant outcome. The reviewer did not author the fixtures and read only the four authorized files. A subordinate reviewer read only the public bundle, did not see the key, and independently identified the same two alternatives. No public text, expected label, rationale, threshold or protocol was changed.

## Gold disputes

- **IKR-001 — `af0a5d7128444e9280a1cb6e1f8ec0a0`, decision.** “The device should be ready.” reasonably supports frozen `ambiguous`, but `ready` is defensible as a tentative affirmative expectation. The rubric says modal wording “may remain ambiguous”; it does not mandate when bare “should” is ambiguous. `no_explanation` is secure.

- **IKR-002 — `a9ac02cce4344667afa5adfdb36ce8ff`, consistency.** The frozen `ambiguous` consistency is supportable because the relation between the unresolved failure branch and “possibly ready” is open. `consistent` is also defensible because the explanation qualifies the uncertainty and asserts neither branch as an actual conflicting current verdict. The rubric does not distinguish coherent explanation of uncertainty from unresolved consistency across possible underlying verdicts. Decision `ambiguous` and the presence of explanatory content are secure.

These are pre-outcome semantic defects, not proposed outcome-driven replacements. Under the frozen repair rule, retain the exercise and any original attempts, suspend using it as definitive qualification, clarify the rubric prospectively, and create a fresh independently authored held-out set. Do not relabel this key, delete disputed items, relax the threshold, or turn an existing failure into a pass. No coder pass/fail is established here.

## Absence and intentional ambiguity

The schema has `no_answer` for decision absence and `no_explanation` for explanatory-content absence; it has no `nocontent` code. Both modal examples discuss readiness and therefore differ from “Please resend the question” (`no_answer/no_explanation`). The bare modal has no reason and warrants `no_explanation`; the possibly-ready item has explanatory content and cannot be `no_explanation`. The bare JSON ready field is `ready/no_explanation`. Thus absence is distinguished from ambiguity even though the two labels above are disputed.

## Integrity and coverage

All checks passed: exact frozen public/key/rubric hashes; 24 unique items and matching ordered IDs; each text hash; all example quotes as exact substrings; and blank public coding fields. The decision distribution is ready 6, not_ready 5, undetermined 6, ambiguous 6, no_answer 1. Consistency distribution is consistent 16, contradictory 4, ambiguous 1, no_explanation 3.

All coverage families stated in the method note are represented: current prose/JSON decisions; current JSON/prose and prose/prose conflicts; historical and hypothetical opposites; unknown withholding including the parenthetical lexical collision; known mandatory failure with another unknown; bare and explanatory modal uncertainty; absent task decision; bare decision; and wrong-fact but internally coherent ready, not_ready and undetermined examples. Private fictional facts were used only to verify that adverse examples exist, never to recode communicated semantics. External governing controls and referenced source/task documents were not read, so their independent completeness is outside this review.

## Exact source hashes

| Authorized file | SHA-256 |
|---|---|
| `public-items.json` | `6d9cd2237fda9c59d89799e0724248b6166bb8d1b98777078a1bcbd81acd16b1` |
| `sealed-key.json` | `340703654d79615c988a39536b0183989d5a476c0c35a5b658f932050ecb1d17` |
| `calibration-protocol.json` | `19de0898733652f721573311b06d1558f246e14285ceb111ffc0441c6c88f942` |
| `method-quality-note.md` | `09d625b3bece53497e87b933e3aee3d66f9fdce9314edba0afb6edf954a7ed57` |
| Embedded rubric UTF-8 | `fcffc6cf26a818ed6224970358d688518ea1913b618da373d3e34d45559665d1` |

## Each-ID review

| ID | Frozen decision / consistency | Review |
|---|---|---|
| `a7f37e56f26b417493186fb0fb8b11f1` | `undetermined` / `consistent` | Supported. The answer expressly identifies a current undetermined verdict and distinguishes missing evidence from a failed requirement. Its explanation supports that distinction. |
| `35c02765c9374514bad94d50af6ee228` | `undetermined` / `consistent` | Supported. Readiness is conditional on a future missing reading; the actual current verdict is expressly undetermined. The hypothetical affirmative clause does not contradict it. |
| `e326a6fd45ba4015b1fb2c655d6bf9e8` | `ready` / `consistent` | Supported. The negative verdict is expressly hypothetical and unoccurred. The current ready conclusion is supported by the asserted satisfaction of all present requirements. |
| `b718f91fa3c9419ebeba12a4488f3970` | `not_ready` / `consistent` | Supported. The explicit current not_ready verdict and explanation of a failed mandatory test communicate the same negative conclusion. |
| `16729b20f5024b22b9c355868023e806` | `ambiguous` / `contradictory` | Supported. The ready JSON field and not_ready prose are expressly retained as simultaneous current conclusions. Their incompatibility makes the whole answer ambiguous and the explanation contradictory. |
| `d89682b464094c64a25495ff7b452db9` | `ready` / `consistent` | Supported. The earlier not_ready verdict is expressly superseded after repair. The present ready verdict has a current passing-check explanation. |
| `b6bd208c823a45f3b1b7a0f34a03d6f2` | `not_ready` / `consistent` | Supported. The not_ready field and explanation of a current mandatory failure agree. No incompatible present claim is made. |
| `84e09289666c44988d3b68cde77c2b68` | `undetermined` / `consistent` | Supported. The answer expressly cannot establish current readiness owing to unavailable evidence; undetermined is supported without an asserted criterion failure. |
| `80f48b664a174a24a6c03e43dd585e89` | `not_ready` / `consistent` | Supported. The answer explicitly communicates not_ready and a failed-requirement explanation that supports it internally. The private fictional actual measurement cannot change semantic labels. |
| `e73602e686b941a3913ace298f6e0fcc` | `ready` / `consistent` | Supported. The explicit current ready conclusion and asserted satisfaction of all requirements agree. |
| `388728a3ed234c7783e7587540d4ffa1` | `ambiguous` / `contradictory` | Supported. Two incompatible current conclusions are simultaneously retained in prose. Decision ambiguity and explanatory contradiction are directly supported. |
| `4098dff0dea549cfa99b5b036af23b44` | `not_ready` / `consistent` | Supported. A current not_ready verdict is expressly based on a known mandatory failure. An additional unknown check is acknowledged without reversing that verdict. |
| `af0a5d7128444e9280a1cb6e1f8ec0a0` | `ambiguous` / `no_explanation` | Decision disputable; consistency supported. Ambiguous is a reasonable interpretation of the bare modal should, but the rubric says tentative modal wording may remain ambiguous rather than requiring that treatment. Reading this as an expected affirmative readiness conclusion makes ready defensible. No explanatory reason accompanies either reading. |
| `a031f2ae69674b5193c92f6949817da7` | `no_answer` / `no_explanation` | Supported. Requesting the question again communicates no readiness decision and supplies no explanation of a verdict. This is distinct from tentative readiness wording. |
| `44d20fa3b9bf42b3baba9002e39f1bf7` | `ready` / `consistent` | Supported. The answer explicitly communicates ready and an internally coherent passing-requirement explanation. Its private fictional false measurement is outside this rubric. |
| `987a814a45f24ce8ab07d9e78ff125a3` | `undetermined` / `consistent` | Supported. The parenthetical undetermined and full explanation define practical withholding as inability to establish readiness and expressly exclude a known failure. The isolated not ready phrase does not establish an incompatible criterion verdict. |
| `d56b2b97450640939eea189507f69a27` | `not_ready` / `consistent` | Supported. The historical ready conclusion is expressly superseded. The current mandatory failure supports the current not_ready conclusion. |
| `a9ac02cce4344667afa5adfdb36ce8ff` | `ambiguous` / `ambiguous` | Decision supported; consistency disputable. Unresolved failed-requirement versus unknown-readiness meanings support an ambiguous decision. There is explanatory content. Ambiguous consistency is supportable if the unresolved branch leaves its relation to possibly ready open; consistent is also defensible because the explanation describes and qualifies that uncertainty without asserting either incompatible branch as the actual conclusion. The rubric does not settle these competing applications. |
| `19a346cef64d4ff0b0df66de226688b1` | `undetermined` / `consistent` | Supported. The undetermined field and missing-record explanation agree internally. The private fictional record actually being present concerns factual correctness, not communicated decision or internal consistency. |
| `5c95ac346bef4741a82e9fd990469cf0` | `undetermined` / `consistent` | Supported. The undetermined field and express inability to establish readiness from a missing current reading agree. |
| `aa35c8180e124879ab462dfdd9e03e1d` | `ambiguous` / `contradictory` | Supported. An undetermined field and explicit current failed-criterion not_ready explanation are both retained; the explanation excludes the unknown-only reading. Whole-answer ambiguity and contradiction are supported. |
| `3b8c241efbb9431aa048d00925bcfebd` | `ambiguous` / `contradictory` | Supported. The not_ready field and ready explanation are both expressly current and neither supersedes the other. They support whole-answer ambiguity and explanatory contradiction. |
| `0d4ab7dfc2cb446698bf297c50fefe3d` | `ready` / `consistent` | Supported. The ready field and current passing-check explanation support the same current affirmative conclusion. |
| `6935a273464240a8a6cec9b052bcfb50` | `ready` / `no_explanation` | Supported. A bare ready decision field communicates an affirmative verdict but has no explanatory content. |

The JSON companion records each item’s exact supporting full-answer quote, text hash, alternatives and detailed disposition.
