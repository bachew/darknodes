from invoke import Collection, Program
from . import tasks
import pkg_resources


class Inkbot(Program):
    def __init__(self):
        namespace = Collection.from_module(tasks)
        version = pkg_resources.require("inkbot")[0].version
        super(Inkbot, self).__init__(namespace=namespace, version=version)

    def create_config(self):
        super(Inkbot, self).create_config()
        self.config['run'] = {
            'echo': True,
            'pty': True,
        }


def main():
    Inkbot().run()
