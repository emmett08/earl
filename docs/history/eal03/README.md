# EAL/0.3 experiment plans

These plans document the experiments reported in [EAL/0.3 model results](../../eal03-model-results.md). Their original bytes, names, host modes and relative paths are preserved:

| Plan | Original repository path |
|---|---|
| [Repeated matrix](eal03-matrix.json) | `benchmarks/experiments/eal03-matrix.json` |
| [Development ablation](eal03-development-ablation.json) | `benchmarks/experiments/eal03-development-ablation.json` |

The relative paths describe the original layout. The `legacy` host mode belongs to that historical implementation. Reconstructing those experiments requires the recorded EAL/0.3 code and frozen source inputs; these files are outside the current runnable-plan directory. The [result archive](../../../benchmarks/results/2026-09-23-eal03/index.json) retains exact inputs, implementation hashes, trial traces and recorded outcomes.

Use the current [EAL/2 matrix](../../../benchmarks/experiments/eal2-regression-matrix.json) or [EAL/2 development ablation](../../../benchmarks/experiments/eal2-development-ablation.json) with the [current runner](../../model-evaluation.md). Both use previously exposed tasks. New runs measure the current implementation and must retain their own inputs and results.
