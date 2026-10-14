#!/usr/bin/env python3
"""Tests for OpenCarnet — stdlib only, no network, no personal config touched.

Run:
    python3 -m unittest discover -s tests -t .
    # or
    python3 tests/test_opencarnet.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _pivot as P            # noqa: E402
import compile as C           # noqa: E402
import templating             # noqa: E402

COMPILE = SCRIPTS / "compile.py"
EXAMPLE = ROOT / "assets" / "example.analysis.json"


def run_compile(*args):
    return subprocess.run([sys.executable, str(COMPILE), *args],
                          capture_output=True, text=True)


def write_analysis(path: Path, items, src="https://www.instagram.com/reel/ABC123/"):
    path.write_text(json.dumps({"id": "t", "source_url": src, "extraction": items},
                               ensure_ascii=False), encoding="utf-8")
    return path


def item(name, **kw):
    base = {"type_contenu": "reference", "nom": name, "resume": "a summary",
            "confiance": "haute", "themes": ["general"]}
    base.update(kw)
    return base


class TempHome:
    """Point HOME (and the default config path) at a throwaway dir."""

    def __init__(self, home: Path):
        self.home = home
        self.saved = {}

    def __enter__(self):
        for k in ("HOME", "OPENCARNET_CONFIG", "OPENCARNET_LANG",
                  "INSTAGRAM_SAVED_CONFIG", "LC_ALL", "LC_MESSAGES", "LANG"):
            self.saved[k] = os.environ.get(k)
            os.environ.pop(k, None)
        os.environ["HOME"] = str(self.home)
        os.environ["LC_ALL"] = "C"
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --------------------------------------------------------------------------- #
class PivotTest(unittest.TestCase):
    def test_canal_from_host_not_substring(self):
        self.assertEqual(P.canal_from_url("https://www.netflix.com/title/1"), "")
        self.assertEqual(P.canal_from_url("https://www.dropbox.com/s/x"), "")
        self.assertEqual(P.canal_from_url("https://x.com/u/status/1"), "tweet")
        self.assertEqual(P.canal_from_url("https://twitter.com/u/status/1"), "tweet")
        self.assertEqual(P.canal_from_url("https://www.instagram.com/reel/A/"), "reel")
        self.assertEqual(P.canal_from_url("https://www.instagram.com/p/A/"), "post")
        self.assertEqual(P.canal_from_url("https://www.tiktok.com/@a/video/1"), "tiktok")
        self.assertEqual(P.canal_from_url("https://youtu.be/abcdef"), "youtube")

    def test_canal_without_scheme(self):
        self.assertEqual(P.canal_from_url("instagram.com/reel/abc"), "reel")
        self.assertEqual(P.canal_from_url("x.com/u/status/1"), "tweet")

    def test_canonical_adds_scheme(self):
        self.assertEqual(P.canonical_url("instagram.com/reel/abc"),
                         "https://instagram.com/reel/abc")
        self.assertEqual(P.canonical_url("https://twitter.com/u/status/12"),
                         "https://x.com/i/web/status/12")

    def test_iso_date(self):
        self.assertEqual(P.iso_date(1700000000), "2023-11-14")
        self.assertEqual(P.iso_date("1700000000000"), "2023-11-14")  # ms
        self.assertEqual(P.iso_date("2024-01-02T03:04:05Z"), "2024-01-02")
        self.assertEqual(P.iso_date("not a date"), "")
        self.assertEqual(P.iso_date("999999999999"), "")             # out of range, no crash

    def test_make_item_id_stable(self):
        a = P.make_item("https://x.com/i/web/status/1")
        b = P.make_item("x.com/u/status/1")  # same canonical URL
        self.assertEqual(a["id"], b["id"])

    def test_dedup_items(self):
        rows = [P.make_item("https://x.com/u/status/1"),
                P.make_item("https://x.com/u/status/1")]
        self.assertEqual(len(P.dedup_items(rows)), 1)


# --------------------------------------------------------------------------- #
class CompileHelpersTest(unittest.TestCase):
    def test_dedup_key_unicode(self):
        self.assertEqual(C.dedup_key("My_Note"), C.dedup_key("My Note"))
        self.assertEqual(C.dedup_key("Привет мир"), C.dedup_key("привет  мир"))
        self.assertEqual(C.dedup_key("Café"), C.dedup_key("cafe"))
        # distinct punctuation-only titles must not collide on an empty key
        self.assertNotEqual(C.dedup_key("！！！"), C.dedup_key("？？？"))

    def test_yaml_str(self):
        self.assertTrue(C.yaml_str("line1\nline2").startswith('"'))
        self.assertTrue(C.yaml_str("- dash").startswith('"'))
        self.assertTrue(C.yaml_str("a: b").startswith('"'))
        self.assertEqual(C.yaml_str("plain"), "plain")

    def test_within_root(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "sub").mkdir()
            outside = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, outside, True)
            os.symlink(outside, root / "link")
            self.assertTrue(C.within_root(root, root / "sub" / "x"))
            self.assertTrue(C.within_root(root, root / "link"))   # lexical, no symlink follow
            self.assertFalse(C.within_root(root, root / ".." / "etc"))
            self.assertFalse(C.within_root(root, Path("/etc/passwd")))

    def test_has_substance(self):
        self.assertFalse(C.has_substance({"liens": ["https://x.com/i/web/status/1"]}))
        self.assertTrue(C.has_substance({"resume": "r"}))
        self.assertTrue(C.has_substance({"citation_cle": "a quote"}))
        self.assertTrue(C.has_substance({"donnees": {"ingredients": ["flour"]}}))

    def test_managed_dirs_scoped(self):
        cfg = {"review_dir": "to-review",
               "routes": {"r": {"family": "resource", "folder_if_ai": "tech"},
                          "w": {"family": "resource", "folder": "."}},
               "themes": {"general": "general", "tech": "tech"},
               "formats": {"recipe": {"folder": "Recipes"}}}
        dirs = C.managed_dirs(cfg)
        for d in ("to-review", "tech", "general", "Recipes"):
            self.assertIn(d, dirs)
        self.assertNotIn(".", dirs)

    def test_resolve_folder_never_none(self):
        cfg = {"themes": {"general": "general"}, "default_theme": "general",
               "routes": {"p": {"family": "prompt"}}}
        self.assertEqual(C.resolve({"type_contenu": "p", "themes": []}, cfg)["folder"], ".")

    def test_safe_name_and_untitled(self):
        self.assertEqual(C.safe_name("a/b:c", "en"), "a-b-c")
        self.assertEqual(C.safe_name("", "en"), "Untitled")
        self.assertEqual(C.safe_name("", "fr"), "Sans titre")

    def test_source_column(self):
        cols = {"nom": "{nom}", "lien": "{source_url}"}
        self.assertEqual(C.source_column(cols), "lien")
        self.assertEqual(C.source_column({"nom": "{nom}"}), "source")


# --------------------------------------------------------------------------- #
class I18nTest(unittest.TestCase):
    def test_t_messages(self):
        self.assertIn("created", C.T("en", "created"))
        self.assertEqual(C.T("fr", "created"), "créé")
        self.assertEqual(C.T("fr", "missing_key_xyz"), "missing_key_xyz")

    def test_template_booleans(self):
        ctx = {"flag": True}
        self.assertEqual(templating.render("{flag}", ctx, lang="en"), "yes")
        self.assertEqual(templating.render("{flag}", ctx, lang="fr"), "oui")

    def test_default_lang_priority(self):
        with tempfile.TemporaryDirectory() as t:
            with TempHome(Path(t)):
                cfg = Path(t) / "cfg.json"
                cfg.write_text('{"language": "fr"}')
                os.environ["OPENCARNET_CONFIG"] = str(cfg)
                self.assertEqual(P.default_lang(), "fr")
                os.environ["OPENCARNET_LANG"] = "en"          # explicit wins
                self.assertEqual(P.default_lang(), "en")
                os.environ.pop("OPENCARNET_LANG")
                # default path (~/.config/opencarnet/config.json) is also read
                os.environ.pop("OPENCARNET_CONFIG")
                d = Path(t) / ".config" / "opencarnet"
                d.mkdir(parents=True)
                (d / "config.json").write_text('{"language": "fr"}')
                self.assertEqual(P.default_lang(), "fr")
                (d / "config.json").unlink()
                self.assertEqual(P.default_lang(), "en")      # locale C → en
                os.environ["LC_ALL"] = "fr_FR.UTF-8"          # no config → system locale
                self.assertEqual(P.default_lang(), "fr")


# --------------------------------------------------------------------------- #
class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = self.tmp / "config.json"
        self.root = self.tmp / "notes"
        r = run_compile("--init", "--force", "--config", str(self.cfg),
                        "--tool", "plain-markdown", "--language", "en",
                        "--root", str(self.root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cfg_data = json.loads(self.cfg.read_text())

    def _md(self):
        return [p for p in self.root.rglob("*.md") if not p.name.startswith("Index")]

    def test_markdown_filing(self):
        a = write_analysis(self.tmp / "a.json", [item("One"), item("Two", themes=["tech"])])
        r = run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertIn("2 created", r.stdout)
        self.assertEqual(len(self._md()), 2)

    def test_path_traversal_blocked(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        a = write_analysis(self.tmp / "a.json", [
            item("Evil", dossier_cible=str(outside)),
            item("Evil2", dossier_cible="../../evil2"),
        ])
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertFalse((outside / "Evil.md").exists())
        self.assertFalse((self.root / ".." / ".." / "evil2").exists())
        self.assertTrue((self.root / "to-review" / "Evil.md").exists())

    def test_dry_run_counts_and_writes_nothing(self):
        a = write_analysis(self.tmp / "a.json", [item("Dup"), item("Dup")])
        r = run_compile("--analysis", str(a), "--config", str(self.cfg), "--dry-run")
        self.assertIn("1 created", r.stdout)
        self.assertIn("1 duplicate", r.stdout)
        self.assertEqual(self._md(), [])

    def test_no_content_goes_to_review(self):
        a = write_analysis(self.tmp / "a.json", [
            item("Bare", resume="", type_contenu="reference"),
        ])
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertTrue((self.root / "to-review" / "Bare.md").exists())

    def test_unicode_titles_kept_apart(self):
        a = write_analysis(self.tmp / "a.json", [
            item("Привет мир"), item("東京ラーメン")])
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertEqual(len(self._md()), 2)

    def test_csv_custom_source_column_and_merge(self):
        self.cfg_data["output"] = {"format": "csv",
                                   "columns": {"nom": "{nom}", "lien": "{source_url}"}}
        self.cfg.write_text(json.dumps(self.cfg_data))
        a1 = write_analysis(self.tmp / "a1.json", [item("C")],
                            src="https://x.com/i/web/status/1")
        a2 = write_analysis(self.tmp / "a2.json", [item("C")],
                            src="https://x.com/i/web/status/999")
        run_compile("--analysis", str(a1), "--config", str(self.cfg))
        run_compile("--analysis", str(a2), "--config", str(self.cfg))
        text = (self.root / "opencarnet.csv").read_text()
        self.assertIn("lien", text.splitlines()[0])
        self.assertNotIn("source", text.splitlines()[0])
        self.assertIn("status/999", text)

    def test_jsonl_preserves_invalid_line(self):
        self.cfg_data["output"] = {"format": "jsonl"}
        self.cfg.write_text(json.dumps(self.cfg_data))
        a = write_analysis(self.tmp / "a.json", [item("J")])
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        f = self.root / "opencarnet.jsonl"
        f.write_text(f.read_text() + "{ not json }\n")
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertIn("{ not json }", f.read_text())

    def test_duplicates_scope_not_whole_root(self):
        # a user note at the root (outside destination folders) must be left alone
        (self.root / "Foo.md").write_text("---\nsource: x\n---\nuser note\n")
        a = write_analysis(self.tmp / "a.json", [item("Foo")])
        run_compile("--analysis", str(a), "--config", str(self.cfg))
        self.assertNotIn("duplicate", (self.root / "Foo.md").read_text().lower())
        self.assertTrue((self.root / "general" / "Foo.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
