# -*- coding: utf-8 -*-
__all__ = ('index', 'create_root', 'includeme')
from h.api.resources import create_root
from h.api.views import index


def includeme(config):
    config.set_root_factory(create_root)
    config.add_route('api', '/')

    config.include('h.features')
    config.include('h.api.db')
    config.include('h.api.queue')
    config.include('h.api.views')
