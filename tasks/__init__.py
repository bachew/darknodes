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
def backup(ctx, backup_file=None):  # TODO: default backup_file
    memory_dir = '/dev/shm'
    temp_dir = memory_dir if osp.isdir(memory_dir) else None
    backup_dir = tempfile.mkdtemp(prefix='ink-', dir=temp_dir)  # TODO: ink?
    darknode_excludes = [
        '.terraform',
        '/bin/',
        '/darknode-setup',
        '/gen-config',
    ]
    try:
        rsync(ctx, '~/.darknode/',
              osp.join(backup_dir, 'darknode/'),
              excludes=darknode_excludes)
        rsync(ctx, '~/.aws/', osp.join(backup_dir, 'aws/'))
        ctx.run(list2cmdline(['find', backup_dir]))  # TESTING
    finally:
        ctx.run(list2cmdline(['rm', '-rf', backup_dir]))


@task
def restore(ctx, backup_file=None):
    pass


def rsync(ctx, src, dest, excludes=[]):
    src = osp.expanduser(src)
    dest = osp.expanduser(dest)

    if not osp.exists(src):
        print('{!r} does not exist, not rsyncing it'.format(src))
        return

    cmd = ['rsync', '-av']

    for exclude in excludes:
        cmd.append('--exclude={}'.format(exclude))

    cmd += [src, dest]
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
