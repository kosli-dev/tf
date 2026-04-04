"""Tests for TfBackend state configuration."""

import hashlib
from unittest.mock import patch
import tf


class TestTfBackendBucket:
    def test_bucket_name_is_hashed_environment_id(self):
        backend = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                               repo_name="my-repo")
        env_id = "123456789012-eu-west-1"
        expected_hash = hashlib.sha1(env_id.encode()).hexdigest()

        assert backend.bucket == f"terraform-state-{expected_hash}"

    def test_bucket_name_varies_by_account(self):
        backend_a = tf.TfBackend(account_id="111111111111", region="eu-west-1",
                                  repo_name="my-repo")
        backend_b = tf.TfBackend(account_id="222222222222", region="eu-west-1",
                                  repo_name="my-repo")

        assert backend_a.bucket != backend_b.bucket

    def test_bucket_name_varies_by_region(self):
        backend_a = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                                  repo_name="my-repo")
        backend_b = tf.TfBackend(account_id="123456789012", region="us-east-1",
                                  repo_name="my-repo")

        assert backend_a.bucket != backend_b.bucket


class TestTfBackendLockTable:
    def test_lock_table_matches_bucket(self):
        backend = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                               repo_name="my-repo")

        assert backend.lock_table == backend.bucket


class TestTfBackendStatePath:
    def test_state_path_uses_repo_name(self):
        backend = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                               repo_name="my-repo")

        assert backend.state_path == "terraform/my-repo/main.tfstate"

    def test_state_path_varies_by_repo(self):
        backend_a = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                                  repo_name="repo-a")
        backend_b = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                                  repo_name="repo-b")

        assert backend_a.state_path != backend_b.state_path


class TestTfBackendDataDir:
    def test_data_dir_includes_environment_id(self):
        backend = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                               repo_name="my-repo")

        assert backend.data_dir == ".terraform.123456789012-eu-west-1"

    def test_data_dir_varies_by_account(self):
        backend_a = tf.TfBackend(account_id="111111111111", region="eu-west-1",
                                  repo_name="my-repo")
        backend_b = tf.TfBackend(account_id="222222222222", region="eu-west-1",
                                  repo_name="my-repo")

        assert backend_a.data_dir != backend_b.data_dir

    def test_data_dir_varies_by_region(self):
        backend_a = tf.TfBackend(account_id="123456789012", region="eu-west-1",
                                  repo_name="my-repo")
        backend_b = tf.TfBackend(account_id="123456789012", region="us-east-1",
                                  repo_name="my-repo")

        assert backend_a.data_dir != backend_b.data_dir


class TestTfBackendRepoName:
    def test_reads_repo_name_from_git_remote(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 0
            mock_subprocess.run.return_value.stdout = \
                "git@github.com:kosli-dev/terraform-server.git\n"

            assert tf.TfBackend._get_repo_name() == "terraform-server"

    def test_strips_dot_git_suffix(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 0
            mock_subprocess.run.return_value.stdout = \
                "https://github.com/kosli-dev/my-repo.git\n"

            assert tf.TfBackend._get_repo_name() == "my-repo"

    def test_handles_https_url_without_dot_git(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 0
            mock_subprocess.run.return_value.stdout = \
                "https://github.com/kosli-dev/my-repo\n"

            assert tf.TfBackend._get_repo_name() == "my-repo"

    def test_raises_when_not_a_git_repo(self):
        import pytest
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 128
            mock_subprocess.run.return_value.stdout = ""

            with pytest.raises(tf.TfError, match="not a git repo"):
                tf.TfBackend._get_repo_name()
