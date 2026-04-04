"""Tests for TfRunner subcommand detection and command building."""

import tf


class TestSubcommand:
    def test_extracts_plan(self):
        assert tf.TfRunner(["plan"]).subcommand == "plan"

    def test_extracts_apply(self):
        assert tf.TfRunner(["apply"]).subcommand == "apply"

    def test_extracts_init(self):
        assert tf.TfRunner(["init"]).subcommand == "init"

    def test_skips_chdir_flag(self):
        assert tf.TfRunner(["-chdir=envs/prod", "plan"]).subcommand == "plan"

    def test_skips_chdir_with_space(self):
        assert tf.TfRunner(["-chdir", "envs/prod", "plan"]).subcommand == "plan"

    def test_returns_none_for_empty_args(self):
        assert tf.TfRunner([]).subcommand is None

    def test_returns_none_for_only_flags(self):
        assert tf.TfRunner(["-chdir=envs/prod"]).subcommand is None


class TestBuildCommand:
    def test_injects_var_file_for_plan(self):
        result = tf.TfRunner(["plan"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"])
        )

        assert result == [
            "terraform", "plan", "-var-file", "/tmp/staging.tfvars",
        ]

    def test_injects_multiple_var_files_in_order(self):
        result = tf.TfRunner(["plan"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars", "/tmp/staging-eu-west-1.tfvars"]),
        )

        assert result == [
            "terraform", "plan",
            "-var-file", "/tmp/staging.tfvars",
            "-var-file", "/tmp/staging-eu-west-1.tfvars",
        ]

    def test_injects_var_file_for_apply(self):
        result = tf.TfRunner(["apply"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"])
        )

        assert result == [
            "terraform", "apply", "-var-file", "/tmp/staging.tfvars",
        ]

    def test_injects_var_file_for_destroy(self):
        result = tf.TfRunner(["destroy"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"])
        )

        assert result == [
            "terraform", "destroy", "-var-file", "/tmp/staging.tfvars",
        ]

    def test_injects_var_file_for_import(self):
        result = tf.TfRunner(["import", "aws_thing.foo", "i-12345"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"]),
        )

        assert result == [
            "terraform", "import",
            "-var-file", "/tmp/staging.tfvars",
            "aws_thing.foo", "i-12345",
        ]

    def test_passes_through_when_no_var_files(self):
        result = tf.TfRunner(["plan"]).build_command(tf.TfVarsFiles([]))

        assert result == ["terraform", "plan"]

    def test_preserves_chdir_flag(self):
        result = tf.TfRunner(["-chdir=envs/prod", "plan"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"]),
        )

        assert result == [
            "terraform", "-chdir=envs/prod", "plan",
            "-var-file", "/tmp/staging.tfvars",
        ]

    def test_preserves_extra_flags_after_subcommand(self):
        result = tf.TfRunner(["plan", "-out=plan.tfplan"]).build_command(
            tf.TfVarsFiles(["/tmp/staging.tfvars"]),
        )

        assert result == [
            "terraform", "plan",
            "-var-file", "/tmp/staging.tfvars",
            "-out=plan.tfplan",
        ]
