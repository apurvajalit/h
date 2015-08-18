import logging

from h import i18n

from h.api.models import Annotation
from h.api import nipsa
from h.api import search as search_lib
from h.api import groups


_ = i18n.TranslationString
log = logging.getLogger(__name__)


# These annotation fields are not to be set by the user.
PROTECTED_FIELDS = ['created', 'updated', 'user', 'consumer', 'id']


def create_annotation(fields, user, effective_principals):
    """Create and store an annotation.

    :raises RuntimeError: If the request isn't authorized to write to the
        annotation's group.

    """
    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)

    # Create Annotation instance
    annotation = Annotation(fields)

    groups.set_group_if_reply(annotation)

    if not groups.authorized_to_write_group(
            effective_principals, annotation.get('group')):
        raise RuntimeError(_('Not authorized to write to group.'), 401)

    annotation['user'] = user.id
    annotation['consumer'] = user.consumer.key

    if nipsa.has_nipsa(user.id):
        annotation["nipsa"] = True

    # Save it in the database
    search_lib.prepare(annotation)
    annotation.save()

    log.debug('Created annotation; user: %s, consumer key: %s',
              annotation['user'], annotation['consumer'])

    return annotation


def _anonymize_deletes(annotation):
    """Clear the author and remove the user from the annotation permissions."""
    # Delete the annotation author, if present
    user = annotation.pop('user')

    # Remove the user from the permissions, but keep any others in place.
    permissions = annotation.get('permissions', {})
    for action in permissions.keys():
        filtered = [
            role
            for role in annotation['permissions'][action]
            if role != user
        ]
        annotation['permissions'][action] = filtered


def update_annotation(annotation, fields, has_admin_permission,
                      effective_principals):
    """Update the given annotation with the given new fields.

    :raises RuntimeError: if the fields attempt to change the annotation's
       permissions and has_admin_permission is False, or if
       effective_principals aren't authorized to write to the annotation's
       group

    """
    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)

    # If the user is changing access permissions, check if it's allowed.
    changing_permissions = (
        'permissions' in fields and
        fields['permissions'] != annotation.get('permissions', {})
    )
    if changing_permissions and not has_admin_permission:
        raise RuntimeError(
            _('Not authorized to change annotation permissions.'), 401)

    can_write_old_group = groups.authorized_to_write_group(
        effective_principals, annotation.get('group'))
    can_write_new_group = groups.authorized_to_write_group(
        effective_principals, fields.get('group'))
    if not (can_write_old_group and can_write_new_group):
        raise RuntimeError(_('Not authorized to write to group.'), 401)

    # Update the annotation with the new data
    annotation.update(fields)

    groups.set_group_if_reply(annotation)

    # If the annotation is flagged as deleted, remove mentions of the user
    if annotation.get('deleted', False):
        _anonymize_deletes(annotation)

    # Save the annotation in the database, overwriting the old version.
    search_lib.prepare(annotation)
    annotation.save()


def delete_annotation(annotation, effective_principals):
    if not groups.authorized_to_write_group(
            effective_principals, annotation.get('group')):
        raise RuntimeError(_('Not authorized to write to group.'), 401)
    annotation.delete()
