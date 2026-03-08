"""Tests for pure helpers in workspace/local_exec/validation.py.

Stdlib-only, loaded with a unique module name.
We force jsonschema=None by loading before any jsonschema import
(or patch it) to ensure lite-mode paths are tested.

Covers:
- validator_mode
- _ensure
- _require_keys
- _validate_job_lite
- _validate_schema_lite (repo_index_task, test_runner_task, doc_compactor_task)
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = REPO_ROOT / "workspace" / "local_exec" / "validation.py"

# Force jsonschema to appear unavailable so lite-mode is used
_jschema_stub = types.ModuleType("jsonschema")
_jschema_stub.validate = None  # None means it's there but not None-check-safe
# Actually we want jsonschema IS None in the module, so we inject after load.
_spec = _ilu.spec_from_file_location("local_exec_validation_real", str(VALIDATION_PATH))
val = _ilu.module_from_spec(_spec)
sys.modules["local_exec_validation_real"] = val
# Temporarily make jsonschema unavailable so module sets it to None
_saved_jsonschema = sys.modules.pop("jsonschema", None)
_spec.loader.exec_module(val)
# Restore if needed
if _saved_jsonschema is not None:
    sys.modules["jsonschema"] = _saved_jsonschema
# Force lite mode for tests
val.jsonschema = None


def _valid_job() -> dict:
    """Return a minimal valid job dict."""
    return {
        "job_id": "job-abc123def456",
        "job_type": "repo_index_task",
        "created_at_utc": "2026-03-07T12:00:00Z",
        "payload": {"include_globs": ["**/*.py"], "max_files": 1000, "max_file_bytes": 65536},
        "budgets": {
            "max_wall_time_sec": 300,
            "max_tool_calls": 50,
            "max_output_bytes": 1048576,
            "max_concurrency_slots": 2,
        },
        "tool_policy": {
            "allow_network": False,
            "allow_subprocess": True,
            "allowed_tools": ["read_file"],
        },
    }


# ---------------------------------------------------------------------------
# validator_mode
# ---------------------------------------------------------------------------

class TestValidatorMode(unittest.TestCase):
    """Tests for validator_mode() — reports lite vs jsonschema mode."""

    def test_returns_string(self):
        self.assertIsInstance(val.validator_mode(), str)

    def test_lite_mode_when_no_jsonschema(self):
        # val.jsonschema is set to None above
        self.assertEqual(val.validator_mode(), "lite")


# ---------------------------------------------------------------------------
# _ensure
# ---------------------------------------------------------------------------

class TestEnsure(unittest.TestCase):
    """Tests for _ensure() — raises ValidationError when condition is False."""

    def test_true_does_not_raise(self):
        val._ensure(True, "should not raise")

    def test_false_raises_validation_error(self):
        with self.assertRaises(val.ValidationError):
            val._ensure(False, "error message")

    def test_error_message_in_exception(self):
        try:
            val._ensure(False, "specific error text")
        except val.ValidationError as e:
            self.assertIn("specific error text", str(e))

    def test_validation_error_is_value_error(self):
        self.assertTrue(issubclass(val.ValidationError, ValueError))


# ---------------------------------------------------------------------------
# _require_keys
# ---------------------------------------------------------------------------

class TestRequireKeys(unittest.TestCase):
    """Tests for _require_keys() — checks required + allowed keys."""

    def test_valid_passes(self):
        obj = {"a": 1, "b": 2}
        val._require_keys(obj, required={"a", "b"}, allowed={"a", "b"}, where="test")

    def test_missing_required_raises(self):
        with self.assertRaises(val.ValidationError):
            val._require_keys({"a": 1}, required={"a", "b"}, allowed={"a", "b"}, where="test")

    def test_extra_keys_raises(self):
        with self.assertRaises(val.ValidationError):
            val._require_keys({"a": 1, "b": 2, "c": 3}, required={"a"}, allowed={"a", "b"}, where="test")

    def test_optional_keys_allowed(self):
        obj = {"a": 1}  # "b" is optional
        val._require_keys(obj, required={"a"}, allowed={"a", "b"}, where="test")


# ---------------------------------------------------------------------------
# _validate_job_lite
# ---------------------------------------------------------------------------

class TestValidateJobLite(unittest.TestCase):
    """Tests for _validate_job_lite() — lite schema validation of a job dict."""

    def test_valid_job_passes(self):
        val._validate_job_lite(_valid_job())

    def test_invalid_job_id_prefix_raises(self):
        job = _valid_job()
        job["job_id"] = "abc-123def456789"  # no "job-" prefix
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_invalid_job_type_raises(self):
        job = _valid_job()
        job["job_type"] = "unknown_task"
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_invalid_created_at_utc_raises(self):
        job = _valid_job()
        job["created_at_utc"] = "not-a-timestamp"
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_missing_required_field_raises(self):
        job = _valid_job()
        del job["payload"]
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_max_wall_time_too_large_raises(self):
        job = _valid_job()
        job["budgets"]["max_wall_time_sec"] = 99999
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_allow_network_must_be_bool_raises(self):
        job = _valid_job()
        job["tool_policy"]["allow_network"] = "yes"
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_allowed_tools_must_be_list_raises(self):
        job = _valid_job()
        job["tool_policy"]["allowed_tools"] = "read_file"
        with self.assertRaises(val.ValidationError):
            val._validate_job_lite(job)

    def test_all_valid_job_types_pass(self):
        for jtype in ("repo_index_task", "test_runner_task", "doc_compactor_task"):
            job = _valid_job()
            job["job_type"] = jtype
            val._validate_job_lite(job)  # should not raise


# ---------------------------------------------------------------------------
# _validate_schema_lite — repo_index_task
# ---------------------------------------------------------------------------

class TestValidateSchemeLiteRepoIndex(unittest.TestCase):
    """Tests for _validate_schema_lite() with repo_index_task schema."""

    SCHEMA = "repo_index_task.schema.json"

    def _valid(self):
        return {"include_globs": ["**/*.py"], "max_files": 1000, "max_file_bytes": 65536}

    def test_valid_passes(self):
        val._validate_schema_lite(self.SCHEMA, self._valid())

    def test_missing_include_globs_raises(self):
        p = self._valid()
        del p["include_globs"]
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_max_files_too_large_raises(self):
        p = self._valid()
        p["max_files"] = 999999
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_with_optional_exclude_globs(self):
        p = self._valid()
        p["exclude_globs"] = ["*.txt"]
        val._validate_schema_lite(self.SCHEMA, p)

    def test_invalid_extra_key_raises(self):
        p = self._valid()
        p["unknown_key"] = "value"
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)


# ---------------------------------------------------------------------------
# _validate_schema_lite — test_runner_task
# ---------------------------------------------------------------------------

class TestValidateSchemeLiteTestRunner(unittest.TestCase):
    """Tests for _validate_schema_lite() with test_runner_task schema."""

    SCHEMA = "test_runner_task.schema.json"

    def _valid(self):
        return {"commands": [["python3", "-m", "pytest"]], "timeout_sec": 60}

    def test_valid_passes(self):
        val._validate_schema_lite(self.SCHEMA, self._valid())

    def test_missing_commands_raises(self):
        p = self._valid()
        del p["commands"]
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_timeout_too_large_raises(self):
        p = self._valid()
        p["timeout_sec"] = 99999
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_with_optional_cwd(self):
        p = self._valid()
        p["cwd"] = "/tmp"
        val._validate_schema_lite(self.SCHEMA, p)


# ---------------------------------------------------------------------------
# _validate_schema_lite — doc_compactor_task
# ---------------------------------------------------------------------------

class TestValidateSchemeLiteDocCompactor(unittest.TestCase):
    """Tests for _validate_schema_lite() with doc_compactor_task schema."""

    SCHEMA = "doc_compactor_task.schema.json"

    def _valid(self):
        return {
            "inputs": ["workspace/docs/README.md"],
            "max_input_bytes": 1048576,
            "max_output_bytes": 65536,
        }

    def test_valid_passes(self):
        val._validate_schema_lite(self.SCHEMA, self._valid())

    def test_empty_inputs_raises(self):
        p = self._valid()
        p["inputs"] = []
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_max_input_bytes_too_small_raises(self):
        p = self._valid()
        p["max_input_bytes"] = 10  # < 128
        with self.assertRaises(val.ValidationError):
            val._validate_schema_lite(self.SCHEMA, p)

    def test_with_optional_title(self):
        p = self._valid()
        p["title"] = "My Doc"
        val._validate_schema_lite(self.SCHEMA, p)


if __name__ == "__main__":
    unittest.main()
