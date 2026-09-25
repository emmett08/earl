# One end-to-end GitHub Actions argument

**Question:** Did GitHub Actions report a successful `test` workflow run, including `make check` and `make build`, for exact main commit `a9cdabee643118ff3ae28b3ec5c346427cca8cad`?

[`source.eal`](source.eal) pins workflow ID `365107869`, path `.github/workflows/test.yml`, run ID `36133531512`, attempt 1, creation time `2026-09-25T12:11:37Z`, event `push`, branch `main`, job `test` and both named steps. Its claim reports **GitHub's status for that run**. A passing workflow cannot establish that the software is correct, that a later commit passed, or that EAL/2 is superior to another representation.

The operator's [`tools.toml`](tools.toml) binds `github_workflow/1` to the local [read-only collector](collect_workflow.py). EAL source supplies the pinned JSON input; it cannot supply executable paths, a URL or an HTTP method. The collector calls GitHub's [workflow run attempt](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt) and [attempt jobs](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt) GET endpoints. It also reads the current run before and after collection to reject an older attempt and a rerun during acquisition. It checks repository, workflow, commit, event, branch, run, attempt, creation time, every job page, required steps and job identities; a missing or failed step produces no positive support. Redirects, excessive responses and changed page counts fail collection. The EAL evaluator separately checks observation identity, maximum age (300 seconds), context and predicates.

## Live path

Install the package from the repository root (`python3 -m pip install -e '.[dev]'`). For a private repository, supply `GITHUB_TOKEN` through the host environment with repository Actions **read** permission. The token is not in source, TOML, the prompt or the collector output.

```sh
eal --workspace . --registry examples/workflow-gate/tools.toml validate examples/workflow-gate/source.eal
eal --workspace . --registry examples/workflow-gate/tools.toml collect examples/workflow-gate/source.eal \
  --context '{"repository":"emmett08/earl","decision":"workflow-result"}' > /tmp/workflow-collection.json
COLLECTION_ID=$(python3 -c 'import json; print(json.load(open("/tmp/workflow-collection.json"))["collection_id"])')
eal --workspace . --registry examples/workflow-gate/tools.toml reason examples/workflow-gate/source.eal \
  --context '{"repository":"emmett08/earl","decision":"workflow-result"}' \
  --collection "$COLLECTION_ID" > /tmp/workflow-assessment.json
ASSESSMENT_ID=$(python3 -c 'import json; print(json.load(open("/tmp/workflow-assessment.json"))["assessment_id"])')
eal --workspace . --registry examples/workflow-gate/tools.toml explain "$ASSESSMENT_ID" --claim workflow_passed
```

Check `claims.workflow_passed.status` in the assessment; the claimed result is supported only if the exact API response and EAL predicates pass. Collection failures are stored as error observations and cannot support the claim. Recollect for a later decision because the stored observation is time-bound.

The corresponding MCP path starts `eal-mcp --workspace . --registry examples/workflow-gate/tools.toml`, then calls `eal_validate(source)`, `eal_collect(source, context)`, `eal_reason(source, context, collection_id)`, and `eal_explain(assessment_id, claim="workflow_passed")`. The source text is the exact bytes of `source.eal`; the context is the JSON object above. The host retains the checked claim status independently of a model's explanation.

## Offline verification and provenance

```sh
python3 examples/workflow-gate/run.py --offline
```

This command checks a SHA-256 pinned [projection of actual GitHub API responses](receipt.json) fetched from the three exact URLs recorded in that file. The response identified one successful `test` job and successful `Run make check` and `Run make build` steps for run 36133531512 attempt 1. The projection retains only fields used by the collector. Its `projection_recorded_at` is the time the selected fields were written to this fixture, separate from the workflow's `updated_at` and the later assessment time.

The runner first executes the real CLI and a real MCP stdio client/server lifecycle using a temporary TOML binding that passes `--offline-receipt` explicitly. That adapter labels the observation `offline_receipt`; the live-only `source.eal` requires `live_api`, so **both checked claims are `unsupported`**. It then executes [`captured.eal`](captured.eal) through a separate [capture binding](capture-tools.toml) and SHA-256 checking [historical adapter](captured_workflow.py). This second source requires `captured_api` and limits its statement to the *retained projection*. With `now` set to the recorded projection time, its checked claim is **supported** through both CLI and MCP. That status concerns this historical capture; it says nothing about a later attempt, current branch head or a future release decision. The saved projection is not producer-authenticated by the file hash.

The local environment used to prepare this example could fetch the API responses through an authorised GitHub connector but could not make a direct HTTPS request from the Python collector. The live command above therefore needs execution on a networked host with the requisite repository permission. The example tests cover source validity, acquisition identity, rerun races, prior attempts, pagination, missing steps, failed jobs and both CLI/MCP paths. They do not report any model comparison.
