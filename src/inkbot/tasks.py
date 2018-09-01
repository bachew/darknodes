# -*- coding: utf-8 -*-
from contextlib import contextmanager
from glob import glob
from invoke import Failure, task
from os import path as osp
from subprocess import list2cmdline
from textwrap import dedent
import json
import os
import re
import requests
import sys
import tempfile


home_dir = osp.expanduser('~')
real_darknode_dir = osp.join(home_dir, '.darknode')
test_darknode_dir = real_darknode_dir + '-test'
test = False  # set to True to darknode dir in ~/.darknode-test
darknode_dir = test_darknode_dir if test else real_darknode_dir
darknode_dir_var = '{{ darknode_dir }}'
darknode_bin_dir = osp.join(darknode_dir, 'bin')
inkbot_dir = osp.join(darknode_dir, 'inkbot')
_darknode_in_path = None


@task
def install_darknode_cli(ctx, update=False):
    '''
    Install darknode-cli if not already installed
    '''
    if osp.exists(osp.join(real_darknode_dir, 'bin')):
        if update:
            ctx.run('curl https://darknode.republicprotocol.com/update.sh -sSf | sh')
    else:
        ctx.run('curl https://darknode.republicprotocol.com/install.sh -sSf | sh')

    if test:
        rsync(ctx, real_darknode_dir, test_darknode_dir)


def darknode_bin(name='darknode'):
    if darknode_in_path():
        return name

    return osp.join(darknode_bin_dir, name)


def darknode_in_path():
    global _darknode_in_path

    if _darknode_in_path is None:
        paths = os.environ['PATH'].split(os.pathsep)
        bin_dir = osp.join(darknode_dir, 'bin')
        _darknode_in_path = bin_dir in paths

    return _darknode_in_path


@task
def set_aws_keys(ctx):
    '''
    Set AWS access key and secret key for adding new darknodes
    '''
    dct = {
        'accessKey': get_input('AWS access key: '),
        'secretKey': get_input('AWS secret key: ')
    }
    write_json_file(osp.join(inkbot_dir, 'aws.json'), dct)


@task
def aws_access_key(ctx):
    '''
    Print AWS access key set by 'inkbot set-aws-keys'
    '''
    print(read_aws_keys()[0])


@task
def aws_secret_key(ctx):
    '''
    Print AWS secret key set by 'inkbot set-aws-keys'
    '''
    print(read_aws_keys()[1])


