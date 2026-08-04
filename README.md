# tf

A Terraform wrapper that automatically selects the correct `.tfvars` files based on your active
AWS profile and region.

## Why

When deploying Terraform across multiple AWS accounts, each repo typically contains tfvars files
named after AWS profiles (e.g. `prod.tfvars`, `staging-eu-west-2.tfvars`). Remembering to pass
the right `-var-file` flags every time is tedious and error-prone. `tf` does it for you.

## How it works

1. Reads your active AWS profile from the `AWS_VAULT` env var (local) or `environment` (CI)
2. Reads the region from `AWS_DEFAULT_REGION` or `AWS_REGION`
3. Finds matching tfvars files in the current directory:
   - `<profile>.tfvars` (base)
   - `<profile>-<region>.tfvars` (overlay, loaded on top if it exists)
4. Passes everything through to `terraform` with the correct `-var-file` flags injected

## Status

- `TfRunner` — orchestrates the tool with four execution paths:
  - **Simple subcommands** (fmt, validate, etc.) pass through directly, no AWS session needed
  - **init** injects `-backend-config` flags for bucket, key, region, locking, and encrypt
  - **show, output, state** set `TF_DATA_DIR` so terraform finds the correct providers, then
    pass through
  - **plan, apply, etc.** auto-run `terraform init` with backend config, then inject
    `-var-file` flags
  - **force-unlock** auto-runs `terraform init` with backend config so the lock can be located,
    but does not inject `-var-file` flags
- `tf plan` automatically saves a binary plan to `/tmp/<profile>.tfplan` (view with
  `tf show /tmp/<profile>.tfplan`). Skipped if the user passes their own `-out` flag.
- `tf apply` automatically appends `-auto-approve`, since locally the plan has already been
  reviewed and in CI interactive approval is not available.

## Installation

Clone this repo and add `bin/` to your PATH:

```bash
git clone git@github.com:kosli-dev/tf.git ~/tools/tf
# Add to ~/.zshrc or ~/.bashrc:
export PATH="$HOME/tools/tf/bin:$PATH"
```

## Usage

Use `tf` wherever you would use `terraform`:

```bash
aws-vault exec staging -- tf plan
aws-vault exec prod -- tf apply
```

## GitHub Actions

This repo provides reusable workflows for Terraform plan and apply in CI. They handle checkout,
AWS OIDC authentication, terraform installation, formatting checks, and plan artifact uploads.

### Usage

Call the plan workflow (designed to be used from a matrix job):

```yaml
plan:
  needs: [all-environments]
  permissions:
    id-token: write
    contents: write
  uses: kosli-dev/tf/.github/workflows/plan.yml@main
  strategy:
    fail-fast: false
    matrix:
      include: ${{ fromJSON(needs.all-environments.outputs.json) }}
  name: ${{ matrix.name }}
  with:
    aws_region: ${{ matrix.aws_region }}
    aws_role_arn: "arn:aws:iam::${{ matrix.aws_account_id }}:role/my-role"
    environment: ${{ matrix.environment }}
    tf_version: v1.14.6
```

To apply instead of plan, use `apply.yml`:

```yaml
  uses: kosli-dev/tf/.github/workflows/apply.yml@main
```

### Workflow inputs

Both `plan.yml` and `apply.yml` accept the same core inputs:

