# -*- coding: utf-8 -*-
from contextlib import contextmanager
from glob import glob
from invoke import task
from os import path as osp
from subprocess import list2cmdline as cmdline
import json
import os
import re
import sys
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
    # TODO: only the bin name if '{{ DARKNODE_DIR }}/bin' already in $PATH
    return osp.join(DARKNODE_DIR, 'bin', name)


@task
def set_aws_keys(ctx):
    '''
    Set AWS access key and secret key that will be used by add command to add darknode
    '''
    dct = {
        'accessKey': get_input('AWS access key: '),
        'secretKey': get_input('AWS secret key: ')
    }
    write_json_file(osp.join(INKBOT_DIR, 'aws.json'), dct)


@task
def aws_access_key(ctx):
    '''
    Print AWS access key
    '''
    print(read_aws_keys()[0])


@task
def aws_secret_key(ctx):
    '''
    Print AWS secret key
    '''
    print(read_aws_keys()[1])


def read_aws_keys():
    try:
        config = read_json_file(osp.join(INKBOT_DIR, 'aws.json'))
    except FileNotFoundError:
        error_exit("AWS keys not found, please run 'inkbot set-aws-keys' to set them")

    access_key = config.get('accessKey')

    if not access_key:
        error_exit("AWS access key not found, please run 'inkbot set-aws-keys' to set it")

    secret_key = config.get('secretKey')

    if not secret_key:
        error_exit("AWS secret key not found, please run 'inkbot set-aws-keys' to set it")

    return access_key, secret_key


def write_json_file(filename, obj):
    print('Writing to {!r}'.format(filename))
    text = json.dumps(obj, indent=2, sort_keys=True) + '\n'

    try:
        os.makedirs(osp.dirname(filename))
    except FileExistsError:
        pass

    with open(filename, 'w') as fobj:
        fobj.write(text)


def read_json_file(filename):
    with open(filename) as fobj:
        text = fobj.read().strip()

    try:
        config = json.loads(text)
    except ValueError:
        error_exit('Invalid json config {!r}, root must be an object'.format(filename))

    return config


def error_exit(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


@task
def set_do_token(ctx):
    '''
    Set Digital Ocean token that will be used by add command to add darknode
    '''
    dct = {
        'token': get_input('Digital Ocean token: ')
    }
    write_json_file(osp.join(INKBOT_DIR, 'do.json'), dct)


@task
def do_token(ctx):
    '''
    Print Digital Ocean token
    '''
    def error():
        error_exit("DO token not found, please run 'inkbot set-do-token' to set it")

    try:
        config = read_json_file(osp.join(INKBOT_DIR, 'do.json'))
    except FileNotFoundError:
        error()

    token = config.get('token')

    if not token:
        error()

    print(token)


def make_inkbot_dir(ctx):
    ctx.run(cmdline(['mkdir', '-p', INKBOT_DIR]), echo=False)


def get_input(prompt):
    line = None

    while not line:
        line = input(prompt)

        if not line:
            print('Please specify a value!')

    return line


# TODO: is it better to split into add_aws_node() and add_do_node()?
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
            '--aws-access-key', '$(inkbot aws-access-key)',
            '--aws-secret-key', '$(inkbot aws-secret-key)',
        ]

        if spec:
            cmd += ['--aws-instance', spec]
    elif provider == 'do':
        cmd += [
            '--do',
            '--do-region', region,
            '--do-token', '$(inkbot do-token)',
        ]

        if spec:
            cmd += ['--do-droplet', spec]
    else:
        raise ValueError("Provider must be either 'aws' or 'do'")

    install_darknode_cli(ctx)
    ctx.run(cmdline(cmd))


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