def read_aws_keys():
    try:
        config = read_json_file(osp.join(inkbot_dir, 'aws.json'))
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
    Set Digital Ocean token for adding new darknodes
    '''
    dct = {
        'token': get_input('Digital Ocean token: ')
    }
    write_json_file(osp.join(inkbot_dir, 'do.json'), dct)


@task
def do_token(ctx):
    '''
    Print Digital Ocean token set by 'inkbot set-do-token'
    '''
    print(get_do_token())


def get_do_token():
    def error():
        error_exit("DO token not found, please run 'inkbot set-do-token' to set it")

    try:
        config = read_json_file(osp.join(inkbot_dir, 'do.json'))
    except FileNotFoundError:
        error()

    token = config.get('token')

    if not token:
        error()

    return token


def make_inkbot_dir(ctx):
    ctx.run(list2cmdline(['mkdir', '-p', inkbot_dir]), echo=False)


def get_input(prompt):
    line = None

    while not line:
        line = input(prompt)

        if not line:
            print('Please specify a value!')

    return line


@task
def add_aws_node(ctx, name, print_command=False, network=None, region=None, instance=None):
    '''
    Add a AWS darknode using credentials set by 'inkbot set-aws-keys'
    '''
    cmd = [
        darknode_bin(), 'up',
        '--name', name,
    ]

    if network:
        cmd += ['--network', network]

    cmd += [
        '--aws',
        '--aws-access-key', '$(inkbot aws-access-key)',
        '--aws-secret-key', '$(inkbot aws-secret-key)',
    ]

    if region:
        cmd += ['--aws-region', region]

    if instance:
        cmd += ['--aws-instance', instance]

    cmdline = list2cmdline(cmd)

    if print_command:
        print(cmdline)
    else:
        install_darknode_cli(ctx)
        ctx.run(cmdline)


@task
def add_do_node(ctx, name, print_command=False, network=None, region=None, droplet=None):
    '''
    Add a Digital Ocean darknode using credentials set by 'inkbot set-do-token'
    '''
    cmd = [
        darknode_bin(), 'up',
        '--name', name,
    ]

    if network:
        cmd += ['--network', network]

    cmd += [
        '--do',
        '--do-token', '$(inkbot do-token)',
    ]

    if region:
        cmd += ['--do-region', region]

    if droplet:
        cmd += ['--do-droplet', droplet]

    cmdline = list2cmdline(cmd)

    if print_command:
        print(cmdline)
    else:
        install_darknode_cli(ctx)
        ctx.run(cmdline)


@task
def do_regions(ctx, sizes=False):
    '''
    Print Digital Ocean available regions
    '''
    def format(r):
        buf = [
            r['slug'], ': ', r['name']
        ]

        if sizes:
            buf.extend(['\n  sizes: ', ', '.join(r['sizes']), '\n'])

        return ''.join(buf)

    headers = {
        'Authorization': 'Bearer {}'.format(get_do_token())
    }
    resp = requests.get('https://api.digitalocean.com/v2/regions', headers=headers)
    regions = resp.json().get('regions', [])

    for region in regions:
        if region.get('available'):
            print(format(region))


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
        rsync(ctx, darknode_dir, osp.join(backup_dir), excludes)
        search_replace_tf(backup_dir, re.escape(darknode_dir), darknode_dir_var)
        archive_encrypt(ctx, backup_dir, backup_file)


def search_replace_tf(dirname, pattern, repl):
    for filename in glob(osp.join(dirname, '*.tf')):
        search_replace(filename, pattern, repl)

    for filename in glob(osp.join(dirname, 'darknodes/*/*.tf')):
        search_replace(filename, pattern, repl)


def search_replace(filename, pattern, repl):
    print('Search and replace {!r}: {} -> {}'.format(filename, pattern, repl))

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
        search_replace_tf(backup_dir, re.escape(darknode_dir_var), darknode_dir)
        rsync(ctx, backup_dir, darknode_dir)
        extra_nodes = compare_darknodes(backup_dir, darknode_dir)

    try:
        terraform_init(ctx)
    except Failure:
        print("'terraform init' failed, you can try again with 'inkbot terraform-init'")
        raise

    if extra_nodes:
        print(("Extra darknodes {!r} are left untouched,"
               " to remove them you have to do it manually".format(extra_nodes)))


def compare_darknodes(backup_dir, darknode_dir):
    def nodes(dirname):
        dirs = glob(osp.join(dirname, 'darknodes/*'))
        return [osp.basename(d) for d in dirs]

    backup_nodes = nodes(backup_dir)
    current_nodes = nodes(darknode_dir)
    extra_nodes = set(current_nodes).difference(backup_nodes)
    return sorted(list(extra_nodes))


@task
def terraform_init(ctx, force=False):
    '''
    Run 'terraform init' in darknode directories
    '''
    def init(dirname):
        if glob(osp.join(dirname, '*.tf')):
            if force or not osp.exists(osp.join(dirname, '.terraform')):
                with ctx.cd(dirname):
                    ctx.run(list2cmdline([darknode_bin('terraform'), 'init']))

    init(darknode_dir)

    darknodes_dir = osp.join(darknode_dir, 'darknodes')

    if osp.exists(darknodes_dir):
        for name in os.listdir(darknodes_dir):
            init(osp.join(darknodes_dir, name))


@contextmanager
def new_temp_dir(ctx):
    memory_dir = '/dev/shm'
    temp_dir = memory_dir if osp.isdir(memory_dir) else None
    backup_dir = tempfile.mkdtemp(prefix='inkbot-', suffix='.bak', dir=temp_dir)

    try:
        yield backup_dir
    finally:
        ctx.run(list2cmdline(['rm', '-rf', backup_dir]))


def rsync(ctx, src, dest, excludes=None):
    def end_slash(dirname):
        return dirname if dirname.endswith('/') else dirname + '/'

    src = osp.expanduser(src)
    dest = osp.expanduser(dest)

    if not osp.exists(src):
        print('{!r} does not exist, not rsyncing it'.format(src))
        return

    cmd = ['rsync', '-avh']

    if excludes:
        for exclude in excludes:
            cmd.append('--exclude={}'.format(exclude))

    cmd += [end_slash(src), end_slash(dest)]
    ctx.run(list2cmdline(cmd))


@task
def archive_encrypt(ctx, src_dir, backup_file):
    '''
    Archive <src-dir> into tar file and encrypt it to <backup-file>
    '''
    with new_temp_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(backup_file) + '.tgz'))

        with ctx.cd(src_dir):
            ctx.run(list2cmdline(['tar', '-czf', archive_file, '*']))

        encrypt(ctx, archive_file, backup_file)


@task
def decrypt_extract(ctx, backup_file, dest_dir):
    '''
    Decrypt <backup-file> to a tar file and extract it to <dest-dir>
    '''
    with decrypted(ctx, backup_file) as archive_file:
        if not osp.exists(dest_dir):
            ctx.run(list2cmdline(['mkdir', '-p', dest_dir]))

        ctx.run(list2cmdline(['tar', '-C', dest_dir, '-xzf', archive_file]))


@task
def list_backup(ctx, backup_file):
    '''
    List files inside <backup-file>
    '''
    with decrypted(ctx, backup_file) as archive_file:
        ctx.run(list2cmdline(['tar', '-tvf', archive_file]))


@contextmanager
def decrypted(ctx, backup_file):
    with new_temp_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(backup_file) + '.tgz'))
        decrypt(ctx, backup_file, archive_file)
        yield archive_file


@task
def encrypt(ctx, plain_file, cipher_file):
    '''
    Encrypt <plain-file> to <cipher-file>
    '''
    ctx.run(list2cmdline([
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
    ctx.run(list2cmdline(['gpg', '-o', plain_file, cipher_file]))
