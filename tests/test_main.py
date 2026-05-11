"""Tests for TfRunner orchestration logic."""

import os
from unittest.mock import patch, call
import pytest
import tf


def _mock_backend():
    return tf.TfBackend(
        account_id="123456789012", region="eu-west-1", repo_name="my-repo"
    )


class TestTfRunnerPassesThroughSimpleSubcommands:
    def test_fmt_does_not_resolve_context(self):
        with patch("tf.TfContext.from_environment") as mock_context, \
             patch("tf.os.execvp"):
            tf.TfRunner(["fmt"]).call()

        mock_context.assert_not_called()

    def test_validate_does_not_resolve_context(self):
        with patch("tf.TfContext.from_environment") as mock_context, \
             patch("tf.os.execvp"):
            tf.TfRunner(["validate"]).call()

        mock_context.assert_not_called()

    def test_fmt_does_not_search_for_tfvars(self):
        with patch("tf.TfVarsFiles.find") as mock_find, \
             patch("tf.os.execvp"):
            tf.TfRunner(["fmt"]).call()

        mock_find.assert_not_called()

    def test_fmt_execs_terraform_directly(self):
        with patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["fmt"]).call()

        mock_execvp.assert_called_once_with("terraform", ["terraform", "fmt"])


class TestTfRunnerInit:
    def test_init_resolves_context(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp"):
            tf.TfRunner(["init"]).call()

    def test_init_injects_backend_config(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        backend = _mock_backend()
        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init"]).call()

        command = mock_execvp.call_args[0][1]
        assert f"-backend-config=key={backend.state_path}" in command
        assert f"-backend-config=bucket={backend.bucket}" in command
        assert "-backend-config=region=eu-west-1" in command
        assert "-backend-config=use_lockfile=true" in command
        assert not any(arg.startswith("-backend-config=dynamodb_table=")
                       for arg in command)
        assert "-backend-config=encrypt=true" in command

    def test_init_preserves_extra_args(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init", "-upgrade"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-upgrade" in command

    def test_init_uses_tf_state_file_name_env_var(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.setenv("TF_STATE_FILE_NAME", "environment-reporter.tfstate")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-backend-config=key=terraform/my-repo/" \
            "environment-reporter.tfstate" in command

    def test_init_defaults_to_main_tfstate_when_env_var_unset(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.delenv("TF_STATE_FILE_NAME", raising=False)

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-backend-config=key=terraform/my-repo/main.tfstate" in command

    def test_init_defaults_to_s3_lockfile_when_env_var_unset(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.delenv("TF_STATE_LOCK", raising=False)

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-backend-config=use_lockfile=true" in command
        assert not any(arg.startswith("-backend-config=dynamodb_table=")
                       for arg in command)

    def test_init_uses_dynamodb_when_tf_state_lock_dynamodb(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.setenv("TF_STATE_LOCK", "dynamodb")

        backend = _mock_backend()
        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["init"]).call()

        command = mock_execvp.call_args[0][1]
        assert f"-backend-config=dynamodb_table={backend.lock_table}" in command
        assert "-backend-config=use_lockfile=true" not in command

    def test_init_invalid_tf_state_lock_raises(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.setenv("TF_STATE_LOCK", "memcached")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp"):
            with pytest.raises(tf.TfError, match="Invalid TF_STATE_LOCK"):
                tf.TfRunner(["init"]).call()


class TestTfRunnerAutoInit:
    def test_plan_runs_init_before_command(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run") as mock_run, \
             patch("tf.os.execvp"):
            mock_run.return_value.returncode = 0
            tf.TfRunner(["plan"]).call()

        init_command = mock_run.call_args[0][0]
        assert init_command[0] == "terraform"
        assert init_command[1] == "init"
        assert any(arg.startswith("-backend-config=bucket=") for arg in init_command)

    def test_plan_fails_if_init_fails(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run") as mock_run, \
             patch("tf.os.execvp"):
            mock_run.return_value.returncode = 1

            with pytest.raises(tf.TfError, match="init failed"):
                tf.TfRunner(["plan"]).call()


class TestTfRunnerResolvesContextForVarFileSubcommands:
    def test_plan_resolves_context(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp"):
            tf.TfRunner(["plan"]).call()

    def test_apply_resolves_context(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp"):
            tf.TfRunner(["apply"]).call()


class TestTfRunnerShow:
    def test_show_sets_tf_data_dir(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.delenv("TF_DATA_DIR", raising=False)

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp"):
            tf.TfRunner(["show", "/tmp/staging.tfplan"]).call()

        assert os.environ["TF_DATA_DIR"] == ".terraform.123456789012-eu-west-1"

    def test_show_does_not_run_init(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.subprocess.run") as mock_run, \
             patch("tf.os.execvp"):
            tf.TfRunner(["show", "/tmp/staging.tfplan"]).call()

        mock_run.assert_not_called()

    def test_show_does_not_inject_var_files(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find") as mock_find, \
             patch("tf.os.execvp"):
            tf.TfRunner(["show", "/tmp/staging.tfplan"]).call()

        mock_find.assert_not_called()

    def test_show_passes_args_through(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["show", "/tmp/staging.tfplan"]).call()

        mock_execvp.assert_called_once_with(
            "terraform", ["terraform", "show", "/tmp/staging.tfplan"]
        )


class TestTfRunnerApplyAutoApprove:
    def test_apply_adds_auto_approve(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["apply"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-auto-approve" in command

    def test_apply_does_not_duplicate_auto_approve(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["apply", "-auto-approve"]).call()

        command = mock_execvp.call_args[0][1]
        assert command.count("-auto-approve") == 1

    def test_plan_does_not_add_auto_approve(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["plan"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-auto-approve" not in command

    def test_destroy_does_not_add_auto_approve(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["destroy"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-auto-approve" not in command


class TestTfRunnerPlanSavesOutput:
    def test_plan_adds_out_flag(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["plan"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-out=/tmp/staging.tfplan" in command

    def test_plan_out_flag_uses_profile_name(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "prod")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["plan"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-out=/tmp/prod.tfplan" in command

    def test_plan_does_not_override_explicit_out_flag(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["plan", "-out=my.tfplan"]).call()

        command = mock_execvp.call_args[0][1]
        assert "-out=my.tfplan" in command
        assert "-out=/tmp/staging.tfplan" not in command

    def test_apply_does_not_add_out_flag(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with patch("tf.TfBackend._get_repo_name", return_value="my-repo"), \
             patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"), \
             patch("tf.TfVarsFiles.find", return_value=tf.TfVarsFiles([])), \
             patch("tf.subprocess.run", return_value=type("R", (), {"returncode": 0})()), \
             patch("tf.os.execvp") as mock_execvp:
            tf.TfRunner(["apply"]).call()

        command = mock_execvp.call_args[0][1]
        assert not any(arg.startswith("-out=") for arg in command)
