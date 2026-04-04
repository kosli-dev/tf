"""Tests for TfVarsFiles discovery."""

from unittest.mock import patch
import tf


def make_context(profile="staging", region="eu-west-1"):
    return tf.TfContext(profile=profile, region=region)


class TestTfVarsFilesResolve:
    def test_finds_base_tfvars(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [str(tmp_path / "staging.tfvars")]

    def test_finds_regional_tfvars(self, tmp_path):
        (tmp_path / "staging-eu-west-1.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [str(tmp_path / "staging-eu-west-1.tfvars")]

    def test_finds_both_base_and_regional(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()
        (tmp_path / "staging-eu-west-1.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [
            str(tmp_path / "staging.tfvars"),
            str(tmp_path / "staging-eu-west-1.tfvars"),
        ]

    def test_base_comes_before_regional(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()
        (tmp_path / "staging-eu-west-1.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        files = list(tfvars)
        assert files[0].endswith("staging.tfvars")
        assert files[1].endswith("staging-eu-west-1.tfvars")

    def test_returns_empty_when_no_match(self, tmp_path):
        (tmp_path / "prod.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == []

    def test_ignores_unrelated_tfvars(self, tmp_path):
        (tmp_path / "prod.tfvars").touch()
        (tmp_path / "dev.tfvars").touch()
        (tmp_path / "staging.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [str(tmp_path / "staging.tfvars")]

    def test_is_not_using_deprecated_filenames(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()

        tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert not tfvars.is_using_deprecated_filenames()

    def test_empty_result_is_not_deprecated(self, tmp_path):
        with patch("tf.TfVarsFiles._get_account_id", return_value=None):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert not tfvars.is_using_deprecated_filenames()


class TestTfVarsFilesAccountIdFallback:
    def test_falls_back_to_account_id(self, tmp_path):
        (tmp_path / "123456789012.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [str(tmp_path / "123456789012.tfvars")]

    def test_falls_back_to_account_id_with_region(self, tmp_path):
        (tmp_path / "123456789012.tfvars").touch()
        (tmp_path / "123456789012-eu-west-1.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [
            str(tmp_path / "123456789012.tfvars"),
            str(tmp_path / "123456789012-eu-west-1.tfvars"),
        ]

    def test_profile_takes_precedence_over_account_id(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()
        (tmp_path / "123456789012.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value="123456789012") as mock:
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == [str(tmp_path / "staging.tfvars")]
        mock.assert_not_called()

    def test_no_fallback_when_sts_fails(self, tmp_path):
        (tmp_path / "123456789012.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value=None):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert list(tfvars) == []

    def test_is_using_deprecated_filenames(self, tmp_path):
        (tmp_path / "123456789012.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert tfvars.is_using_deprecated_filenames()

    def test_profile_match_is_not_deprecated(self, tmp_path):
        (tmp_path / "staging.tfvars").touch()

        with patch("tf.TfVarsFiles._get_account_id", return_value="123456789012"):
            tfvars = tf.TfVarsFiles.find(make_context(), str(tmp_path))

        assert not tfvars.is_using_deprecated_filenames()


class TestGetAccountId:
    def test_returns_account_id_from_sts(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 0
            mock_subprocess.run.return_value.stdout = "123456789012\n"

            assert tf.TfVarsFiles._get_account_id() == "123456789012"

    def test_calls_sts_get_caller_identity(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 0
            mock_subprocess.run.return_value.stdout = "123456789012\n"

            tf.TfVarsFiles._get_account_id()

            mock_subprocess.run.assert_called_once_with(
                ["aws", "sts", "get-caller-identity",
                 "--query", "Account", "--output", "text"],
                capture_output=True,
                text=True,
            )

    def test_returns_none_when_sts_fails(self):
        with patch("tf.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value.returncode = 1
            mock_subprocess.run.return_value.stdout = ""

            assert tf.TfVarsFiles._get_account_id() is None
