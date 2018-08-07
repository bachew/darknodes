from invoke import task
from subprocess import list2cmdline as cmdline


default_repo_url = 'https://pypi.org/legacy/'


@task
def init(ctx):
    pass


@task
def build(ctx):
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
