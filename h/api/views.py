# -*- coding: utf-8 -*-

"""HTTP/REST API for interacting with the annotation store."""

import json
import logging

import gevent
from pyramid.response import Response
from pyramid.view import view_config

from h.api.auth import get_user
from h.api.events import AnnotationEvent
from h.api.models import Annotation
from h.api.resources import Root
from h.api.resources import Annotations
from h.api import search as search_lib
from h.api import logic


log = logging.getLogger(__name__)


def api_config(**kwargs):
    """Extend Pyramid's @view_config decorator with modified defaults."""
    config = {
        'accept': 'application/json',
        'renderer': 'json',
    }
    config.update(kwargs)
    return view_config(**config)


@api_config(context=Root)
@api_config(route_name='api')
def index(context, request):
    """Return the API descriptor document.

    Clients may use this to discover endpoints for the API.
    """
    return {
        'message': "Annotator Store API",
        'links': {
            'annotation': {
                'create': {
                    'method': 'POST',
                    'url': request.resource_url(context, 'annotations'),
                    'desc': "Create a new annotation"
                },
                'read': {
                    'method': 'GET',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Get an existing annotation"
                },
                'update': {
                    'method': 'PUT',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Update an existing annotation"
                },
                'delete': {
                    'method': 'DELETE',
                    'url': request.resource_url(context, 'annotations', ':id'),
                    'desc': "Delete an annotation"
                }
            },
            'search': {
                'method': 'GET',
                'url': request.resource_url(context, 'search'),
                'desc': 'Basic search API'
            },
        }
    }


@api_config(context=Root, name='search')
def search(request):
    """Search the database for annotations matching with the given query."""
    search_normalized_uris = request.feature('search_normalized')

    # The search results are filtered for the authenticated user
    user = get_user(request)
    results = search_lib.search(request_params=request.params,
                                user=user,
                                search_normalized_uris=search_normalized_uris)

    return {
        'total': results['total'],
        'rows': [search_lib.render(a) for a in results['rows']],
    }


@api_config(context=Root, name='access_token')
def access_token(request):
    """The OAuth 2 access token view."""
    return request.create_token_response()


# N.B. Like the rest of the API, this view is exposed behind WSGI middleware
# that enables appropriate CORS headers and response to preflight request.
#
# However, this view requires credentials (a cookie) so is in fact not
# currently accessible off-origin. Given that this method of authenticating to
# the API is not intended to remain, this seems like a limitation we do not
# need to lift any time soon.
@api_config(context=Root, name='token', renderer='string')
def annotator_token(request):
    """The Annotator Auth token view."""
    request.grant_type = 'client_credentials'
    response = access_token(request)
    return response.json_body.get('access_token', response)


@api_config(context=Annotations, request_method='GET')
def annotations_index(request):
    """Do a search for all annotations on anything and return results.

    This will use the default limit, 20 at time of writing, and results
    are ordered most recent first.
    """
    search_normalized_uris = request.feature('search_normalized')

    user = get_user(request)
    results = search_lib.index(user=user,
                               search_normalized_uris=search_normalized_uris)

    return {
        'total': results['total'],
        'rows': [search_lib.render(a) for a in results['rows']],
    }


@api_config(context=Annotations, request_method='POST', permission='create')
def create(request):
    """Read the POSTed JSON-encoded annotation and persist it."""
    # Read the annotation from the request payload
    try:
        fields = request.json_body
    except ValueError:
        return _api_error(request,
                          'No JSON payload sent. Annotation not created.',
                          status_code=400)  # Client Error: Bad Request

    user = get_user(request)

    # Create the annotation
    annotation = logic.create_annotation(fields, user)

    # Notify any subscribers
    _publish_annotation_event(request, annotation, 'create')

    # Return it so the client gets to know its ID and such
    return search_lib.render(annotation)


@api_config(containment=Root, context=Annotation,
            request_method='GET', permission='read')
def read(context, request):
    """Return the annotation (simply how it was stored in the database)."""
    annotation = context

    # Notify any subscribers
    _publish_annotation_event(request, annotation, 'read')

    return search_lib.render(annotation)


@api_config(containment=Root, context=Annotation,
            request_method='PUT', permission='update')
def update(context, request):
    """Update the fields we received and store the updated version."""
    annotation = context

    # Read the new fields for the annotation
    try:
        fields = request.json_body
    except ValueError:
        return _api_error(request,
                          'No JSON payload sent. Annotation not created.',
                          status_code=400)  # Client Error: Bad Request

    # Check user's permissions
    has_admin_permission = request.has_permission('admin', annotation)

    # Update and store the annotation
    try:
        logic.update_annotation(annotation, fields, has_admin_permission)
    except RuntimeError as err:
        return _api_error(
            request,
            err.args[0],
            status_code=err.args[1])

    # Notify any subscribers
    _publish_annotation_event(request, annotation, 'update')

    # Return the updated version that was just stored.
    return search_lib.render(annotation)


@api_config(containment=Root, context=Annotation,
            request_method='DELETE', permission='delete')
def delete(context, request):
    """Delete the annotation permanently."""
    annotation = context
    id_ = annotation['id']
    # Delete the annotation from the database.
    annotation.delete()

    # Notify any subscribers
    _publish_annotation_event(request, annotation, 'delete')

    # Return a confirmation
    return {
        'id': id_,
        'deleted': True,
    }


@view_config(context=Root, name='events')
def event_source(request):
    search_normalized_uris = request.feature('search_normalized')
    user = get_user(request)

    percolator = search_lib.percolator(
        request.params,
        user=user,
        search_normalized_uris=search_normalized_uris
    )

    if 'X-Client-Id' in request.headers:
        percolator['id'] = request.headers['X-Client-Id']

    percolator['_ttl'] = 60000
    percolator.save()

    app_iter = _consume_annotation_events(request, percolator)
    response = Response(app_iter=app_iter, content_type='text/event-stream')
    response.cache_control = 'no-cache'

    return response


def _consume_annotation_events(request, percolator):
    queue = gevent.queue.Queue()

    topic_id = 'percolator-{}#ephemeral'.format(percolator['id'])
    reader = request.get_queue_reader(topic_id, 'clients#ephemeral')

    def on_message(reader, message=None):
        if message is not None:
            event = json.loads(message.body)
            queue.put(event)

    reader.on_message.connect(on_message)
    reader.start(block=False)

    def refresh():
        while True:
            gevent.sleep(45)
            percolator.save()

    refreshlet = gevent.spawn(refresh)

    try:
        while True:
            try:
                event = queue.get(block=True, timeout=30)
                action = event['action']
                data = json.dumps(event['annotation'])
                yield 'event:{}\ndata:{}\n\n'.format(action, data)
            except gevent.queue.Empty:
                # heartbeat
                yield ':\n'
    except GeneratorExit:
        pass
    finally:
        reader.close()
        reader.join()
        refreshlet.kill()
        refreshlet.join()
        percolator.delete()


def _publish_annotation_event(request, annotation, action):
    """Publish an event to the annotations queue for this annotation action"""
    event = AnnotationEvent(request, annotation, action)
    request.registry.notify(event)


def _api_error(request, reason, status_code):
    request.response.status_code = status_code
    response_info = {
        'status': 'failure',
        'reason': reason,
    }
    return response_info


def includeme(config):
    config.scan(__name__)
