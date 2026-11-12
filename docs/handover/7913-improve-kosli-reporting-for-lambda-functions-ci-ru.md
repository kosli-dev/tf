# Issue #7913: Improve kosli reporting for lambda-functions CI runs

> **Last updated:** 2026-11-12
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

- [x] Package bucket in the dev account, overwrites blocked, readable by each repo's deploy role
      (terraform-base-infra#1247)
- [x] Golden pipeline: a reusable workflow in this repo that zips, tests, uploads, attests, evaluates the controls
      and deploys to staging, then prod after approval (#46)
- [x] Pilot: `kosli-queue-sampler` (terraform-server#685)
- [ ] Remaining flavour A functions: `kosli-queue-sampler`, `terraform-statefile-paths-reporter`,
      `docdb-pass-rotation` and `kosli-docdb-creds-reporter` are on `lambda-function/v1` (terraform-server#691,
      #694, terraform-base-infra#1268); the bedrock action groups remain
- [ ] Flavour D (notify-slack), built from the pinned module source
- [ ] Flavour C (`upload-package` in terraform-aws-evidence-reporter attests its zip)
- [ ] Flavour B → C (terraform-modules backup, terraform-aws-kosli-instance-access-reporter)
- [ ] `kosli-reporter/aws` functions (deferred)
- [ ] Remove the apply's Lambda attestation (kosli-dev/tf#41) once every function is attested at build

---

## PRs & Branches

| Branch | PR | Status |
|--------|----|--------|
| `7913-lambda-golden-pipeline` | #46 | merged |
| terraform-base-infra `7913-lambda-package-bucket` | terraform-base-infra#1247 | merged |
| sdlc-policies `7913-policy-variants` | sdlc-policies#59 | merged |
| server `7913-sdlc-policies-variants` | #7934 | merged |
| opa-lambda `7913-sdlc-policies-variants` | opa-lambda#40 | merged |
| sdlc-policies `7913-dependencies-zip-variant` | sdlc-policies#60 | merged |
| terraform-base-infra `7913-lambda-deploy-role` | terraform-base-infra#1251 (prod: #1253) | merged |
| terraform-server `7913-queue-sampler-pipeline` | terraform-server#685 | merged |
| `7913-lambda-params-fix` | #47 | merged |
| sdlc-policies `7913-unit-tests-only` | sdlc-policies#61 | merged |
| `7913-unit-tests-only-pin` | #48 | merged |
| `7913-deploy-lambda-plan` | #49 | merged |
| terraform-server `7913-queue-sampler-plan` | terraform-server#688 | merged |
| terraform-modules `7913-lambda-function-module` | terraform-modules#29 | merged |
| terraform-server `7913-queue-sampler-lambda-module` | terraform-server#691 (prod: #693) | merged |
| terraform-base-infra `7913-paths-reporter-deploy-role` | terraform-base-infra#1260 (prod: #1261) | merged |
| terraform-server `7913-paths-reporter-lambda-module` | terraform-server#694 (prod: #693) | merged |
| terraform-modules `backup-v10-lambda-8` | terraform-modules#30 | merged |
| terraform-base-infra `fix-apply-role-backup-storage`, `backup-postgresql-v10` | terraform-base-infra#1263, #1264 | merged |
| terraform-modules `7913-lambda-function-role-name` | terraform-modules#31 | merged |
| terraform-base-infra `7913-base-infra-lambda-deploy-role` | terraform-base-infra#1267 (prod: #1272) | merged |
| terraform-modules `7913-lambda-function-ignore-s3-source` | terraform-modules#32 | merged |
| terraform-modules `7913-lambda-function-source-account` | terraform-modules#33 | merged |
| terraform-base-infra `7913-docdb-lambdas-module` | terraform-base-infra#1268 (prod: #1272) | merged |
| `7913-handover-lambda-module` | #50 | open |

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
- A function whose code the pipeline deploys is a plain `aws_lambda_function` with its package in `ignore_changes`, not a `terraform-aws-modules/lambda` call: the module names its package after the content and the provider swaps the code when the name changes, so any apply after a source change would put back an unattested build. The module's `ignore_source_code_hash` leaves the name tracked; a fixed placeholder package was rejected because the first apply swaps it in and breaks the function; Terraform downloading the deployed package by a pointer was rejected for a drift diff after every deploy; moving each function's Terraform into its own repo was rejected for the extra applies a new environment would need. The module still builds the package a new environment's function starts with.
- Each repo deploys with its own role, trusting only `deploy-lambda.yml` on main, rather than with its Terraform role, so the deploy can swap code and nothing else.
- Production deploys wait on a GitHub environment named `production` with `tech-team` as required reviewer and `master` as the only deployment branch, the same name and gate as the proposal to replace the prod branch.
- SDLC-CTRL-0008 lets a consumer require the unit-test suite alone (sdlc-policies#61), because the Lambda functions have unit tests only; this lowers the control's floor for every consumer that asks for it.
- A deploy shows a plan before its approval, one job summary per account naming the fingerprint and commit it runs and will run, because a code swap has no Terraform plan to review; the gate sits on the deploy jobs themselves, since one approval releases every job waiting on the environment.
- Functions whose code the pipeline deploys share one module, `lambda-function/v1` in terraform-modules, so each gets the same split between Terraform and the pipeline; it has no `layers` input, so everything a function runs is in its attested package.
- A function that runs in several accounts with per-account data carries every account's data in one package and picks it by environment variable, so every account runs the same attested package.
- When a function moves from a layer to bundled code, production gets the pipeline's deploy before the Terraform change that drops the layer, so the function is never left without its dependency.
- `lambda-function/v1` ignores a function's S3 code source as well as its local package, so a function that was deployed from S3 moves onto the module without Terraform clearing its only code source.
- `lambda-function/v1` roles trust Lambda only when it acts for the role's own account, so moving a function onto the module keeps the confused-deputy guard its role had.

---

## Next Steps

- [x] Package bucket (terraform-base-infra#1247)
- [x] Golden pipeline inputs and outputs; `build-lambda.yml` and `deploy-lambda.yml` written
- [x] SDLC-CTRL-0004 for zips: the `zip` variant (sdlc-policies#59, #60), used by `build-lambda.yml`
- [x] Pilot: `boto3` locked, deploy role `terraform-server-lambda-deploy` in every account, the function as plain
      resources ignoring its package, the unqualified EventBridge permission only, and the `production` environment
      (terraform-server#685, terraform-base-infra#1251)
- [x] `lambda-package-publisher`'s trust on `job_workflow_ref`: the pilot's first build uploaded
- [x] The pilot deployed to staging, infra-dev and production with all four decisions passing, after `jq -n`
      (#47) and the unit-tests-only floor (sdlc-policies#61, #48); `terraform-server-lambda-deploy`'s trust works
- [x] The deploy plan: `queue-sampler.yml` passes `kosli_flow`, `kosli_trail` and the Kosli token
      (terraform-server#688); its run showed the commit lookup, staging deploying without an environment, and one
      approval releasing every production account
- [x] Shared function module `lambda-function/v1` (terraform-modules#29), used by the queue sampler (terraform-server#691)
- [x] `terraform-statefile-paths-reporter` on the module, with the Kosli CLI 2.18.0 bundled (terraform-server#694,
      terraform-base-infra#1260); deployed to every account, staging snapshot 406 taken by the new code
- [x] `docdb-pass-rotation` and `kosli-docdb-creds-reporter` on the module, with their own deploy role
      `terraform-base-infra-lambda-deploy` (terraform-base-infra#1267, #1268); deployed to every account, prod
      snapshot 56 compliant with both on the pipeline's build
- [ ] The bedrock action groups
- [ ] README documentation of `build-lambda.yml` and `deploy-lambda.yml`
