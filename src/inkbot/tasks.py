# -*- coding: utf-8 -*-
from contextlib import contextmanager
from glob import glob
from invoke import task
from os import path as osp
from subprocess import list2cmdline as cmdline
import os
import re
import tempfile


HOME_DIR = osp.expanduser('~')
HOME_DIR_PLACEHOLDER = '{{ INKBOT_HOME }}'
DARKNODE_DIR = '~/.darknode'


@task
def install_darknode_cli(ctx, update=False):
    '''
    Install darknode-cli if not already installed
    '''
    if not osp.exists(darknode_bin()):
        ctx.run('curl https://darknode.republicprotocol.com/install.sh -sSf | sh')
        return

    if update:
        ctx.run('curl https://darknode.republicprotocol.com/update.sh -sSf | sh')


def darknode_bin(name='darknode'):
    return osp.join(DARKNODE_DIR, 'bin', name)


# TODO: should have a task for user to set AWS and DO tokens so we can store
# them in ~/.inkbot/tokens because we should not expect them to be in
# ~/.aws/credentials and ~/.config/doctl/config.yaml


@task
def add(ctx, network, provider, region, tag=None, spec=None):
    '''
    Add a new darknode with name based on parameters
    '''
    if network.endswith('net'):
        short_network = network[:-3]
    else:
        short_network = network

    params = [short_network, provider, region]

    if tag:
        params.append(tag)

    cmd = [
        darknode_bin(), 'up',
        '--name', '-'.join(params),
        '--network', network
    ]

    if provider == 'aws':
        cmd += [
            '--aws',
            '--aws-region', region,
            # TODO: --aws-access-key and --aws-secret-key
        ]

        if spec:
            cmd += ['--aws-instance', spec]
    elif provider == 'do':
        cmd += [
            '--do',
            '--do-region', region,
            # TODO: --do-token
        ]

        if spec:
            cmd += ['--do-droplet', spec]
    else:
        raise ValueError("Provider must be either 'aws' or 'do'")

    print(cmdline(cmd))


@task
def backup(ctx, backup_file):
    '''
    Backup darknodes and credentials to <backup-file>
    '''
    os.stat(osp.dirname(osp.abspath(backup_file)))  # validate dir

    with new_secure_dir(ctx) as backup_dir:
        excludes = [
            '.terraform',
            '/bin/',
            '/darknode-setup',
            '/gen-config',
        ]
        rsync(ctx, DARKNODE_DIR + '/', osp.join(backup_dir, 'darknode/'), excludes)

        search_replace(osp.join(backup_dir, 'darknode/main.tf'),
                       re.escape(HOME_DIR), HOME_DIR_PLACEHOLDER)

        excludes = [
            '/cli',
            'config',
        ]
        rsync(ctx, '~/.aws/', osp.join(backup_dir, 'aws/'), excludes)

        archive_encrypt(ctx, backup_dir, backup_file)

    # Option to delete secret data


def search_replace(filename, pattern, repl):
    if not osp.exists(filename):
        return

    print('Search and replace {!r}'.format(filename))

    with open(filename) as fobj:
        replaced = re.sub(pattern, repl, fobj.read())

    with open(filename, 'w') as fobj:
        fobj.write(replaced)


@task
def restore(ctx, backup_file):
    '''
    Restore darknodes and credentials from <backup-file>
    '''
    install_darknode_cli(ctx)

    with new_secure_dir(ctx) as backup_dir:
        decrypt_extract(ctx, backup_file, backup_dir)

        search_replace(osp.join(backup_dir, 'darknode/main.tf'),
                       re.escape(HOME_DIR_PLACEHOLDER), HOME_DIR)

        rsync(ctx, osp.join(backup_dir, 'darknode/'), DARKNODE_DIR + '/')
        rsync(ctx, osp.join(backup_dir, 'aws/'), '~/.aws')

    terraform_init(ctx, DARKNODE_DIR)

    darknodes_dir = osp.join(DARKNODE_DIR, 'darknodes')

    if osp.exists(darknodes_dir):
        for name in os.listdir(darknodes_dir):
            terraform_init(ctx, osp.join(darknodes_dir, name))


def terraform_init(ctx, dirname):
    if not osp.exists(osp.join(dirname, '.terraform')) and glob(osp.join(dirname, '*.tf')):
        with ctx.cd(dirname):
            ctx.run(cmdline([darknode_bin('terraform'), 'init']))


@contextmanager
def new_secure_dir(ctx):
    memory_dir = '/dev/shm'
    temp_dir = memory_dir if osp.isdir(memory_dir) else None
    backup_dir = tempfile.mkdtemp(prefix='inkbot-', suffix='.bak', dir=temp_dir)

    try:
        yield backup_dir
    finally:
        ctx.run(cmdline(['rm', '-rf', backup_dir]))


def rsync(ctx, src, dest, excludes=None):
    src = osp.expanduser(src)
    dest = osp.expanduser(dest)

    if not osp.exists(src):
        print('{!r} does not exist, not rsyncing it'.format(src))
        return

    cmd = ['rsync', '-ac']

    if excludes:
        for exclude in excludes:
            cmd.append('--exclude={}'.format(exclude))

    cmd += [src, dest]
    ctx.run(cmdline(cmd))


@task
def archive_encrypt(ctx, src_dir, dest_file):
    '''
    Archive <src-dir> into tar file and encrypt it to <dest-file>
    '''
    with new_secure_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(dest_file) + '.tar'))

        with ctx.cd(src_dir):
            ctx.run(cmdline(['tar', '-czf', archive_file, '*']))

        encrypt(ctx, archive_file, dest_file)


@task
def decrypt_extract(ctx, src_file, dest_dir):
    '''
    Decrypt <src-file> to a tar file and extract it to <dest-dir>
    '''
    with new_secure_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(src_file) + '.tar'))
        decrypt(ctx, src_file, archive_file)

        if not osp.exists(dest_dir):
            ctx.run(cmdline(['mkdir', '-p', dest_dir]))

        ctx.run(cmdline(['tar', '-C', dest_dir, '-xzf', archive_file]))


@task
def encrypt(ctx, plain_file, cipher_file):
    '''
    Encrypt <plain-file> to <cipher-file>
    '''
    ctx.run(cmdline([
        'gpg', '--cipher-algo', 'AES256',
        '-c',
        '-o', cipher_file,
        plain_file
    ]))


@task
def decrypt(ctx, cipher_file, plain_file):
    '''
    Decrypt <cipher-file> to <plain-file>
    '''
    ctx.run(cmdline(['gpg', '-o', plain_file, cipher_file]))
