from . import models
from . import wizard


def post_init_hook(env):
    env["vet.exam.node"]._load_standard_structure()
