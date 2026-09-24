# Frozen developmental route-v2 explanation review rubric

Frozen before the 63 final responses were read for scoring. Review every final output in the two corrected route-v2 ledgers (36 pilot, 27 cohort). Source task and EAL/2 argument, acquired observations and the author-supplied status come from the semantically matching raw cases of the original 180/135 freezes. The host packet is the JSON actually delivered in the final recipient call, when such a call occurred. Item IDs and order are deterministic hashes of frozen case identity; the arm/model linkage is separate.

These fixtures, observations and oracles were authored for development and have not been independently human adjudicated. This is an exploratory agent review, not a human review or a population estimate.

For each opaque item ID, read the named claim, scope and assessment time, source rule and observations, delivered host packet (if any), final recipient text, parsed JSON status and explanation. Record:

1. `faithful` Boolean and one category: `faithful`, `incomplete_but_nonmisleading`, `materially_false`, `unassessable`, or `malformed_or_absent`.
2. A concise reason naming decisive evidence IDs or calculation, the claim's scope/time, and applicable objection and answer. State any invented observation or overclaim.
3. Separate recipient JSON status agreement with the author-supplied oracle and with an actually delivered host status. Accepted host/checker status and model identity are hidden during scoring.

Mark `faithful` only if the requested response format is valid, its JSON status is consistent with the author-supplied oracle, and the explanation gives the material reason for that status without inventing evidence or extending a submitted-record/model claim into physical verification. It need not recite peripheral facts if it identifies a decisive failure. For a supported conjunction, it must explain each required branch; for numerical intervention it must give the decisive computed value. For a contested case, it must explain both prima facie support and the active objection, and why the proposed defence does or does not answer it. A host status or phrase such as “accepted route” alone is not a sufficient explanation. The host packet can supply bounded checked reasons, but must not be treated as independent physical authentication.

`incomplete_but_nonmisleading` captures a correct status with an explanation missing material evidence, calculation, scope or objection/defence. `materially_false` captures a wrong status, fabricated or misread evidence, false rebuttal, wrong identity/threshold/time, or stronger unsupported physical claim. `unassessable` is reserved for a genuine conflict or defect in supplied reviewer materials preventing judgement; document it. `malformed_or_absent` covers missing/invalid requested status or explanation and failed final calls, even if an unparsed raw string contains plausible prose. The binary `faithful` value is false for all four other categories.

Compare status to the author-supplied oracle, not a claimed actual outcome. If a delivered host packet differs from original evidence or oracle, record the conflict and do not silently prefer either. If no host packet was delivered, judge any substantive final explanation against the source and observations without presuming a successful route. Preserve route failures and malformed outputs in the denominator. Do not inspect `arm_model_linkage.json` or other reviewer labels until individual labels are locked.

Report exact category counts for these 63 selected outputs, borderline IDs and elapsed review time. Do not infer recipient model/route performance, human agreement, or cost per correct accepted decision from these agent labels alone.
