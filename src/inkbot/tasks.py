from contextlib import contextmanager
from invoke import task
from invoke.exceptions import UnexpectedExit
from os import path as osp
from subprocess import list2cmdline as cmdline
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
def backup(ctx, backup_file):
    darknode_excludes = [
        '.terraform',
        '/bin/',
        '/darknode-setup',
        '/gen-config',
    ]
    with new_secure_dir(ctx) as backup_dir:
        rsync(ctx, '~/.darknode/',
              osp.join(backup_dir, 'darknode/'),
              excludes=darknode_excludes)
        rsync(ctx, '~/.aws/credentials', osp.join(backup_dir, 'aws/'))
        archive_encrypt(ctx, backup_dir, backup_file)

    # Option to delete secret data


@task
def restore(ctx, backup_file):
    with new_secure_dir(ctx) as backup_dir:
        decrypt_extract(ctx, backup_file, backup_dir)
        # TESTING: ~ -> /dev/shm/home
        rsync(ctx, osp.join(backup_dir, 'darknode/'), '/dev/shm/home/.darknode/')
        rsync(ctx, osp.join(backup_dir, 'aws/'), '/dev/shm/home/.aws')


@contextmanager
def new_secure_dir(ctx):
    memory_dir = '/dev/shm'
    temp_dir = memory_dir if osp.isdir(memory_dir) else None
    backup_dir = tempfile.mkdtemp(prefix='ink-', dir=temp_dir)  # TODO: ink?

    try:
        yield backup_dir
    finally:
        ctx.run(cmdline(['rm', '-rf', backup_dir]))


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
    ctx.run(cmdline(cmd))


@task
def archive_encrypt(ctx, src_dir, dest_file):
    '''
    Archive <src-dir> into tar file and encrypt it to <dest-file>.
    '''
    with new_secure_dir(ctx) as temp_dir:
        archive_file = osp.abspath(osp.join(temp_dir, osp.basename(dest_file) + '.tar'))

        with ctx.cd(src_dir):
            ctx.run(cmdline(['tar', '-czf', archive_file, '*']))

        encrypt(ctx, archive_file, dest_file)


@task
def decrypt_extract(ctx, src_file, dest_dir):
    '''
    Decrypt <src-file> to a tar file and extract it to <dest-dir>.
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
    Encrypt <plain-file> to <cipher-file>.
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
    Decrypt <cipher-file> to <plain-file>.
    '''
    ctx.run(cmdline(['gpg', '-o', plain_file, cipher_file]))
