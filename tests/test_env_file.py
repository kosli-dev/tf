"""Tests for tf.env file loading."""

import tf


class TestLoadEnvFile:
    def test_loads_key_value_pairs(self, tmp_path):
        (tmp_path / "tf.env").write_text("FOO=bar\nBAZ=qux\n")
        import os

        tf.load_env_file(str(tmp_path / "tf.env"))

        assert os.environ["FOO"] == "bar"
        assert os.environ["BAZ"] == "qux"
        del os.environ["FOO"]
        del os.environ["BAZ"]

    def test_ignores_comments(self, tmp_path):
        (tmp_path / "tf.env").write_text("# this is a comment\nFOO=bar\n")
        import os

        tf.load_env_file(str(tmp_path / "tf.env"))

        assert os.environ["FOO"] == "bar"
        del os.environ["FOO"]

    def test_ignores_blank_lines(self, tmp_path):
        (tmp_path / "tf.env").write_text("FOO=bar\n\n\nBAZ=qux\n")
        import os

        tf.load_env_file(str(tmp_path / "tf.env"))

        assert os.environ["FOO"] == "bar"
        assert os.environ["BAZ"] == "qux"
        del os.environ["FOO"]
        del os.environ["BAZ"]

    def test_does_nothing_when_file_missing(self, tmp_path):
        tf.load_env_file(str(tmp_path / "tf.env"))

    def test_does_not_override_existing_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FOO", "original")
        (tmp_path / "tf.env").write_text("FOO=overridden\n")

        tf.load_env_file(str(tmp_path / "tf.env"))

        import os
        assert os.environ["FOO"] == "original"
