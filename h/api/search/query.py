from h.api import uri
from h.api import nipsa


def build(request_params, userid=None, search_normalized_uris=False):
    """
    Return an Elasticsearch query dict for the given h search API params.

    Translates the HTTP request params accepted by the h search API into an
    Elasticsearch query dict.

    :param request_params: the HTTP request params that were posted to the
        h search API
    :type request_params: webob.multidict.NestedMultiDict

    :param userid: the ID of the authorized user (optional, default: None),
    :type userid: unicode or None

    :param search_normalized_uris: Whether or not to use the "uri" param to
        search against pre-normalized URI fields.
    :type search_normalized_uris: bool

    :returns: an Elasticsearch query dict corresponding to the given h search
        API params
    :rtype: dict
    """
    # NestedMultiDict objects are read-only, so we need to copy to make it
    # modifiable.
    request_params = request_params.copy()

    try:
        from_ = int(request_params.pop("offset"))
        if from_ < 0:
            raise ValueError
    except (ValueError, KeyError):
        from_ = 0

    try:
        size = int(request_params.pop("limit"))
        if size < 0:
            raise ValueError
    except (ValueError, KeyError):
        size = 20

    sort = [{
        request_params.pop("sort", "updated"): {
            "ignore_unmapped": True,
            "order": request_params.pop("order", "desc")
        }
    }]

    filters = []
    matches = []

    uri_param = request_params.pop("uri", None)
    if uri_param is None:
        pass
    elif search_normalized_uris:
        filters.append(_filter_for_uri_term(uri_param))
    else:
        filters.append(_filter_for_uri_match(uri_param))

    if "any" in request_params:
        matches.append({
            "multi_match": {
                "fields": ["quote", "tags", "text", "uri.parts", "user"],
                "query": request_params.getall("any"),
                "type": "cross_fields"
            }
        })
        del request_params["any"]

    for key, value in request_params.items():
        matches.append({"match": {key: value}})

    # Add a filter for "not in public site areas" considerations
    filters.append(nipsa.nipsa_filter(userid=userid))

    query = {"match_all": {}}

    if matches:
        query = {"bool": {"should": matches}}

    if filters:
        query = {
            "filtered": {
                "filter": {"and": filters},
                "query": query,
            }
        }

    return {
        "from": from_,
        "size": size,
        "sort": sort,
        "query": query,
    }


def _filter_for_uri_match(uristr):
    """Return an Elasticsearch match clause dict for the given URI."""
    uristrs = uri.expand(uristr)
    clauses = [{"match": {"uri": u}} for u in uristrs]

    if len(clauses) == 1:
        return {"query": clauses[0]}
    return {"query": {"bool": {"should": clauses}}}


def _filter_for_uri_term(uristr):
    """Return an Elasticsearch term clause for the given URI."""
    uristrs = uri.expand(uristr)
    clauses = [{"term": {"target.source_normalized": uri.normalize(u)}}
               for u in uristrs]

    if len(clauses) == 1:
        return clauses[0]
    return {
        "or": clauses
    }
