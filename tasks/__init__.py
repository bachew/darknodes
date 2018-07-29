from invoke import task
from invoke.exceptions import UnexpectedExit
from os import path as osp
from subprocess import list2cmdline
import os


@task
def init(ctx):
    try:
        ctx.run('darknode --version')
    except UnexpectedExit:
        install_dncli(ctx)
        add_dncli_path()
    else:
        update_dncli(ctx)


def add_dncli_path():
    paths = os.environ['PATH'].split(os.pathsep)
    cli_path = osp.expanduser('~/.darknode/bin')

    if cli_path not in paths:
        print('add!')
        paths.append(cli_path)
        os.environ['PATH'] = os.pathsep.join(paths)


@task
def install_dncli(ctx):
    ctx.run('curl https://darknode.republicprotocol.com/install.sh -sSf | sh')


@task
def update_dncli(ctx):
    ctx.run('curl https://darknode.republicprotocol.com/update.sh -sSf | sh')


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
