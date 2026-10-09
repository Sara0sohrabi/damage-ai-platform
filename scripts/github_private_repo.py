"""Create the user-requested private source repository using existing Git credentials.
Never prints or persists credentials. No project files are uploaded by this script.
"""
import json
import os
import subprocess
import urllib.request
import urllib.error

r = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                   text=True, capture_output=True, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
if r.returncode:
    raise SystemExit('GitHub authentication unavailable; sign in to Git first.')
credentials = dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)
headers = {'Authorization': 'Bearer ' + credentials.get('password', ''),
           'Accept': 'application/vnd.github+json', 'User-Agent': 'Damage-AI-Setup'}

def request(path, data=None):
    req = urllib.request.Request('https://api.github.com' + path, headers=headers,
                                data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)

if __name__ == '__main__':
    user = request('/user')
    if user['login'].lower() != 'sara0sohrabi':
        raise SystemExit('Saved account does not match requested repository owner.')
    name = 'damage-ai-prediction-panel'
    try:
        repo = request('/repos/Sara0sohrabi/' + name)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        repo = request('/user/repos', {'name': name, 'private': True,
                       'description': 'Persian RTL Damage AI assessment panel and prediction service'})
    if not repo['private']:
        raise SystemExit('Destination is not private; refusing upload setup.')
    print(json.dumps({'url': repo['html_url'], 'private': repo['private']}))
