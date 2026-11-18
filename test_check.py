import unittest

import check


class ProbeTests(unittest.TestCase):
    def test_up_on_first_try(self):
        calls = []
        ok, detail = check.probe('https://x', 200, fetch=lambda u: calls.append(u) or 200, sleep=lambda s: None)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)

    def test_down_only_after_all_tries_fail(self):
        calls = []

        def fetch(url):
            calls.append(url)
            raise TimeoutError('timed out')
        ok, detail = check.probe('https://x', 200, fetch=fetch, sleep=lambda s: None)
        self.assertFalse(ok)
        self.assertEqual(len(calls), 3)
        self.assertIn('timed out', detail)

    def test_recovers_on_a_later_try(self):
        replies = iter([503, 200])
        ok, _ = check.probe('https://x', 200, fetch=lambda u: next(replies), sleep=lambda s: None)
        self.assertTrue(ok)

    def test_wrong_status_is_down(self):
        ok, detail = check.probe('https://x', 302, fetch=lambda u: 200, sleep=lambda s: None)
        self.assertFalse(ok)
        self.assertIn('HTTP 200', detail)
        self.assertIn('expected 302', detail)


class PlanTests(unittest.TestCase):
    def test_down_without_issue_opens_one(self):
        actions = check.plan({'a': (False, 'HTTP 502')}, {})
        self.assertEqual(actions, [('open', 'a', 'HTTP 502')])

    def test_still_down_does_nothing(self):
        self.assertEqual(check.plan({'a': (False, 'x')}, {'a': 7}), [])

    def test_up_with_open_issue_closes_it(self):
        self.assertEqual(check.plan({'a': (True, '')}, {'a': 7}), [('close', 'a', 7, 'recovered')])

    def test_up_without_issue_does_nothing(self):
        self.assertEqual(check.plan({'a': (True, '')}, {}), [])

    def test_issue_for_a_site_no_longer_checked_is_closed(self):
        self.assertEqual(check.plan({}, {'gone': 9}), [('close', 'gone', 9, 'no longer monitored')])


class IssueMapTests(unittest.TestCase):
    def test_open_issues_are_mapped_by_site_label(self):
        issues = [
            {'number': 3, 'labels': [{'name': 'down'}, {'name': 'site:a'}]},
            {'number': 4, 'labels': [{'name': 'down'}]},
            {'number': 5, 'labels': [{'name': 'site:b'}, {'name': 'down'}], 'pull_request': {}},
        ]
        self.assertEqual(check.issues_by_site(issues), {'a': 3})


if __name__ == '__main__':
    unittest.main()
