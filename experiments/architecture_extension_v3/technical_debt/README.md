# Conditional technical-debt calculation

This command evaluates equation (2) of the user-supplied *A language-agnostic cost model of technical debt in software and infrastructure as code*. It is a deterministic calculator for a declared scenario:

\[
D_H(a\mid r)=\delta^H P+g_H(\delta)
\left[c_a^{\mathsf T}(I-B_a)^{-1}M_a\lambda
-c_r^{\mathsf T}(I-B_r)^{-1}M_r\lambda+\ell_a-\ell_r\right],
\qquad g_H(\delta)=\sum_{t=0}^{H-1}\delta^t.
\]

`a` is the assessed implementation and `r` an attainable reference that delivers the same required service. `lambda` is a common period-integrated external change demand, `M` maps demand to initial work, `B[i,j]` is directly induced type `i` work per type `j` parent, `c` is cost per work unit, and `ell` is separately attributed period cost. `P` is the specified transition expenditure at period `H`; `delta` discounts one period. `J` is the signed bracketed carrying difference. The model attributes each root cohort's full expected work to its initiation period. It assumes linear and stationary first moments, nonnegative work/cost inputs, globally subcritical propagation, no double counting, and a feasible reference and remedy. The calculator cannot establish those external conditions.

## Input and status

`scenarios/attached-synthetic.json` transcribes the paper's **stipulated** matrices, demand and prices. Its result is a numerical implementation check, not a field measurement. `scenarios/incomplete-empirical.json` declares the v3 fulfilment system but leaves unmeasured demand, work propagation, costs and remediation blank. It deliberately omits `candidate_sha256`, because no candidate-bound maintenance ledger has been collected. An empirical estimate also requires the candidate digest in the EAL assessment context, and a matching digest in its scenario. The incomplete record returns `status: not_estimable` and sorted `missing_fields`, without `J` or `D_H`. This is a successful observation of a specified input gap; it supplies neither a zero cost nor a negative debt finding.

The scenario schema is `technical-debt-scenario/1`. Top-level fields are exactly `schema`, `basis`, `boundary`, `demand_categories`, `lambda`, `actual`, `reference`, `remediation` and optional `candidate_sha256`; unexpected fields are errors. `basis` is `synthetic`, `hypothetical` or `empirical`. The boundary declares `system`, `required_service`, `reference`, `period`, `currency`. Each implementation has its own `work_categories`, `M`, `B`, `c`, `ell`. The remedy declares `P`, `H`, `delta`. Null or omitted required fields yield `not_estimable`; malformed supplied values, incompatible dimensions, unstable matrices and digest mismatches are errors. The status `estimated` means the *conditional arithmetic* was completed from supplied values, regardless of basis. It does not mean that empirical coefficients were statistically identified or forecasts validated. A purported empirical input record needs independent provenance and held-out validation before it can support a real debt claim.

The EAL command reads a JSON request on stdin containing `evidence_id`, `environment`, `tool: technical_debt`, `tool_version: 1`, `input: {scenario_path, expected_sha256}` and context `{experiment: architecture-extension-v3, stage: post-B}` with optional candidate SHA-256. It returns the standard `value`, `observed_at`, `context`, `request`, `details` envelope. Paths are confined to this directory's `scenarios/`; the file bytes must match the expected SHA-256. The tool and both exemplar files are pinned in [`eal-tools.toml`](eal-tools.toml). The EAL file declares opposed `estimated` and `not_estimable` predicates on the **same** empirical tool query, plus a separate synthetic arithmetic observation. Its missing-input objection concerns a candidate-specific projection route. It leaves the architecture mechanism logically open.

## Arithmetic and bounds

The command parses JSON decimal numbers without binary floating-point loss and solves `(I-B)w=1` and `(I-B)x=M lambda` using exact rational Gaussian elimination. For nonnegative `B`, a positive `w` yields the certificate `max_i (Bw)_i/w_i < 1`, so the spectral radius is below one. Acyclic matrices with a row sum above one remain admissible. The bare `--scenario` result includes exact solve residuals, the positive witness, exact rational quantities and finite decimal approximations. The MCP observation omits the large exact fractions and witness vector, reports the certificate bound and zero residual, and includes `audit_sha256` of the complete result; replaying `--scenario` recovers the full audit. The exact arithmetic checks the *supplied* model; it does not supply confidence intervals for estimated parameters.

Limits: up to eight work and eight demand categories, 65,536 input bytes, 18 decimal places, each nonnegative input at most one billion, `H` from 0 through 120, `0 < delta <= 1`, and output magnitudes at most one quadrillion. Larger scenarios require a separately tested numerical backend and stability/error controls. The runner has a 30-second timeout and a 65,536-byte output cap in the TOML binding.

## Verify

From the repository root with the project's Python dependencies installed:

```bash
python3 -m unittest experiments/architecture_extension_v3/technical_debt/test_tool.py -v
python3 experiments/architecture_extension_v3/technical_debt/tool.py --scenario experiments/architecture_extension_v3/technical_debt/scenarios/attached-synthetic.json
python3 experiments/architecture_extension_v2/mcp_roundtrip.py \
  --source experiments/architecture_extension_v3/technical_debt/debt-model.eal \
  --registry experiments/architecture_extension_v3/technical_debt/eal-tools.toml \
  --context '{"experiment":"architecture-extension-v3","stage":"post-B"}' \
  --goal empirical_estimate_unavailable --compile-aspic \
  --output /tmp/debt-model-mcp-demo.json
```

The attached synthetic scenario gives `J` approximately £3,365.44 and `D_H` approximately £50,601.15 for 12 monthly periods under its price convention. Ten tests cover that arithmetic, horizon and discount boundaries, signed values, unstable and acyclic propagation, representation invariance, malformed input, missingness and EAL envelope acquisition. The [MCP demonstration summary](mcp-demonstration.json) contains hashes and statuses only; [the compressed wire record](mcp-demonstration.json.gz) retains the full 15-message exchange. In that run the empirical estimate predicate was unavailable, the positive `not_estimable` predicate was available, and ASPIC+ accepted the input-gap claim. The fact of a missing input blocks an empirical reduction estimate, while synthetic arithmetic does not replace the missing observations.

For a field measurement, record dated root change cohorts, attributed initial and parent-to-child work episodes, complete follow-up, time and compute costs, the actual and reference service contract, and a feasible remedy estimate. Fit on earlier cohorts and test cost predictions on held-out changes. A directly measured paired carrying-cost difference is preferable when the individual entries of `B` cannot be identified. Report parameter and structural uncertainty separately from the exact solver residual.
