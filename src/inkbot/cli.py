from invoke import Collection, Program
from . import tasks


def main(*args):
    program = Program(namespace=Collection.from_module(tasks), version='0.0.1')
    program.run(*args)
