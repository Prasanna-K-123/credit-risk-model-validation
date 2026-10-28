"""Fail closed before release writes when reviewed identities diverge."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_guard import REPOSITORY, publish, release_text, tag_commit, validate_request, verify_refs

SHA = 'a' * 40
TAG = 'v1.1.0'


class FakeAPI:
    def __init__(self):
        self.main = SHA
        self.target = SHA
        self.release = None
        self.writes = []
        self.refs_read = 0
        self.move_on_second_check = False

    def __call__(self, path, payload=None, missing_ok=False):
        if path == '/branches/main':
            self.refs_read += 1
            if self.move_on_second_check and self.refs_read > 1:
                self.main = 'b' * 40
            return {'commit': {'sha': self.main}}
        if path == '/git/ref/tags/' + TAG:
            if self.target is None:
                raise RuntimeError('HTTP 404')
            return {'object': {'type': 'commit', 'sha': self.target}}
        if path == '/releases/tags/' + TAG:
            return self.release
        if path == '/releases' and payload:
            self.writes.append((path, copy.deepcopy(payload)))
            self.release = {**payload, 'html_url': 'https://example.test/release'}
            return self.release
        raise AssertionError('Unexpected API call: ' + path)


class ReleaseGuardTests(unittest.TestCase):
    def environment(self):
        return {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REPOSITORY': REPOSITORY,
                'GITHUB_REF': 'refs/heads/main', 'REVIEWED_COMMIT': SHA, 'GITHUB_SHA': SHA,
                'RELEASE_TAG': TAG}

    def test_context_must_bind_review_to_dispatch_and_checkout(self):
        self.assertEqual(validate_request(self.environment(), SHA), (SHA, TAG))
        for key, value in [('GITHUB_EVENT_NAME', 'push'), ('GITHUB_REPOSITORY', 'other/repo'),
                           ('GITHUB_REF', 'refs/heads/other'), ('REVIEWED_COMMIT', 'a'*7),
                           ('GITHUB_SHA', 'b'*40), ('RELEASE_TAG', '../main')]:
            env = self.environment(); env[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_request(env, SHA)
        with self.assertRaises(ValueError):
            validate_request(self.environment(), 'b'*40)

    def test_missing_tag_is_not_created(self):
        api = FakeAPI(); api.target = None
        with self.assertRaises(RuntimeError):
            publish(api, SHA, TAG)
        self.assertFalse(api.writes)

    def test_changed_main_or_tag_blocks_all_writes(self):
        for field in ['main', 'target']:
            api = FakeAPI(); setattr(api, field, 'b'*40)
            with self.subTest(field=field), self.assertRaises(ValueError):
                publish(api, SHA, TAG)
            self.assertFalse(api.writes)

    def test_main_is_rechecked_immediately_before_publication(self):
        api = FakeAPI(); api.move_on_second_check = True
        with self.assertRaises(ValueError):
            publish(api, SHA, TAG)
        self.assertFalse(api.writes)

    def test_release_creation_has_no_tag_mutation_and_replay_is_idempotent(self):
        api = FakeAPI()
        first = publish(api, SHA, TAG)
        self.assertEqual(publish(api, SHA, TAG), first)
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(api.writes[0][0], '/releases')
        self.assertEqual(api.writes[0][1]['target_commitish'], SHA)

    def test_existing_different_release_is_never_overwritten(self):
        api = FakeAPI(); title, body = release_text(SHA, TAG)
        api.release = {'tag_name': TAG, 'name': title, 'body': body+' modified',
                       'draft': False, 'prerelease': False}
        with self.assertRaises(ValueError):
            publish(api, SHA, TAG)
        self.assertFalse(api.writes)

    def test_annotated_tag_resolution_and_cycle_rejection(self):
        def annotated(path):
            if path.startswith('/git/ref/'):
                return {'object': {'type': 'tag', 'sha': 'b'*40}}
            return {'object': {'type': 'commit', 'sha': SHA}}
        self.assertEqual(tag_commit(annotated, TAG), SHA)
        def cycle(path):
            return {'object': {'type': 'tag', 'sha': 'b'*40}}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            tag_commit(cycle, TAG)


if __name__ == '__main__':
    unittest.main()
