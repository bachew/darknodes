# -*- coding: utf-8 -*-
from contextlib import contextmanager
from glob import glob
from invoke import task
from os import path as osp
from subprocess import list2cmdline as cmdline
import json
import os
import re
import tempfile


HOME_DIR = osp.expanduser('~')
HOME_DIR_PLACEHOLDER = '{{ INKBOT_HOME }}'
DARKNODE_DIR = osp.join(HOME_DIR, '.darknode')
INKBOT_DIR = osp.join(DARKNODE_DIR, 'inkbot')


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
def set_aws_keys(ctx):
    '''
    Set AWS access key and secret key that will be used by add command to add darknode
    '''
    dct = {
        'access_key': get_input('AWS access key: '),
        'secret_key': get_input('AWS secret key: ')
    }
    make_inkbot_dir(ctx)

    with open(osp.join(INKBOT_DIR, 'aws.json'), 'w') as fobj:
        fobj.write(to_json(dct))


@task
def set_do_token(ctx):
    '''
    Set Digital Ocean API token that will be used by add command to add darknode
    '''
    dct = {
        'token': get_input('DO token: ')
    }
    make_inkbot_dir(ctx)

    with open(osp.join(INKBOT_DIR, 'do.json'), 'w') as fobj:
        fobj.write(to_json(dct))


def make_inkbot_dir(ctx):
    ctx.run(cmdline(['mkdir', '-p', INKBOT_DIR]), echo=False)


def to_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True)


def get_input(prompt):
    line = None

    while not line:
        line = input(prompt)

        if not line:
            print('Please specify a value!')

    return line


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

    with new_temp_dir(ctx) as temp_dir:
        if provider == 'aws':
            aws_access_key_file, aws_secret_key_file = get_aws_key_files(temp_dir)
            cmd += [
                '--aws',
                '--aws-region', region,
                '--aws-access-key', '$(cat {!r})'.format(aws_access_key_file),
                '--aws-secret-key', '$(cat {!r})'.format(aws_secret_key_file),
            ]

            if spec:
                cmd += ['--aws-instance', spec]
        elif provider == 'do':
            do_token_file = get_do_token_file(temp_dir)
            cmd += [
                '--do',
                '--do-region', region,
                '--do-token', '$(cat {!r})'.format(do_token_file),
            ]

            if spec:
                cmd += ['--do-droplet', spec]
        else:
            raise ValueError("Provider must be either 'aws' or 'do'")

        install_darknode_cli(ctx)
        ctx.run(cmdline(cmd))


def get_aws_key_files(temp_dir):
    # TODO
    return osp.join(temp_dir, 'aws-access-key'), osp.join(temp_dir, 'aws-secret-key')


def get_do_token_file(temp_dir):
    # TODO
    return osp.join(temp_dir, 'do-token')


@task
def backup(ctx, backup_file):
    '''
    Backup darknodes and credentials to <backup-file>
    '''
    os.stat(osp.dirname(osp.abspath(backup_file)))  # validate dir

    with new_temp_dir(ctx) as backup_dir:
        excludes = [
            '.terraform',
            '/bin/',
            '/darknode-setup',
            '/gen-config',
        ]
        rsync(ctx, DARKNODE_DIR + '/', osp.join(backup_dir, 'darknode/'), excludes)

        search_replace_tf(osp.join(backup_dir, 'darknode'),
                          re.escape(HOME_DIR), HOME_DIR_PLACEHOLDER)

        excludes = [
            '/cli',
            'config',
        ]
        rsync(ctx, '~/.aws/', osp.join(backup_dir, 'aws/'), excludes)

        archive_encrypt(ctx, backup_dir, backup_file)


def search_replace_tf(dirname, pattern, repl):
    for filename in glob(osp.join(dirname, '*.tf')):
        search_replace(filename, pattern, repl)

    for filename in glob(osp.join(dirname, 'darknodes/*/*.tf')):
        search_replace(filename, pattern, repl)


def search_replace(filename, pattern, repl):
    print('Search and replace {!r}: {}/{}'.format(filename, pattern, repl))

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

    with new_temp_dir(ctx) as backup_dir:
        decrypt_extract(ctx, backup_file, backup_dir)

        search_replace_tf(osp.join(backup_dir, 'darknode'),
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
def new_temp_dir(ctx):
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
    with new_temp_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(dest_file) + '.tar'))

        with ctx.cd(src_dir):
            ctx.run(cmdline(['tar', '-czf', archive_file, '*']))

        encrypt(ctx, archive_file, dest_file)


@task
def decrypt_extract(ctx, src_file, dest_dir):
    '''
    Decrypt <src-file> to a tar file and extract it to <dest-dir>
    '''
    with new_temp_dir(ctx) as temp_dir:
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
