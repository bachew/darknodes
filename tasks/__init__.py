from invoke import task
from invoke.exceptions import UnexpectedExit
from os import path as osp
from subprocess import list2cmdline
import os
import tempfile


@task
def init(ctx):
    install_darknode_cli(ctx)


@task
def install_darknode_cli(ctx):
    try:
        ctx.run('darknode --version')
    except UnexpectedExit:
        ctx.run('curl https://darknode.republicprotocol.com/install.sh -sSf | sh')
        add_dncli_path()
    else:
        ctx.run('curl https://darknode.republicprotocol.com/update.sh -sSf | sh')


def add_dncli_path():
    paths = os.environ['PATH'].split(os.pathsep)
    cli_path = osp.expanduser('~/.darknode/bin')

    if cli_path not in paths:
        paths.append(cli_path)
        os.environ['PATH'] = os.pathsep.join(paths)


@task
def backup(ctx, file):
    temp_dir = tempfile.mkdtemp(prefix='.darknode-', dir='/dev/shm')
    try:
        rsync(ctx, '~/.darknode', temp_dir)
    finally:
        ctx.run(list2cmdline(['rm', '-rf', temp_dir]))


@task
def restore(ctx, file):
    pass


def rsync(ctx, src, dest):
    def end_slash(path):
        return path if path.endswith('/') else path + '/'

    cmd = ['rsync', '-av']

    excludes = [
        '.terraform',
        '/bin/',
        '/darknode-setup',
        '/gen-config',
    ]

    for exclude in excludes:
        cmd.append('--exclude={}'.format(exclude))

    cmd.extend([end_slash(src), end_slash(dest)])
    ctx.run(list2cmdline(cmd))


@task
def up(ctx):
    ctx.run(list2cmdline([
        'darknode', 'up',
        '--network', 'testnet',
        '--name', 'darknode2',
        '--tags', 'darknode2',
        '--aws',
        '--aws-region', 'eu-west-2',
    ]))


@task
def down(ctx):
    ctx.run(list2cmdline([
        'darknode', 'down',
        '--name', 'darknode2',
        '--tags', 'darknode2',
        '--aws',
        '--aws-region', 'eu-west-2',
    ]))
