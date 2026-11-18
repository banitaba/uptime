"""Outside uptime check for the Lightsail sites, run by GitHub Actions.

The server's own watchdog reports problems to BaniSupport, but when the whole
server is down neither of them can. This check runs from GitHub: a site is down
only if all 3 tries (20 s apart) fail. A down site gets one open issue (labels
`down` + `site:<name>`), which GitHub emails to the repo owner; it is commented
and closed when the site is back. Still down: nothing new, so one outage is one
email. Python standard library only.
"""
import concurrent.futures
import datetime
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

TRIES, WAIT, TIMEOUT = 3, 20, 10
OWNER_MENTION = '@banitaba'
TEST_SITE = {'name': 'uptime-selftest', 'url': 'http://127.0.0.1:1/', 'expect': 200}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # report 3xx as-is (auth.banilabs.com is expected to answer 302)


_opener = urllib.request.build_opener(_NoRedirect)


def http_status(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'banitaba-uptime'})
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def probe(url, expect, fetch=http_status, sleep=time.sleep):
    """(ok, detail). Down only when every try fails."""
    detail = ''
    for attempt in range(TRIES):
        if attempt:
            sleep(WAIT)
        try:
            status = fetch(url)
            if status == expect:
                return True, ''
            detail = f'HTTP {status} (expected {expect})'
        except Exception as error:
            detail = f'{type(error).__name__}: {str(error)[:200]}'
    return False, detail


def issues_by_site(issues):
    """Open `down` issues keyed by the site in their `site:<name>` label (pull requests ignored)."""
    found = {}
    for issue in issues:
        if 'pull_request' in issue:
            continue
        names = [label['name'] for label in issue.get('labels', [])]
        if 'down' in names:
            for name in names:
                if name.startswith('site:'):
                    found[name[5:]] = issue['number']
    return found


def plan(results, open_issues):
    """results: {site: (ok, detail)}; open_issues: {site: number}. Returns actions to take."""
    actions = []
    for site, (ok, detail) in results.items():
        if not ok and site not in open_issues:
            actions.append(('open', site, detail))
        elif ok and site in open_issues:
            actions.append(('close', site, open_issues[site], 'recovered'))
    for site, number in open_issues.items():
        if site not in results:
            actions.append(('close', site, number, 'no longer monitored'))
    return actions


def github(method, path, body=None):
    request = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
                                     data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={'Authorization': f"Bearer {os.environ['GITHUB_TOKEN']}",
                                              'Accept': 'application/vnd.github+json', 'User-Agent': 'banitaba-uptime'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b'null')


def main():
    sites = json.loads((pathlib.Path(__file__).parent / 'sites.json').read_text())
    if os.environ.get('TEST_DOWN') == '1':
        sites.append(TEST_SITE)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = dict(zip([s['name'] for s in sites], pool.map(lambda s: probe(s['url'], s['expect']), sites)))
    urls = {s['name']: s['url'] for s in sites}
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    for site, (ok, detail) in outcomes.items():
        print(f"{'UP  ' if ok else 'DOWN'} {site} {detail}")
    open_issues = issues_by_site(github('GET', '/issues?state=open&labels=down&per_page=100'))
    for action in plan(outcomes, open_issues):
        if action[0] == 'open':
            _, site, detail = action
            issue = github('POST', '/issues', {
                'title': f'{site} is down', 'labels': ['down', f'site:{site}'],
                'body': f'{OWNER_MENTION} **{site}** did not answer correctly from outside the server.\n\n'
                        f'- URL: {urls[site]}\n- Result after {TRIES} tries {WAIT} s apart: {detail}\n- Time: {now}\n\n'
                        'If the whole server is down, the BaniSupport watchdog cannot report it; check the server '
                        '(DevOps docs: lightsail-outage-check). This issue closes by itself when the site answers again.'})
            print(f"opened #{issue['number']} for {site}")
        else:
            _, site, number, reason = action
            github('POST', f'/issues/{number}/comments', {'body': f'{"Recovered" if reason == "recovered" else "No longer monitored"} at {now}.'})
            github('PATCH', f'/issues/{number}', {'state': 'closed', 'state_reason': 'completed'})
            print(f'closed #{number} for {site} ({reason})')


if __name__ == '__main__':
    main()
