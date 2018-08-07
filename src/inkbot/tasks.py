from contextlib import contextmanager
from glob import glob
from invoke import task
from os import path as osp
from subprocess import list2cmdline as cmdline
import os
import tempfile


@task
def install_darknode_cli(ctx, upgrade=False):
    '''
    Install darknode-cli it's not installed
    '''
    if not osp.exists(darknode_bin()):
        ctx.run('curl https://darknode.republicprotocol.com/install.sh -sSf | sh')
        return

    if upgrade:
        ctx.run('curl https://darknode.republicprotocol.com/update.sh -sSf | sh')


def darknode_bin(name='darknode'):
    return osp.join(osp.expanduser('~/.darknode/bin'), name)


@task
def backup(ctx, backup_file):
    '''
    Backup darknodes and credentials to <backup-file>
    '''
    os.stat(osp.dirname(osp.abspath(backup_file)))  # validate dir
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
        rsync(ctx, '~/.aws/', osp.join(backup_dir, 'aws/'))
        archive_encrypt(ctx, backup_dir, backup_file)

    # Option to delete secret data


@task
def restore(ctx, backup_file):
    '''
    Restore darknodes and credentials from <backup-file>
    '''
    install_darknode_cli(ctx)

    with new_secure_dir(ctx) as backup_dir:
        decrypt_extract(ctx, backup_file, backup_dir)
        rsync(ctx, osp.join(backup_dir, 'darknode/'), '~/.darknode/')
        rsync(ctx, osp.join(backup_dir, 'aws/'), '~/.aws')

    terraform_init(ctx, osp.expanduser('~/.darknode'))

    darknodes_dir = osp.expanduser('~/.darknode/darknodes')

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


def rsync(ctx, src, dest, excludes=[]):
    src = osp.expanduser(src)
    dest = osp.expanduser(dest)

    if not osp.exists(src):
        print('{!r} does not exist, not rsyncing it'.format(src))
        return

    cmd = ['rsync', '-a']

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
