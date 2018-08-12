# Inkbot

Inkbot is a wrapper around [darknode-cli](https://github.com/republicprotocol/darknode-cli) to make it easier to backup and restore darknodes configuration and credentials.

!!! warning
    Inkbot is experimental, use at your own risk. Also darknode-cli is under active development, please check the status before using Inkbot, you might not need this anymore.


## Setup

To install Inkbot:

```console
$ pip install --user inkbot
```

Inkbot **automatically installs darknode-cli** on demand, but you can install it explicityly:

```console
$ inkbot install-darknode-cli
```

Or update it:

```console
$ inkbot install-darknode-cli --update
```


## Backup and restore

To backup darknodes, for example to `darknodes.tgz.gpg`:

```console
$ inkbot backup darknodes.tgz.gpg
Enter passphrase: ******
Repeat passphrase: ******
```

It archives `~/.darknode` without `.terraform` and binary files and encrypts it using GnuPG. You can inspect the backup file content:

```console
$ inkbot list-backup darknodes.tgz.gpg
Enter passphrase: ******
-rw-r--r-- bachew/bachew  1090 2018-08-12 11:39 config.json
drwxr-xr-x bachew/bachew     0 2018-08-12 11:39 darknodes/
drwxr-xr-x bachew/bachew     0 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/
-rw-r--r-- bachew/bachew 10236 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/terraform.tfstate
-rw-r--r-- bachew/bachew     0 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/tags.out
-rw------- bachew/bachew   381 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/ssh_keypair.pub
-rw------- bachew/bachew  1675 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/ssh_keypair
-rw-r--r-- bachew/bachew    69 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/multiAddress.out
-rw------- bachew/bachew  1237 2018-08-12 11:40 darknodes/aws-testnet-eu-west-1/main.tf
-rw------- bachew/bachew  3178 2018-08-12 11:39 darknodes/aws-testnet-eu-west-1/config.json
...
```

To restore the backup to `~/.darknode`:

```console
$ inkbot restore darknodes.tgz.gpg
```


## AWS

To backup AWS access and secret keys you need to run the following command before `inkbot backup <backup-file>`:

```console
$ inkbot set-aws-keys
AWS access key: ******
AWS secret key: ******
```

It writes the keys to `~/.darknode/inkbot/aws.json` for easy backup.


## Digital Ocean

To backup Digital Ocean API token you need to run the following command before `inkbot backup <backup-file>`:

```console
$ inkbot set-do-token
Digital Ocean token: ******
```

It writes the token to `~/.darknode/inkbot.do.json` for easy backup.


## Development

To develop Inkbot locally, clone the repo and initialize it:

```console
git clone git@github.com:bachew/inkbot.git
cd inkbot
python3 init.py
```


### Testing

For testing update set a test directory as home directory in `src/inkbot/tasks.py`:

```python
# HOME_DIR = osp.expanduser('~')
HOME_DIR = osp.expanduser('~/inkbot-test')
```

And copy `~/.darknode` there as well:

```console
$ cp -r ~/.darknode ~/inkbot-test
```

Inkbot will then just backup from and restore to `~/inkbot-test`.


### PyPI

To build and deploy to PyPI:

```console
$ inv build deploy
```
