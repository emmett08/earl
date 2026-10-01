# Packaging and releases

The Python distribution is `engineering-argument-language` version `3.2.2`; its import package is `eal`. It supplies the Python API, the `eal`, `eal-mcp` and `eal-host` commands, and one FastMCP server configurable for stdio or Streamable HTTP. Python 3.11 or later is required. Runtime dependencies are declared in [pyproject.toml](../pyproject.toml) and installed by pip; development dependencies are separate.

## Install a distribution

Use a virtual environment. The commands below use a POSIX shell:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install ./engineering_argument_language-3.2.2-py3-none-any.whl
python -m pip check
eal --help
eal-mcp --help
eal-host --help
```

Supply the path to a downloaded workflow artefact or a wheel built from the reviewed source. A downloaded workflow archive includes `dist/` and `SHA256SUMS`; from its extracted root, run `shasum -a 256 --check SHA256SUMS` before installing a file under `dist/`. A source distribution can be installed with `python -m pip install ./engineering_argument_language-3.2.2.tar.gz`; pip installs the build requirements and builds its wheel. The committed generated ANTLR parser makes Java unnecessary for ordinary installation and parsing.

For a reviewed GitHub revision, substitute its full commit SHA for `FULL_COMMIT_SHA`:

```bash
python -m pip install \
  'engineering-argument-language @ git+https://github.com/emmett08/earl.git@FULL_COMMIT_SHA'
```

Git must be installed for this route. A pinned tag can replace the commit SHA after the maintainer creates that tag. For the first packaged release, the corresponding command is:

```bash
python -m pip install \
  'engineering-argument-language @ git+https://github.com/emmett08/earl.git@v3.2.2'
```

The tag command requires an existing `v3.2.2` tag. PyPI installation requires publication of that version; once published, use:

```bash
python -m pip install 'engineering-argument-language==3.2.2'
```

The wheel is pure Python. Command collectors require POSIX process groups and file descriptors; bounded custom reasoning methods require POSIX resource limits. The release workflow is configured to check distribution installation on Linux with Python 3.11–3.14 and macOS with Python 3.12. Other Python/platform combinations require separate validation for the features used. Workspace coordination covers participating processes on one local filesystem; distributed replicas and network filesystems require another coordinator. See [MCP and tools](mcp-and-tools.md) for execution limits and [MCP architecture](mcp-architecture.md) for acquisition ownership.

## Python integration

These are the documented application import paths:

| Import | Role |
| --- | --- |
| `from eal.knowledge import EALKnowledgeBase, ModelContextAdapter` | Register workspace source, assess exact claims and prepare bounded model messages |
| `from eal.runtime import ReasoningService` | Explicit validation, planning, acquisition, assessment and packet operations |
| `from eal.parser import parse` | Parse source into the typed program representation |
| `from eal.semantics import validate` | Check references, types and reasoning-method contracts |
| `from eal.formatter import format_source` | Produce canonical EAL/3 source |
| `from eal.evaluator import evaluate` | Assess supplied records with an explicit time and context |
| `from eal.methods import MethodContract, MethodRegistry, default_registry` | Construct and install trusted typed method contracts |
| `from eal.limits import ExecutionLimits` | Set host-owned execution budgets |

The [integration contract](../CONTRACT.md) defines signatures and result semantics. The [`EALKnowledgeBase` example](../README.md#assess-a-known-claim) registers a developer-authored file and binds tools through operator-owned TOML. Collection and assessment persist in the selected workspace. Supply an absolute workspace and registry path when embedding the host in an application with a different working directory.

Parsing and static validation can run independently of collection:

```python
from eal.parser import parse
from eal.semantics import validate
from eal.formatter import format_source

source = '''language "EAL/3"
environment staging {
  require cluster == "staging"
}
claim ready {
  statement "The service meets the declared readiness conditions."
  environment staging
}
'''
program = parse(source)
diagnostics = validate(program)
assert not diagnostics
canonical_source = format_source(source)
```

This example checks a declaration's syntax and references. An assessment needs its authored support routes and observations. Private helpers, generated-parser classes and database tables are implementation details; integration code uses the documented interfaces. Pin a reviewed package release and consult the current contract before upgrading. This project develops the current EAL/3 language without a backwards-compatibility guarantee.

Package `3.2.2` identifies this distributed implementation. `EAL/3` identifies source syntax and semantics. Schema identifiers describe different records: observations use `EAL/observation-record/1`, assessment packets use `EAL/assessment-packet/2`, and model messages use `EAL/model-context/2`. A packaging change does not itself revise those language or record contracts.

## Licence scope

The [Unlicense](../LICENSE) dedicates original EARL software to the public domain and supplies unrestricted permission to use, modify and redistribute it for commercial and non-commercial purposes, with the warranty terms stated in that file. The package metadata declares the SPDX expression `Unlicense` and includes the licence text in the wheel and source distribution.

Dependencies and any separately identified third-party or vendored material retain their own licences and notices. The root licence does not grant rights in cited publications, publisher templates, quotations, figures or other externally supplied materials. The wheel contains the runtime and licence materials; the source distribution also includes developer documentation, examples and experiment harnesses. The manuscript, annotations and separately stored experiment runs are excluded from both distributions. Check the relevant attribution and terms before redistributing third-party material from the repository or bundling runtime dependencies into another product.

The repository's `paper/elsarticle.cls`, `paper/elsarticle-num.bst` and LPPL-licensed classes and styles under `paper/vendor/` retain their LaTeX Project Public License 1.3-or-later terms and embedded notices. Their exclusion from the Python distributions preserves the original package licence scope.

## Develop and verify artefacts

From a source checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,release]'
make check
make build
make check-distribution
```

