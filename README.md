# Inkbot

**This repository is no longer maintained**

Inkbot is a wrapper around [darknode-cli](https://github.com/republicprotocol/darknode-cli) to make it easier to backup and restore darknodes configuration and credentials.


## Setup

To install Inkbot:

```console
$ pip install --user inkbot
```

Inkbot automatically installs darknode-cli when needed, but you can install it explicitly:

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

It writes the keys to `~/.darknode/inkbot/aws.json` for easy backup. You can print out the keys:

```console
$ inkbot aws-access-key
$ inkbot aws-secret-key
```


## Digital Ocean

To backup Digital Ocean API token you need to run the following command before `inkbot backup <backup-file>`:

```console
$ inkbot set-do-token
Digital Ocean token: ******
```

It writes the token to `~/.darknode/inkbot.do.json` for easy backup. You can print out the token:

```console
$ inkbot do-token
```


## Adding a new darknode

You can add a new darknode using the set AWS and DO credentials with `inkbot add-aws-node` or `inkbot add-do-node`:

```console
$ inkbot add-aws-node NAME
$ inkbot add-do-node NAME
```

They basically just run `darknode up <options>` in the end, to just see the darknode command, use `--print-command` option:

```console
$ inkbot add-aws-node --print-command NAME
darknode up --name NAME --aws --aws-access-key "$(inkbot aws-access-key)" --aws-secret-key "$(inkbot aws-secret-key)"
$ inkbot add-do-node --print-command NAME
darknode up --name NAME --do --do-token "$(inkbot do-token)"
```

Nothing extraordinary, just a convenient way to pass credentials without having it in command history.


## Development

To develop Inkbot locally, clone the repo and initialize it:

```console
$ git clone git@github.com:bachew/inkbot.git
$ cd inkbot
$ python3 init.py
```

You can then activate the Python virtualenv and run inkbot command:

```console
$ pipenv shell
$ whereis inkbot
$ inkbot --version
```


### Testing

For testing set `test = True` in `src/inkbot/tasks.py`:

```python
...
real_darknode_dir = osp.join(home_dir, '.darknode')
test_darknode_dir = real_darknode_dir + '-test'
test = True  # set to True to darknode dir in ~/.darknode-test
darknode_dir = test_darknode_dir if test else real_darknode_dir
...
```

Then run `inkbot install-darknode-cli` to rsync `~/.darknode` to `~/.darknode-test`.

And copy `~/.darknode` there as well:

```console
$ cp -r ~/.darknode ~/inkbot-test
```

Inkbot will then just backup from and restore to `~/inkbot-test`.


### PyPI

To build and upload to PyPI:

```console
$ inv build upload
```
