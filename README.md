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
  - **init** injects `-backend-config` flags for bucket, key, region, lock table, and encrypt
  - **show, output, state** set `TF_DATA_DIR` so terraform finds the correct providers, then
    pass through
  - **plan, apply, etc.** auto-run `terraform init` with backend config, then inject
    `-var-file` flags
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

This repo provides a reusable workflow for Terraform plan/apply in CI. It handles checkout, AWS
OIDC authentication, terraform installation, formatting checks, and plan artifact uploads.

### Usage

Use the reusable workflow, which is designed to be called from a matrix job:

```yaml
plan:
  needs: [all-environments]
  permissions:
    id-token: write
    contents: write
  uses: kosli-dev/tf/.github/workflows/base.yml@main
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

To apply instead of plan, set `tf_apply: "true"`.

### Reusable workflow inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `environment` | yes | | AWS profile name (e.g. `staging`, `production`) |
| `aws_region` | yes | | AWS region (also used as `AWS_DEFAULT_REGION`) |
| `aws_role_arn` | yes | | IAM role ARN for OIDC authentication |
| `aws_role_duration` | no | `1200` | Role session duration in seconds |
| `working_directory` | no | `./` | Directory containing Terraform config |
| `tf_version` | no | `1.14.6` | Terraform version to install |
| `tf_apply` | no | `false` | Set to `true` to apply instead of plan |

### What it does

**Plan** (`tf_apply: "false"`, the default):
1. Checks out the calling repo
2. Installs terraform and `tf`
3. Runs `terraform fmt --recursive -check` (fails if files need reformatting)
4. Configures AWS credentials via OIDC
5. Runs `tf plan` (auto-init, auto-selects tfvars, saves binary plan)
6. Runs `tf show` to produce a human-readable plan
7. Uploads the plan as a `tfplan-<environment>` artifact

**Apply** (`tf_apply: "true"`):
1. Steps 1–4 as above
2. Runs `tf apply` (auto-init, auto-selects tfvars, auto-approves)

## Configuration

You can place a `tf.env` file in the root of your Terraform repo to set default environment
variables. The file uses `KEY=value` format, one per line. Comments (`#`) and blank lines are
ignored. Values in `tf.env` do not override environment variables that are already set.

Example `tf.env`:

```
AWS_DEFAULT_REGION=eu-west-1
```

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