`make check` checks generated-parser consistency, investigation contracts, the test suite and the maintained synthetic example. Its parser check requires Java and the selected ANTLR generator. The generated Python parser is already committed.

`make check-distribution` invokes [the distribution checker](../scripts/check_distribution.py). It checks the wheel and source distribution, creates fresh virtual environments, installs each artefact, and exercises imports, installed commands and MCP outside the repository. The directory must contain one wheel and one source distribution for the same release. The checker accepts a distribution directory and `--expected-version VERSION`, allowing the release workflow to check the selected tag's package version. These installation checks need access to the configured package index for declared build and runtime dependencies.

## Publish manually

[publish.yml](../.github/workflows/publish.yml) runs only through `workflow_dispatch`. Its inputs are `release_tag` and `destination`, with destination choices `verify`, `testpypi` and `pypi`; `verify` is the default. The owner creates the release tag under the repository's tag ruleset. The workflow reads repository references and publishes verified artefacts using a PyPI API token for production or OpenID Connect for TestPyPI.

Production publication uses the GitHub environment `pypi.org` and its `PYPI_TOKEN` secret. The PyPA action authenticates with the literal username `__token__` and that token as its password; the account username identifies the token owner. Production attestations are disabled because the action generates them through Trusted Publishing. TestPyPI uses the separate `testpypi` environment, a configured Trusted Publisher and signed attestations.

The initial release procedure is:

1. Merge the reviewed packaging change. Ensure `pyproject.toml` and `eal.__version__` agree on `3.2.2`, then create `v3.2.2` at that reviewed commit on `main`.
2. Store a PyPI API token with permission to publish `engineering-argument-language` as the `PYPI_TOKEN` secret in the repository environment `pypi.org`. Configure that environment to permit release tags and apply any required deployment reviewers. For optional TestPyPI publication, configure its Trusted Publisher for project `engineering-argument-language`, GitHub owner `emmett08`, repository `earl`, workflow `publish.yml` and environment `testpypi`, then configure that environment's deployment rules. A new TestPyPI project uses a pending publisher; its publisher registration is separate from production token authentication.
3. Dispatch the workflow from the `v3.2.2` tag, with `release_tag=v3.2.2` and `destination=verify`, using the GitHub CLI command below. The workflow must first exist on the default branch. It requires a stable `vMAJOR.MINOR.PATCH` tag, checks its resolved commit and package version, and requires that commit to belong to `main`'s history.
4. Review the full check and artefact installation results, and download the retained wheel and source distribution. If TestPyPI is configured, dispatch from the same tag with `destination=testpypi` to exercise its publication path and check that release.
5. Dispatch from the same tag with `destination=pypi` to publish the production release. Publication begins after all required verification jobs and the `pypi.org` environment's deployment rules pass.

Dispatch verification with the matching tag ref and input:

```bash
gh workflow run publish.yml --repo emmett08/earl --ref v3.2.2 \
  -f release_tag=v3.2.2 -f destination=verify
```

After verification and authentication setup, dispatch the optional TestPyPI release and the production PyPI release:

```bash
gh workflow run publish.yml --repo emmett08/earl --ref v3.2.2 \
  -f release_tag=v3.2.2 -f destination=testpypi
gh workflow run publish.yml --repo emmett08/earl --ref v3.2.2 \
  -f release_tag=v3.2.2 -f destination=pypi
```

The release workflow is configured to produce exactly one wheel and one source distribution with a SHA-256 checksum file. Linux and macOS installation jobs verify those artefacts; the publishing job verifies the checksum and consumes the same build's retained artefacts by immutable upload ID. Both publishing jobs run without checking out or installing the package. The production job receives the environment's API token and read-only repository permissions; only the TestPyPI job receives `id-token: write`. Production publication requires a valid token, and TestPyPI publication requires its account-level Trusted Publisher registration. A later switch to production Trusted Publishing requires a matching publisher registration for environment `pypi.org`, removal of the explicit token input, `id-token: write` and enabled attestations.

To check a published TestPyPI wheel while resolving dependencies through ordinary PyPI, download just EARL from TestPyPI and install the downloaded file:

```bash
python -m pip download --no-deps --only-binary=:all: \
  --index-url https://test.pypi.org/simple/ --dest test-release \
  'engineering-argument-language==3.2.2'
python -m pip install \
  ./test-release/engineering_argument_language-3.2.2-py3-none-any.whl
python -m pip check
```

The example keeps the test package index separate from dependency resolution. A later release uses a new package version and matching tag rather than replacing published files.

## Packaging references

The [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/) documents virtual environments and local archive installation. [pip's VCS documentation](https://pip.pypa.io/en/stable/topics/vcs-support/) defines pinned Git installations. [PyPI's API token instructions](https://pypi.org/help/#apitoken) specify token permissions and the `__token__` upload username. [PyPI's Trusted Publisher guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) specifies the repository, workflow and environment identity used for OpenID Connect publishing. The [PyPA publishing action](https://github.com/pypa/gh-action-pypi-publish) documents token authentication and the Trusted Publishing requirement for attestations. [GitHub's CLI guide](https://cli.github.com/manual/gh_workflow_run) defines tag selection through `--ref`. [The Unlicense](https://unlicense.org/) supplies the original-software licence text and rationale. These sources explain the packaging mechanisms; the workflow and distribution checker define EARL's implemented release checks.
