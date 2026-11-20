# Issue #7913: Improve kosli reporting for lambda-functions CI runs

> **Last updated:** 2026-11-20
> **Issue:** https://github.com/kosli-dev/server/issues/7913
> **Collaborators:** Tore Martin Hagen (engineer), Claude (claude-opus-5-5, claude-fable-5-2)

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
- [x] Flavour D (notify-slack): the three functions are on `lambda-function/v1` and run upstream's
      `notify_slack.py`, built from the commit pinned in `slack-alerts/lambda-src/upstream.json` and never copied
      into our repo (#59, terraform-base-infra#1319). A weekly workflow opens a PR when upstream has a new
      release (terraform-base-infra#1320). This replaced the AWS Chatbot plan (kosli-dev/server#8073)
- [x] Flavour C: the evidence reporter is retired instead (terraform-evidence-reporter#9): nobody used it. Its
      infrastructure is destroyed, the CLI release no longer triggers it (cli#1398), its roles are removed
      (terraform-base-infra#1311) and the three repos are archived in the `kosli-dev-archive` organisation
- [x] Flavour B, terraform-aws-kosli-instance-access-reporter: the code moved into terraform-base-infra
      `lambda-instance-access-reporter/` and is built and deployed by `instance-access-reporter.yml`, to the
      instance accounts and to the elevation reporter in the SSO account (terraform-base-infra#1300,
      terraform-sso#140, terraform-deploy-matrix#9); the repo is archived
- [x] Flavour B, terraform-modules backup: the code is one copy in terraform-modules `backup/lambda/`, built and
      deployed to every `backup-error-notifications-*` function by `backup-notifications.yml` there
      (terraform-modules#35, #36, terraform-base-infra#1318). This replaced the AWS Chatbot plan too
- [x] `kosli-reporter/aws` functions: one `reporter-kosli` per account, in kosli-dev/kosli-reporter, reports the
      `merkely` cluster, the static files bucket and the `slackapp` cluster, from a package built from the public
      module's source (#57, terraform-aws-kosli-reporter#95, kosli-reporter#13, #15). `static-files-env-reporter`
      and `reporter-slackapp` are destroyed and their code deleted (terraform-server#714-#716, slack-auth-app#36,
      #37)
- [x] Third-party code needs no tests of ours: `build-lambda.yml` tags each flow with `code_origin`, and
      `kosli-lambda-policy` requires SDLC-CTRL-0008 unless the tag is `third-party` (#60, #61,
      terraform-kosli-app#115)
- [ ] `docdb-users`, added by terraform-base-infra#1310 without a build trail, and `postgresql-roles`: Terraform
      invokes both during the apply, so the pipeline does not fit as it is; waiting for a decision in that PR
- [x] Remove the apply's Lambda attestation (#53), done early because `kosli-lambda-policy` failed
      pipeline-built functions through the apply's trails
- [x] `kosli-lambda-policy` on every Lambda environment (terraform-kosli-app#106)

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
| `7913-handover-lambda-module` | #50 | closed (carried by #51) |
| `7913-build-lambda-reusable-package` | #51 | merged |
| terraform-aws-evidence-reporter `7913-evidence-reporter-build-lambda` | terraform-aws-evidence-reporter#11 | merged |
| terraform-kosli-app `7913-lambda-policy` | terraform-kosli-app#106 | merged |
| terraform-base-infra `7913-scaling-alerts-to-slack` | terraform-base-infra#1280 | merged |
| terraform-server `7913-scaling-alarms-to-base-infra` | terraform-server#697 | merged |
| `7913-remove-apply-lambda-attestation` | #53 | merged |
| sdlc-policies `7913-zip-licence-names` | sdlc-policies#64 | merged |
| `7913-bump-sdlc-policies-pin` | #54 | merged |
| terraform-server `7913-boto3-1.44.2` | terraform-server#698 | merged |
| terraform-base-infra `7913-boto3-1.44.2` | terraform-base-infra#1281 | merged |
| terraform-base-infra `7913-notify-slack-deploy-role` | terraform-base-infra#1283 | merged |
| terraform-server `7913-remove-scaling-alerts` | terraform-server#700 (prod: #701) | merged |
| terraform-base-infra `7913-remove-scaling-alerts` | terraform-base-infra#1284 | merged |
| terraform-modules `7913-lambda-function-existing-role` | terraform-modules#34 | merged |
| terraform-server `7913-keep-scaling-kms-key` | terraform-server#702 | closed (admin applies instead) |
| terraform-base-infra `7913-keep-scaling-alerts-kms-key` | terraform-base-infra#1285 | closed (admin applies instead) |
| terraform-base-infra `7913-notify-slack-lambda-module` | terraform-base-infra#1296 | closed (AWS Chatbot instead, kosli-dev/server#8073) |
| `7913-build-lambda-tests-dir` | #55 | merged |
| terraform-aws-kosli-instance-access-reporter `7913-single-source-dir` | terraform-aws-kosli-instance-access-reporter#11 | merged |
| terraform-base-infra `7913-instance-access-reporter-upload-role` | terraform-base-infra#1297 | merged (role removed by #1300) |
| terraform-aws-kosli-instance-access-reporter `7913-build-package` | terraform-aws-kosli-instance-access-reporter#12 | merged (superseded by #1300) |
| terraform-deploy-matrix `7913-sso-account` | terraform-deploy-matrix#9 | merged |
| terraform-sso `7913-elevation-reporter-lambda-function` | terraform-sso#140 | merged |
| terraform-base-infra `7913-instance-access-reporter-code` | terraform-base-infra#1300 | merged |
| `7913-build-lambda-source-repository` | #57 | merged |
| `7913-deploy-lambda-names` | #58 | merged |
| terraform-aws-kosli-reporter `7913-attestable-package` | terraform-aws-kosli-reporter#95 (v0.12.0) | merged |
| terraform-base-infra `7913-kosli-reporter-deploy-role`, `7913-kosli-reporter-apply-permissions` | terraform-base-infra#1309, #1312 | merged |
| kosli-reporter `7913-build-and-deploy-reporter` | kosli-reporter#13 | merged |
| kosli-reporter `cli-release-opens-pr` | kosli-reporter#14 | merged |
| kosli-reporter `7913-report-static-files-and-slackapp` | kosli-reporter#15 | merged |
| slack-auth-app `7913-remove-slackapp-reporter`, `7913-delete-slackapp-reporter-files` | slack-auth-app#36, #37 | merged |
| terraform-server `7913-remove-static-files-reporter`, `7913-delete-static-files-reporter-files` | terraform-server#714 (prod: #715), #716 | merged |
| cli `retire-evidence-reporter` | cli#1398 | merged |
| terraform-evidence-reporter `retire-evidence-reporter` | terraform-evidence-reporter#13 | merged |
| terraform-base-infra `retire-evidence-reporter-roles` | terraform-base-infra#1311 | merged |
| terraform-base-infra `claude-md-new-lambda-rule` | terraform-base-infra#1313 | merged |
| terraform-modules `7913-backup-notifications-one-copy`, `7913-backup-notifications-workflow` | terraform-modules#35, #36 | merged |
| terraform-base-infra `7913-backup-notifications-deploy-role` | terraform-base-infra#1318 | merged |
| `build-lambda-upstream-code` | #59 | merged |
| terraform-base-infra `7913-alerts-to-slack-pinned-upstream` | terraform-base-infra#1319 | merged |
| terraform-base-infra `7913-notify-slack-upstream-bump` | terraform-base-infra#1320 | merged |
| `build-lambda-code-origin` | #60 | merged |
| `7913-state-code-origin` in terraform-base-infra, terraform-server, terraform-modules, kosli-reporter | terraform-base-infra#1321, terraform-server#717, terraform-modules#37, kosli-reporter#16 | merged |
| terraform-kosli-app `7913-third-party-code-needs-no-tests` | terraform-kosli-app#115 | merged |
| `build-lambda-code-origin-required` | #61 | open |

---

## Decisions Made

- The repo that holds the source builds and attests the artifact, and the deploy only moves it, as server does; the apply attesting what it zips was a way to get provenance, not the target process.
- Terraform owns each function and ignores its code, and the pipeline swaps the code; passing the package to Terraform as an argument was rejected because the scheduled drift plan and PR plans run without a build, and pinning it in code was rejected because it takes two PRs per change.
- Built zips are stored in S3, not as images in ECR, so the functions keep their packaging and only the step between build and deploy changes.
- Module repos build on merge and dispatch the deploy to their callers, so a module change takes one PR, reviewed where the code is.
- Every Lambda environment gets one policy requiring a decision per control; per-flavour rules in the policy were rejected because one apply flow mixes flavours.
- The Kosli CLI is bundled into the function zip rather than used from a layer, because Kosli's Lambda snapshot reports only the function's own code.
- notify-slack functions are built by the golden pipeline from the pinned module source and need no tests; an exception by name was rejected as a hand-kept list. (superseded: AWS Chatbot replaces them, kosli-dev/server#8073)
- `terraform-aws-kosli-instance-access-reporter` is treated as internal: only Kosli calls it, and it is published as an example. (superseded: its code is in terraform-base-infra and the repo is archived)
- The `kosli-reporter/aws` functions are deferred: customers deploy the module with a plain apply and pick the CLI version independently, and Kosli will not report layers. (superseded: see the `reporter-kosli` decisions below)
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
- A function whose code is released elsewhere, such as the evidence reporter's public zip, is built by `build-lambda.yml` and the release ships the attested zip from the run, so customers and our accounts run the bytes the build trail records; no deploy role is involved, because the Terraform apply that downloads the release deploys it.
- Every Lambda environment requires provenance and a compliant decision for SDLC-CTRL-0002, -0004, -0007 and -0008, with no exceptions, so each function without a build trail shows as non-compliant until it moves. (changed: SDLC-CTRL-0008 is not required from third-party code, see `code_origin` below)
- The Terraform apply no longer attests Lambda functions: the policy requires the decisions in every trail an artifact appears in, and the apply's trails have none. A fingerprint the apply attested earlier stays failing, so a function passes only from its first build with a changed package.
- A licence a package declares as free text is translated per package and per exact string, not replaced per package, so a package that changes to a disallowed licence still fails.
- All notify-slack functions live in terraform-base-infra, each with its own topic and webhook, and run one copy of `notify_slack.py` from one build; the scaling alarms in terraform-server publish to its scaling topic, found through SSM. Where a function lives was mostly convenience, so the move was made now rather than migrating two copies. (superseded: AWS Chatbot replaces them, kosli-dev/server#8073)
- `lambda-function/v1` ignores a function's S3 code source as well as its local package, so a function that was deployed from S3 moves onto the module without Terraform clearing its only code source.
- `lambda-function/v1` roles trust Lambda only when it acts for the role's own account, so moving a function onto the module keeps the confused-deputy guard its role had.
- The scaling notify-slack function and its topic are removed rather than migrated, because nobody uses the scaling messages; the ECS scaling alarms report to the warning topic.
- A disaster-recovery deployment reuses the regular deployment's role through a `lambda-function/v1` option rather than creating a role per region, since IAM is global per account.
- A KMS key that a removal leaves behind is deleted by an admin running the apply by hand, not dropped from state, because the apply roles may not schedule key deletion and a dropped key would still need deleting by hand later.
- Functions that only forward SNS or EventBridge messages to Slack (notify-slack, the backup error notifications) are replaced by AWS Chatbot rather than built by the pipeline: copying third-party code by hand is not acceptable, and building from the pinned upstream still leaves us maintaining code we did not write (kosli-dev/server#8073). (superseded: the Chatbot decision never came, and both groups are built by the pipeline, see below)
- Kosli's own Lambda code keeps the standard Python layout: the function directory holds the code, `pyproject.toml`, `uv.lock` and a `tests/` directory, and only the code is zipped (#55).
- Lambda code lives in the repo that defines its functions, not in a module repo of its own: a module fetched from GitHub breaks `terraform init` once the repo is internal, and a code repo of its own adds a release to coordinate. Where one package runs in several repos' accounts, as the elevation reporter in terraform-sso does, the repo holding the code deploys to all of them, and the other repo's Terraform starts the function from a stub that fails until the first deploy.
- A repo whose build uses `build-lambda.yml` must be internal or private, because the build calls the internal sdlc-policies workflow, which GitHub does not allow from a public repo.
- The bundled Kosli CLI version is a literal in the calling workflow, not the `KOSLI_CLI_VERSION` variable, so a new CLI in production comes through a reviewed commit, which also rebuilds the package.
- The SSO account is in terraform-deploy-matrix with an account type of its own, `sso`, so no existing selection deploys to it.
- The instance access reporters dropped their layer in the same apply that adopted them, against the earlier rule of deploying first, because `terraform init` had failed since the repo went internal; the deploy followed within about a minute in the instance accounts and about 20 minutes in the SSO account.
- Kosli runs one reporter per AWS account, `reporter-kosli`, for every environment of that account, instead of one function per environment in three repos: all three ran the same module code, and one function means one package to attest.
- `reporter-kosli` keeps the CLI in the layer, as customers run the module, and its own code is built from the public module's source at a pinned commit (`source_repository`); the module's `ignore_source_code_hash` (v0.12.0) stops Terraform replacing the code, and the same workflow applies Terraform and then deploys the attested package, so a module bump leaves no gap.
- A Kosli CLI release opens a pull request in kosli-reporter that moves the CLI version, and posts it to the PR reviews Slack channel; merging deploys to staging and then production with no approval step. The team prefers a reviewed PR per upgrade to an automatic deploy.
- The evidence reporter is retired rather than moved: terraform-evidence-reporter#9 had already found that no customer uses it.
- The backup notification code stays in terraform-modules and is built there, because the user rejected a second copy in a repo that has the pipeline set up; the package publisher role already trusts `build-lambda.yml` from any kosli-dev repo, so only a deploy role was needed.
- The backup module creates a function from a zip at a fixed path and ignores its hash, so Terraform uploads code only at creation; the path contains the module version and the caller's `module` name, so moving a backup to another version or renaming its block uploads Terraform's zip once, and a manual run of `backup-notifications.yml` puts the attested package back.
- Third-party code is fetched at build time from a pinned commit and never copied into our repo (`upstream_repository`, `upstream_ref`, `upstream_path`). The trail, commit and pull request stay the caller's, because the change we review is our pin, not upstream's commit.
- The first package of a newly created alerts-to-slack function is the pinned upstream file, fetched by Terraform at plan time; a placeholder was rejected because a disaster-recovery deployment would create functions that cannot post alerts.
- Upgrades of third-party code arrive as a pull request opened by a scheduled workflow and announced in Slack, the same shape as the CLI bump.
- Every `build-lambda.yml` caller states `code_origin`, `own` or `third-party`, and the build tags the flow with it; the input is required so the choice is deliberate. The build accepts `third-party` only with the `upstream_*` inputs and requires SDLC-CTRL-0008 for `own`, so the tag cannot be claimed for our own code. The policy reads the tag, so it keeps no list of names; a flow without the tag still needs all four controls.
- A function that Terraform invokes during the apply (`aws_lambda_invocation`: `docdb-users`, `postgresql-roles`) does not fit the pipeline as it is: Terraform reruns it because a code change publishes a new version, and a workflow that deploys and invokes it races the apply. terraform-base-infra's `CLAUDE.md` tells Claude to stop and ask before adding another (terraform-base-infra#1313).

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
- [x] Every Lambda environment requires the four decisions (terraform-kosli-app#106); the four pipeline-built
      functions are compliant in prod snapshot 70 after the boto3 bump (terraform-server#698,
      terraform-base-infra#1281)
- [x] 2026-11-13: scaling alerts removed; the scaling KMS keys deleted by admin applies in all six accounts,
      terraform-server then terraform-base-infra (#702 and terraform-base-infra#1285 closed in favour of that)
- [x] 2026-11-17: the instance access reporters on the pipeline with CLI 2.57.0 (terraform-base-infra#1300,
      terraform-sso#140); a session and its transcript tested by hand in staging, and prod snapshot 75 shows
      `kosli-instance-access-exec-session-reporter` compliant, 6 compliant functions in all
- [ ] Test the elevation reporter by hand with an elevation into a production account
- [ ] terraform-aws-kosli-instance-access-reporter#9 (skip automated revocation) is unmerged in the archived repo;
      waiting for its author on whether to bring it into terraform-base-infra
- [ ] Bedrock action groups: decide whether code reaches prod on the `release-*` tag or on merge to `main`
- [x] `ecs-exec-identity-reporter`: retired, see flavour C
- [x] 2026-11-20: prod snapshot 97 has 9 compliant and 5 non-compliant artifacts. Compliant: `reporter-kosli`,
      the six backup notification functions (one artifact) and the three alerts-to-slack functions (one
      artifact), beside the six from before. Non-compliant: `docdb-users` and the 4 bedrock action groups
- [ ] Merge #61, then run kosli-reporter's `Main` workflow once: its build has failed at the flow tag step
      since #60, because `kosli tag` rejects the `KOSLI_REPO_ID` a `source_repository` build sets. Its flow was
      tagged by hand meanwhile
- [ ] `bump-cli-version.yml` (kosli-reporter) and `bump-notify-slack.yml` (terraform-base-infra) have not run
      yet; the second runs Mondays 05:00 UTC and will first propose notify-slack v7.5.3
- [ ] `docdb-users` and `postgresql-roles`: decide between the options in terraform-base-infra#1310
- [ ] Bedrock action groups: after the MCP meeting on 2026-11-23
- [ ] Disaster-recovery regions: the pipeline deploys primary regions only, so alerts-to-slack functions there
      keep the code they have
- [ ] Close or rewrite kosli-dev/server#8073, which still says AWS Chatbot replaces the nine forwarders
- [ ] `slackapp-prod` does not exist on staging.app.kosli.com, so the prod `reporter-kosli` logs one error per run
- [ ] README documentation of `build-lambda.yml` and `deploy-lambda.yml`