| Input | Required | Default | Description |
|---|---|---|---|
| `environment` | yes | | AWS profile name (e.g. `staging`, `production`) |
| `aws_region` | yes | | AWS region (also used as `AWS_DEFAULT_REGION`) |
| `aws_role_arn` | yes | | IAM role ARN for OIDC authentication |
| `aws_role_duration` | no | `1200` | Role session duration in seconds |
| `working_directory` | no | `./` | Directory containing Terraform config |
| `tf_version` | no | `1.14.6` | Terraform version to install |
| `tf_vars` | no | `""` | Extra env vars (one `KEY=VALUE` per line) exported before plan/apply; see [Supplying Terraform variables](#supplying-terraform-variables) |
| `job_timeout_minutes` | no | `30` | Minutes before GitHub cancels the plan/apply job; see [Timeouts](#timeouts) |

Plus, for opting into Kosli attestation (see [Kosli attestation](#kosli-attestation) below):

| Input | Required | Default | Description |
|---|---|---|---|
| `kosli_template_file` | no | `""` | Path to Kosli trail template; empty disables Kosli. |
| `kosli_host` | no | `https://app.kosli.com` | Kosli endpoint. |
| `kosli_org` | no | `kosli` | Kosli organisation name. |
| `kosli_cli_version` | no | `2.17.4` | Kosli CLI version to install. |

`apply.yml` also accepts `tf_state_file_name` (default `main.tfstate`) which names the state file
under `terraform/<repo>/` in S3. This is used by `apply.yml`'s drift-plan housekeeping; see below.

### Supplying Terraform variables

A variable declared in `variables.tf` with no default and no `.tfvars` entry would normally make
Terraform prompt for a value on STDIN — which hangs in CI. Use the `tf_vars` input to inject values
from the calling workflow. Each line is a `KEY=VALUE` pair exported into the job environment before
plan/apply; because `tf` inherits the environment, any `TF_VAR_<name>` reaches Terraform as the
value for variable `<name>`. Values must be single-line.

The common case is feeding a freshly built image tag into the apply. The build job pushes the image
to ECR and outputs the tag; the apply job passes it through `tf_vars`:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tag }}
    steps:
      # ... docker build & push to ECR, setting steps.meta.outputs.tag ...

  apply:
    needs: build
    permissions:
      id-token: write
      contents: write
    uses: kosli-dev/tf/.github/workflows/apply.yml@main
    with:
      aws_region: eu-central-1
      aws_role_arn: "arn:aws:iam::123456789012:role/my-role"
      environment: production
      tf_vars: |
        TF_VAR_image_tag=${{ needs.build.outputs.image_tag }}
```

`tf_vars` is intended for **non-sensitive** values — inputs are not masked and may appear in plan
output. Do not pass secrets through it.

For values that are *static per environment* (rather than computed per build), prefer the existing
mechanisms instead of `tf_vars`: add them to the per-environment `<profile>.tfvars` files (which
`tf` auto-selects), or to a committed [`tf.env`](#configuration) file. Neither suits a per-build
image tag, which changes every run.

> **Drift detection caveat.** `detect-drift.yml` also accepts `tf_vars`, but it plans against a
> committed baseline SHA and has no per-build value such as an image tag available. If a required
> variable has no default, the drift plan fails; if it is given a value that differs from what is
> deployed, drift detection reports false drift every run. For per-build values, give the variable a
> default in `variables.tf` and/or add `lifecycle { ignore_changes = [...] }` to the resource that
> consumes it, so the deployed value is not tracked as drift.

### Secrets

| Secret | Required | Description |
|---|---|---|
| `kosli_api_token` | if `kosli_template_file` is set | Kosli API token for the attest steps. |
| `kosli_github_token` | no (only `apply.yml`) | GitHub token used by `kosli attest pr github` to look up pull requests. When omitted, the pull-request attestation step is skipped. Typically passed as `${{ secrets.GITHUB_TOKEN }}` — in which case the **calling job must also declare `pull-requests: read`** in its `permissions:` block (see example below), otherwise the attestation step will fail with `Resource not accessible by integration`. |

### Timeouts

Every job carries a `timeout-minutes` rather than inheriting GitHub's 360-minute default, and the
OIDC credential step is bounded so that an unreachable STS endpoint fails in under a minute instead
of holding a runner — and the environment's `concurrency` group — for over an hour:

```yaml
      - name: Configure AWS credentials
        timeout-minutes: 2
        uses: aws-actions/configure-aws-credentials@ec61189d14ec14c8efccab744f656cffd0e33f37 # v6.1.0
        with:
          # ...
          action-timeout-s: 45
          retry-max-attempts: 3
```

These are the standard values for **any** Kosli workflow using
`aws-actions/configure-aws-credentials`, not just the ones here. The reasoning:

| Setting | Value | Why |
|---|---|---|
| `action-timeout-s` | `45` | Bounds the action as a whole, retries included. Across recent successful runs in `kosli-dev` and `cyber-dojo` the step took 0–2s, worst case 6s, so 45s is far above the real p99 and will not fail a slow-but-healthy authentication. |
| `retry-max-attempts` | `3` | The default is 12. STS throttling is genuinely transient and worth retrying, but 12 attempts is only useful if each attempt is fast — which is exactly what fails to hold when the endpoint is unreachable. |
| `timeout-minutes` (step) | `2` | A backstop that holds regardless of how the action behaves or what a future version changes. |
| `timeout-minutes` (job) | `30` plan/apply, `5`–`10` housekeeping | Bounded by `aws_role_duration`, not by how long Terraform might take — see below. |

`disable-retry` is deliberately **not** used: a couple of quick retries is worth having, and
`action-timeout-s` already bounds the total cost of them.

The plan/apply job's default of 30 minutes is **derived from `aws_role_duration`**, which defaults
to `1200` (20 minutes). The credentials the OIDC step exports are static environment variables and
are never refreshed, so 20 minutes after that step every AWS call starts failing with
`ExpiredToken` — a longer job ceiling would buy nothing, because the work cannot usefully continue.
Measured against real runs, setup before the credentials step takes 1–35s, so a job that consumes
its entire credential lifetime lands around 22–23 minutes; 30 leaves headroom without being
arbitrary.

The two values are coupled, so **raise `job_timeout_minutes` and `aws_role_duration` together** when
a repository has a legitimately long apply. Raising only the session duration lets the job be
cancelled part-way through an `apply`, which can leave the state lock held — a worse outcome than a
slow run. Raising only the job ceiling buys time in which every AWS call fails:

```yaml
    with:
      aws_role_duration: "3600"   # 60 min session
      job_timeout_minutes: 70     # 60 + setup + headroom
```

The role's own maximum session duration is the hard limit on `aws_role_duration`; if a longer
session is refused, that maximum needs raising on the IAM role first.

A job that fails in 45 seconds can be re-run for nothing. A job that hangs for 82 minutes blocks
every apply queued behind it.

### What it does

**Plan** (`plan.yml`):
1. Checks out the calling repo
2. Installs terraform and `tf`
3. Runs `terraform fmt --recursive -check` (fails if files need reformatting)
4. Configures AWS credentials via OIDC
5. Runs `tf plan` (auto-init, auto-selects tfvars, saves binary plan)
6. Runs `tf show` to produce a human-readable plan
7. Uploads the plan as a `tfplan-<environment>` artifact

**Apply** (`apply.yml`):
1. Steps 1–4 as above
2. Runs `tf apply` (auto-init, auto-selects tfvars, auto-approves)
3. Writes `drift.plan.json` (containing `{sha, drift: false}`) alongside the state file in S3,
   so the [drift-detection job][drift-doc] has a known-good baseline to compare against on its
   next run.

### Kosli attestation

Both workflows can optionally attest each Terraform run to Kosli.  This is opt-in: provide a
`kosli_template_file` input and pass the `kosli_api_token` secret, and the workflows will:

* create the Kosli flow `terraform-plan-<environment>-<repo>` (or `terraform-apply-<environment>-<repo>`) from your template,
* begin a trail named after the commit SHA being acted on,
* attest the plan output (and, for apply, the apply log) as generic attestations, and
* in `apply.yml`, additionally attest the **state file** and the **drift plan** as artifacts so
  that any later out-of-band change to either file is detected as drift by the downstream
  [drift-detection job][drift-doc].

The trail template needs to declare every attestation/artifact name the workflow emits:

```yaml
# kosli-apply-template.yml
version: 1
trail:
  attestations:
    - name: terraform-plan
      type: generic
    - name: terraform-apply
      type: generic
  artifacts:
    - name: terraform-state
    - name: drift-plan
```

(The plan workflow only needs `terraform-plan`, so a separate slimmer template can be used for
`plan.yml` if desired.)

Example caller workflow with Kosli enabled:

```yaml
jobs:
  apply:
    needs: [all-environments]
    permissions:
      id-token: write
      contents: write
      pull-requests: read
    uses: kosli-dev/tf/.github/workflows/apply.yml@main
    strategy:
      fail-fast: false
      matrix:
        include: ${{ fromJSON(needs.all-environments.outputs.json) }}
    name: ${{ matrix.name }}
    with:
      aws_region: ${{ matrix.aws_region }}
      aws_role_arn: "arn:aws:iam::${{ matrix.aws_account_id }}:role/my-role"
      environment: ${{ matrix.environment }}
      tf_version: v1.14.6
      kosli_template_file: kosli-apply-template.yml
    secrets:
      kosli_api_token: ${{ secrets.KOSLI_API_TOKEN }}
      kosli_github_token: ${{ secrets.GITHUB_TOKEN }}
```

The `KOSLI_API_TOKEN` secret should be configured at the repository or organization level in
GitHub.  If `kosli_template_file` is left empty, every Kosli step is skipped and the token is not
required.

The `pull-requests: read` permission and the `kosli_github_token` secret are both needed by the
`kosli attest pr github` step in `apply.yml`. They go together: GitHub computes the token's
permissions in a reusable workflow as the intersection of the caller job's `permissions:` and the
called job's `permissions:`, so both sides must grant `pull-requests: read` or the attestation
step fails with `Resource not accessible by integration`. Omit both if you don't need
pull-request attestation — the step is skipped when `kosli_github_token` is not passed.

[drift-doc]: https://github.com/kosli-dev/knowledge-base/blob/main/drift-detection.md

## Configuration

You can place a `tf.env` file in the root of your Terraform repo to set default environment
variables. The file uses `KEY=value` format, one per line. Comments (`#`) and blank lines are
ignored. Values in `tf.env` do not override environment variables that are already set.

Example `tf.env`:

```
AWS_DEFAULT_REGION=eu-west-1
```

### State file name

By default, the Terraform state is stored at `terraform/<repo-name>/main.tfstate` in the S3
backend bucket. If a single repo contains multiple Terraform stacks (e.g. one per subdirectory),
set `TF_STATE_FILE_NAME` per stack so each stack writes to its own state file. The variable can
be set in the environment or via `tf.env`:

```
TF_STATE_FILE_NAME=environment-reporter.tfstate
```

### State locking

By default, `tf` uses Terraform's native S3 lockfile (`use_lockfile=true`), which writes a `.tflock`
object alongside the state file. To fall back to DynamoDB-based locking, set `TF_STATE_LOCK=dynamodb`
in the environment or via `tf.env`. Valid values are `s3` (default) and `dynamodb`. The DynamoDB
table name, when used, matches the state bucket name.

## Development

### Prerequisites

- Python 3.11+
- make

### Setup

```bash
make pip
```

### Running tests

```bash
make test
```
