# Issue #7913: Improve kosli reporting for lambda-functions CI runs

> **Last updated:** 2026-11-10
> **Issue:** https://github.com/kosli-dev/server/issues/7913
> **Collaborators:** Tore Martin Hagen (engineer), Claude (claude-opus-5-5)

---

## Problem Definition

The 26 Lambda functions in `aws-358426185766-eu-central-1-lambda` have provenance (kosli-dev/server#7842), but
no control decisions: SDLC-CTRL-0002, -0004, -0007 and -0008 are evaluated for none of them except `opa-lambda`.
Getting provenance took 18 PRs, most of them spent moving repos onto shared workflows. The goal is a way to add
the controls that scales with the number of pipelines rather than the number of functions.

`terraform apply` builds the package of 25 of the 26 functions, so the trail a function links to today is the
apply's, whose PR reviewed the Terraform and not necessarily the code. The functions differ by where their
source comes from:

| Flavour | Source | Functions |
|---|---|---|
| A | The deploying repo, zipped at apply | `docdb-pass-rotation`, `kosli-docdb-creds-reporter`, `kosli-queue-sampler`, `terraform-statefile-paths-reporter`, the 4 bedrock action groups |
| B | A Kosli-owned shared module, zipped at apply in the caller | the 6 `backup-error-notifications-*` (terraform-modules backup), `reporter-kosli` ×2 and `reporter-slackapp` (kosli-dev/kosli-reporter/aws), `kosli-instance-access-exec-session-reporter` ×2 |
| C | A Kosli-prebuilt zip, downloaded at apply | `ecs-exec-identity-reporter` ×2 (terraform-aws-evidence-reporter) |
| D | A third-party module, zipped at apply | `info-`, `warning-`, `critical-alerts-to-slack`, `scaling-notifications` (terraform-aws-modules/notify-slack) |
| E | An image built in CI | `opa-lambda` |

Acceptance: each function's deployed fingerprint is an artifact on a build trail in the repo that holds its
source, with the PR that reviewed it and a decision per control.

---

## Plan

- [ ] Package bucket in the dev account, overwrites blocked, readable by each repo's deploy role
      (terraform-base-infra)
- [ ] Golden pipeline: a reusable workflow in this repo that zips, tests, uploads, attests, evaluates the controls
      and deploys to staging, then prod after approval
- [ ] Pilot: `kosli-queue-sampler` (terraform-server)
- [ ] Remaining flavour A functions
- [ ] Flavour D (notify-slack), built from the pinned module source
- [ ] Flavour C (`upload-package` in terraform-aws-evidence-reporter attests its zip)
- [ ] Flavour B → C (terraform-modules backup, terraform-aws-kosli-instance-access-reporter)
- [ ] `kosli-reporter/aws` functions (deferred)
- [ ] Remove the apply's Lambda attestation (kosli-dev/tf#41) once every function is attested at build

---

## PRs & Branches

| Branch | PR | Status |
|--------|----|--------|
| `7913-lambda-golden-pipeline` | — | in progress |
| terraform-base-infra `7913-lambda-package-bucket` | terraform-base-infra#1247 | merged |
| sdlc-policies `7913-policy-variants` | sdlc-policies#59 | merged |
| server `7913-sdlc-policies-variants` | #7934 | open |
| opa-lambda `7913-sdlc-policies-variants` | opa-lambda#40 | open |
| sdlc-policies `7913-dependencies-zip-variant` | sdlc-policies#60 | merged |

---

## Decisions Made

- The repo that holds the source builds and attests the artifact, and the deploy only moves it, as server does; the apply attesting what it zips was a way to get provenance, not the target process.
- Terraform owns each function and ignores its code, and the pipeline swaps the code; passing the package to Terraform as an argument was rejected because the scheduled drift plan and PR plans run without a build, and pinning it in code was rejected because it takes two PRs per change.
- Built zips are stored in S3, not as images in ECR, so the functions keep their packaging and only the step between build and deploy changes.
- Module repos build on merge and dispatch the deploy to their callers, so a module change takes one PR, reviewed where the code is.
- Every Lambda environment gets one policy requiring a decision per control; per-flavour rules in the policy were rejected because one apply flow mixes flavours.
- The Kosli CLI is bundled into the function zip rather than used from a layer, because Kosli's Lambda snapshot reports only the function's own code.
- notify-slack functions are built by the golden pipeline from the pinned module source and need no tests; an exception by name was rejected as a hand-kept list.
- `terraform-aws-kosli-instance-access-reporter` is treated as internal: only Kosli calls it, and it is published as an example.
- The `kosli-reporter/aws` functions are deferred: customers deploy the module with a plain apply and pick the CLI version independently, and Kosli will not report layers.
- The golden pipeline lives in kosli-dev/tf, so the build, the Terraform apply and the code deploy share one approval flow.
- The build zips with fixed timestamps and sorted entries, so a re-run of the same commit produces the same fingerprint and is accepted against the write-once key instead of failing.
- The bundled CLI is chosen by `bundle_kosli_cli` and `bundled_kosli_cli_version`, separate from the CLI the pipeline itself runs, because only three packages execute the CLI and the version that ships must not move with the pipeline's.
- SDLC-CTRL-0004 has one policy per packaging variant in sdlc-policies (`image/`, `zip/`) rather than one policy with parameters, so each reads as what it checks; the variant is named by the consumer and the decision name stays `dependencies-decision`.
- For a zip, the Lambda runtime is the base image: the build attests the runtime it built for and the zip policy requires it, and `boto3` is bundled and locked rather than taken from the runtime, so an empty lockfile means the code uses only the standard library; every package the SBOM finds in the zip must be in the lockfile.
- The golden pipeline is two workflows: `build-lambda.yml` builds, tests, uploads and attests, and `deploy-lambda.yml` swaps the code, so a module repo can dispatch a deploy to its callers without rebuilding; only the build may write to the package bucket.

---

## Next Steps

- [x] Package bucket (terraform-base-infra#1247)
- [x] Golden pipeline inputs and outputs; `build-lambda.yml` and `deploy-lambda.yml` written
- [x] SDLC-CTRL-0004 for zips: the `zip` variant (sdlc-policies#59, #60), used by `build-lambda.yml`
- [ ] Pilot: `boto3` declared in `kosli-queue-sampler`'s `pyproject.toml`, a deploy role for terraform-server in
      each account (`modules/iam`), `ignore_changes` on the function's code, and a check that the EventBridge permission, which the module qualifies with the
      function version, still matches once versions are published outside Terraform
- [ ] `lambda-package-publisher`'s trust on `job_workflow_ref` is verified only by the first build run
