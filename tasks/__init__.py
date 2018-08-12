from invoke import task
from subprocess import list2cmdline as cmdline


default_repo_url = 'https://upload.pypi.org/legacy/'


@task
def init(ctx):
    ctx.run('pip install -e .')


@task
def build(ctx):
    ctx.run('rm -rf dist')
    ctx.run('python setup.py build bdist_wheel')


@task
def deploy(ctx, repo_url=None, username=None, test_repo=False):
    cmd = ['twine', 'upload']

    if not repo_url:
        repo_url = default_repo_url

    if test_repo:
        repo_url = 'https://test.pypi.org/legacy/'

    if repo_url:
        cmd += ['--repository-url', repo_url]

    if username:
        cmd += ['-u', username]

    cmd.append('dist/*.whl')
    ctx.run(cmdline(cmd))


@task
def test(ctx):
    ctx.run('mkdir -p tmp')
    ctx.run('rm -rf tmp/test.bak')
    ctx.run('inkbot backup tmp/test.bak')
    ctx.run('rm -rf tmp/test')
    ctx.run('inkbot decrypt-extract tmp/test.bak tmp/test')
