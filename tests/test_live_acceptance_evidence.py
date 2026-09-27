from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from monitoring.kuma_sanitize import (
    REDACTED_PRESENT,
    SENSITIVE_MONITOR_FIELDS as SANITIZER_SENSITIVE_FIELDS,
    sanitize_config_document,
    sanitize_runtime_document,
)
from monitoring.migration import (
    SENSITIVE_MONITOR_FIELDS as MIGRATION_SENSITIVE_FIELDS,
    load_kuma_monitors,
    map_kuma_monitor,
)


class UptimeKumaEvidenceSanitizationTests(SimpleTestCase):
    def test_sensitive_field_policy_matches_migration_importer(self):
        self.assertEqual(SANITIZER_SENSITIVE_FIELDS, MIGRATION_SENSITIVE_FIELDS)

    def test_sensitive_configuration_is_redacted_but_remains_blocking(self):
        source = {
            "version": "2.5.0",
            "monitors": [
                {
                    "id": 7,
                    "name": "Authenticated service",
                    "type": "http",
                    "url": "https://service.example.test/health",
                    "interval": 60,
                    "timeout": 10,
                    "headers": {"Authorization": "Bearer reusable-secret"},
                }
            ],
        }
        sanitized, report = sanitize_config_document(source)
        serialized = json.dumps(sanitized)
        self.assertNotIn("reusable-secret", serialized)
        self.assertEqual(sanitized["monitors"][0]["headers"], REDACTED_PRESENT)
        self.assertEqual(report["monitors_with_redactions"], 1)

        mapping = map_kuma_monitor(sanitized["monitors"][0])
        self.assertFalse(mapping.supported)
        self.assertIn("manual-authentication-required", {issue.code for issue in mapping.issues})

    def test_url_credentials_and_query_are_removed_and_force_manual_review(self):
        sanitized, report = sanitize_config_document(
            {
                "monitors": [
                    {
                        "name": "Signed URL",
                        "type": "http",
                        "url": "https://user:password@example.test/health?token=secret#fragment",
                        "interval": 60,
                        "timeout": 10,
                    }
                ]
            }
        )
        monitor = sanitized["monitors"][0]
        serialized = json.dumps(sanitized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("token=secret", serialized)
        self.assertEqual(monitor["url"], "https://example.test/health?goreecloud_redacted=1")
        self.assertEqual(monitor["headers"], REDACTED_PRESENT)
        self.assertEqual(
            set(report["monitors"][0]["redacted_fields"]),
            {"url-credentials", "url-fragment", "url-query"},
        )
        self.assertFalse(map_kuma_monitor(monitor).supported)

    def test_malformed_port_with_url_credentials_does_not_crash_or_leak(self):
        sanitized, report = sanitize_config_document(
            {
                "monitors": [
                    {
                        "name": "Malformed signed URL",
                        "type": "http",
                        "url": "https://user:password@example.test:notaport/health?token=secret",
                        "interval": 60,
                        "timeout": 10,
                    }
                ]
            }
        )
        monitor = sanitized["monitors"][0]
        serialized = json.dumps(sanitized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("token=secret", serialized)
        self.assertEqual(monitor["url"], "https://example.test/health?goreecloud_redacted=1")
        self.assertEqual(monitor["headers"], REDACTED_PRESENT)
        self.assertIn("url-invalid-port", report["monitors"][0]["redacted_fields"])
        self.assertFalse(map_kuma_monitor(monitor).supported)

    def test_unknown_nonempty_fields_are_omitted_by_name_without_copying_value(self):
        sanitized, report = sanitize_config_document(
            {
                "monitors": [
                    {
                        "name": "Web",
                        "type": "http",
                        "url": "https://example.test/",
                        "interval": 60,
                        "timeout": 10,
                        "futureSecretLikeSetting": "do-not-copy-this-value",
                    }
                ]
            }
        )
        serialized = json.dumps(sanitized)
        self.assertNotIn("do-not-copy-this-value", serialized)
        self.assertIn("futureSecretLikeSetting", report["monitors"][0]["omitted_fields"])
        self.assertIn("futureSecretLikeSetting", sanitized["monitors"][0]["__goreecloud_omitted_fields"])

    def test_kuma_cli_v2_id_keyed_monitor_map_is_sanitized_and_sorted(self):
        sanitized, report = sanitize_config_document(
            {
                "23": {
                    "id": 23,
                    "name": "Second",
                    "type": "http",
                    "url": "https://second.example.test/",
                    "interval": 60,
                    "timeout": 10,
                },
                "2": {
                    "id": 2,
                    "name": "First",
                    "type": "http",
                    "url": "https://first.example.test/",
                    "interval": 60,
                    "timeout": 10,
                },
            }
        )
        self.assertEqual(report["source_format"], "kuma-cli-v2-monitor-map")
        self.assertEqual(report["source_monitors"], 2)
        self.assertEqual([monitor["id"] for monitor in sanitized["monitors"]], [2, 23])

        temp = self.enterContext(self._temporary_json(sanitized))
        monitors, metadata = load_kuma_monitors(temp)
        self.assertEqual(metadata["source_format"], "kuma-cli-config-export")
        self.assertEqual([monitor["id"] for monitor in monitors], [2, 23])

    def test_kuma_cli_v2_monitor_map_rejects_mismatched_monitor_id(self):
        with self.assertRaises(ValueError):
            sanitize_config_document(
                {
                    "2": {
                        "id": 3,
                        "name": "Mismatch",
                        "type": "http",
                        "url": "https://example.test/",
                    }
                }
            )

    def test_runtime_snapshot_keeps_only_comparison_fields(self):
        sanitized = sanitize_runtime_document(
            {
                "ok": True,
                "data": [
                    {
                        "id": 5,
                        "name": "Service",
                        "type": "http",
                        "active": True,
                        "url": "https://secret-target.example.test/private",
                        "heartbeat": {
                            "status": 1,
                            "ping": 42.5,
                            "msg": "private diagnostic content",
                        },
                    }
                ],
            }
        )
        serialized = json.dumps(sanitized)
        self.assertNotIn("secret-target", serialized)
        self.assertNotIn("private diagnostic", serialized)
        self.assertEqual(
            sanitized["data"][0],
            {
                "id": 5,
                "name": "Service",
                "type": "http",
                "active": True,
                "heartbeat": {"status": 1, "ping": 42.5},
            },
        )

    def test_config_only_monitor_list_is_not_runtime_evidence(self):
        with self.assertRaises(ValueError):
            sanitize_runtime_document(
                [
                    {
                        "id": 5,
                        "name": "Service",
                        "type": "http",
                        "active": True,
                        "url": "https://example.test/",
                    }
                ]
            )

    def test_sanitized_export_remains_compatible_with_existing_loader(self):
        sanitized, _ = sanitize_config_document(
            {
                "version": "2.5.0",
                "monitors": [
                    {
                        "name": "Web",
                        "type": "http",
                        "url": "https://example.test/",
                        "interval": 60,
                        "timeout": 10,
                    }
                ],
            }
        )
        temp = self.enterContext(self._temporary_json(sanitized))
        monitors, metadata = load_kuma_monitors(temp)
        self.assertEqual(metadata["source_format"], "kuma-cli-config-export")
        self.assertEqual(len(monitors), 1)
        self.assertTrue(map_kuma_monitor(monitors[0]).supported)

    def test_collector_module_compiles_and_parses_docker_summary(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "collect_live_acceptance_evidence.py"
        spec = importlib.util.spec_from_file_location("live_evidence_collector", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = module._parse_docker_ps("uptime-kuma\timage:tag\tUp 1 hour\t3001/tcp\tproxy\n")
        self.assertEqual(rows[0]["name"], "uptime-kuma")
        self.assertEqual(rows[0]["networks"], "proxy")

        url, source = module._derive_kuma_url(
            {
                "uptime_kuma": {
                    "networks": [
                        {"name": "manager-uptime", "uptime_ipv4": "172.20.0.2"},
                        {"name": "proxy", "uptime_ipv4": "172.19.0.50"},
                    ]
                }
            },
            None,
        )
        self.assertEqual(url, "http://172.19.0.50:3001")
        self.assertEqual(source, "docker-proxy-network")

    def test_retired_kuma_collector_requires_explicit_historical_acknowledgement(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "collect_live_acceptance_evidence.py"
        completed = subprocess.run(
            [sys.executable, str(path), "--no-archive", "--skip-kuma"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--historical-predecessor-evidence is required", completed.stderr)

    class _temporary_json:
        def __init__(self, document):
            import tempfile

            self.document = document
            self.directory = tempfile.TemporaryDirectory()
            self.path = Path(self.directory.name) / "export.json"

        def __enter__(self):
            self.path.write_text(json.dumps(self.document), encoding="utf-8")
            return self.path

        def __exit__(self, exc_type, exc, tb):
            self.directory.cleanup()
