import pytest
import mock

from h import api
from h.api import logic


def _mock_annotation(**kwargs):
    """Return a mock h.api.models.Annotation object."""
    annotation = mock.MagicMock()
    annotation.__getitem__.side_effect = kwargs.__getitem__
    annotation.__setitem__.side_effect = kwargs.__setitem__
    annotation.get.side_effect = kwargs.get
    annotation.__contains__.side_effect = kwargs.__contains__
    annotation.update.side_effect = kwargs.update
    annotation.pop.side_effect = kwargs.pop
    return annotation


# The fixtures required to mock all of create_annotation()'s dependencies.
create_annotation_fixtures = pytest.mark.usefixtures(
    'Annotation', 'nipsa', 'search_lib', 'groups')


@create_annotation_fixtures
def test_create_annotation_pops_protected_fields(Annotation):
    """It should remove any protected fields before calling Annotation."""
    Annotation.return_value = _mock_annotation()
    logic.create_annotation(
        fields={
            'foo': 'bar',
            'created': 'foo',
            'updated': 'foo',
            'user': 'foo',
            'consumer': 'foo',
            'id': 'foo'
        },
        user=mock.Mock(), effective_principals=[])

    for field in ('created', 'updated', 'user', 'consumer', 'id'):
        assert field not in Annotation.call_args[0][0]


@create_annotation_fixtures
def test_create_annotation_calls_Annotation(Annotation):
    Annotation.return_value = _mock_annotation()
    fields = mock.MagicMock()
    logic.create_annotation(fields, mock.Mock(), [])

    Annotation.assert_called_once_with(fields)


@create_annotation_fixtures
def test_create_annotation_calls_set_group_if_reply(Annotation, groups):
    annotation = Annotation.return_value = _mock_annotation()

    logic.create_annotation(mock.MagicMock(), mock.Mock(), [])

    groups.set_group_if_reply.assert_called_once_with(annotation)


@create_annotation_fixtures
def test_create_annotation_calls_authorized_to_write_group(Annotation, groups):
    annotation_data = {
        'group': 'test-group', 'user': 'user', 'consumer': 'consumer'}
    annotation = mock.MagicMock()
    annotation.__getitem__.side_effect = annotation_data.__getitem__
    annotation.get.side_effect = annotation_data.get
    Annotation.return_value = annotation

    logic.create_annotation(
        {}, mock.Mock(), mock.sentinel.effective_principals)

    groups.authorized_to_write_group.assert_called_once_with(
        mock.sentinel.effective_principals, 'test-group')


@create_annotation_fixtures
def test_create_annotation_raises_if_user_is_not_group_member(groups):
    """It should raise if authorized_to_write_group() returns False."""
    groups.authorized_to_write_group.return_value = False

    with pytest.raises(RuntimeError):
        logic.create_annotation({}, mock.Mock(), [])


@create_annotation_fixtures
def test_create_annotation_sets_user(Annotation):
    """It should set the annotation's 'user' field to the user's id."""
    user = mock.Mock()
    Annotation.return_value = _mock_annotation()

    annotation = logic.create_annotation({}, user, [])

    assert annotation['user'] == user.id


@create_annotation_fixtures
def test_create_annotation_sets_consumer(Annotation):
    """It should set the annotation's 'consumer' field to the consumer key."""
    user = mock.Mock()
    Annotation.return_value = _mock_annotation()

    annotation = logic.create_annotation({}, user, [])

    assert annotation['consumer'] == user.consumer.key


@create_annotation_fixtures
def test_create_annotation_calls_nipsa(Annotation, nipsa):
    """It should call has_nipsa() once with the user's id."""
    Annotation.return_value = _mock_annotation()
    user = mock.Mock()

    logic.create_annotation({}, user, [])

    nipsa.has_nipsa.assert_called_once_with(user.id)


@create_annotation_fixtures
def test_create_annotation_sets_nipsa_if_user_is_nipsad(Annotation, nipsa):
    Annotation.return_value = _mock_annotation()
    # The user is nipsa'd.
    nipsa.has_nipsa.return_value = True

    annotation = logic.create_annotation({}, mock.Mock(), [])

    assert annotation['nipsa'] is True


@create_annotation_fixtures
def test_create_annotation_does_not_set_nipsa_if_user_is_not_nipsad(
        Annotation, nipsa):
    Annotation.return_value = _mock_annotation()
    # The user is not nipsa'd.
    nipsa.has_nipsa.return_value = False

    annotation = logic.create_annotation({}, mock.Mock(), [])

    assert 'nipsa' not in annotation


@create_annotation_fixtures
def test_create_annotation_calls_prepare(Annotation, search_lib):
    """It should call prepare() once with the annotation."""
    Annotation.return_value = _mock_annotation()
    logic.create_annotation({}, mock.Mock(), [])

    search_lib.prepare.assert_called_once_with(Annotation.return_value)


@create_annotation_fixtures
def test_create_annotation_calls_save(Annotation):
    """It should call save() once."""
    Annotation.return_value = _mock_annotation()

    logic.create_annotation({}, mock.Mock(), [])

    Annotation.return_value.save.assert_called_once_with()


@create_annotation_fixtures
def test_create_annotation_returns_the_annotation(Annotation):
    Annotation.return_value = _mock_annotation()

    assert logic.create_annotation({}, mock.Mock(), []) == (
            Annotation.return_value)


@create_annotation_fixtures
def test_create_annotation_does_not_crash_if_annotation_has_no_group(
        Annotation):
    Annotation.return_value = _mock_annotation()
    assert 'group' not in Annotation.return_value
    fields = {}  # No group here either.

    logic.create_annotation(fields, mock.Mock(), [])


@create_annotation_fixtures
def test_create_annotation_does_not_crash_if_annotations_parent_has_no_group(
        Annotation):
    """It shouldn't crash if the parent annotation has no group.

    It shouldn't crash if the annotation is a reply and its parent annotation
    has no 'group' field.

    """
    # No group in the original annotation/reply itself.
    Annotation.return_value = _mock_annotation()
    assert 'group' not in Annotation.return_value
    fields = {}  # No group here either.

    # And no group in the parent annotation either.
    Annotation.fetch.return_value = {}

    logic.create_annotation(fields, mock.Mock(), [])


# The fixtures required to mock all of update_annotation()'s dependencies.
update_annotation_fixtures = pytest.mark.usefixtures('search_lib', 'groups')


@update_annotation_fixtures
def test_update_annotation_does_not_pass_protected_fields_to_update():
    annotation = _mock_annotation(group='foo')

    logic.update_annotation(
        annotation,
        fields={
            'foo': 'bar',
            'created': 'foo',
            'updated': 'foo',
            'user': 'foo',
            'consumer': 'foo',
            'id': 'foo'
        },
        has_admin_permission=False, effective_principals=['group:foo'])

    for field in ('created', 'updated', 'user', 'consumer', 'id'):
        assert field not in annotation.update.call_args[0][0]


@update_annotation_fixtures
def test_update_annotation_raises_if_non_admin_changes_perms():
    with pytest.raises(RuntimeError):
        logic.update_annotation(
            _mock_annotation(),
            fields={'permissions': 'changed'},
            has_admin_permission=False,
            effective_principals=[])


@update_annotation_fixtures
def test_update_annotation_admins_can_change_permissions():
    annotation = _mock_annotation(permissions='foo', group='test-group')

    logic.update_annotation(
        annotation,
        fields={'permissions': 'changed'},
        has_admin_permission=True,
        effective_principals=['group:test-group'])

    assert annotation['permissions'] == 'changed'


@update_annotation_fixtures
def test_update_annotation_non_admins_can_make_non_permissions_changes():
    annotation = _mock_annotation(foo='bar', group='test-group')

    logic.update_annotation(
        annotation,
        fields={'foo': 'changed'},
        has_admin_permission=False,
        effective_principals=['group:test-group'])

    assert annotation['foo'] == 'changed'


@update_annotation_fixtures
def test_update_annotation_calls_update():
    annotation = _mock_annotation(group='test-group')
    fields = {'foo': 'bar'}

    logic.update_annotation(annotation, fields, False, ['group:test-group'])

    annotation.update.assert_called_once_with(fields)


@update_annotation_fixtures
def test_update_annotation_calls_set_group_if_reply(groups):
    annotation = _mock_annotation()

    logic.update_annotation(annotation, {}, False, [])

    groups.set_group_if_reply.assert_called_once_with(annotation)


@update_annotation_fixtures
def test_update_annotation_user_can_change_group():
    annotation = _mock_annotation(group='old')
    fields = {'group': 'new'}

    # Since effective_principals has both 'group:old' and the 'group:new' we
    # should be able to change the annotation's group from 'old' to 'new'.
    logic.update_annotation(
            annotation, fields, False, ['group:old', 'group:new'])

    assert annotation['group'] == 'new'


@update_annotation_fixtures
def test_update_annotation_calls_authorized_to_write_group_twice(groups):
    """It should call authorized_to_write_group() twice.

    Once with the annotation's old group and once with the new one.

    """
    annotation = _mock_annotation(group='old')
    fields = {'group': 'new'}
    effective_principals = mock.sentinel.effective_principals

    logic.update_annotation(annotation, fields, False, effective_principals)

    assert groups.authorized_to_write_group.call_args_list == [
        mock.call(effective_principals, 'old'),
        mock.call(effective_principals, 'new')
    ]


@update_annotation_fixtures
def test_update_annotation_raises_if_user_is_not_a_member_of_old_group(groups):
    # Request is authorized to write to group 'new', but not to 'old'.
    def side_effect(effective_principals, group_hashid):
        if group_hashid == 'old':
            return False
        else:
            return True
    groups.authorized_to_write_group.side_effect = side_effect

    # Moving the annotation from group 'old' to 'new'.
    annotation = _mock_annotation(group='old')
    fields = {'group': 'new'}

    with pytest.raises(RuntimeError):
        logic.update_annotation(
            annotation, fields, False, ['group:old'])


@update_annotation_fixtures
def test_update_annotation_raises_if_user_is_not_a_member_of_new_group(groups):
    # Request is authorized to write to group 'old', but not to 'new'.
    def side_effect(effective_principals, group_hashid):
        if group_hashid == 'new':
            return False
        else:
            return True
    groups.authorized_to_write_group.side_effect = side_effect

    # Moving the annotation from group 'old' to 'new'.
    annotation = _mock_annotation(group='old')
    fields = {'group': 'new'}

    with pytest.raises(RuntimeError):
        logic.update_annotation(
            annotation, fields, False, ['group:old'])


@update_annotation_fixtures
def test_update_annotation_removes_userid_from_permissions_if_deleted():
    user = 'acct:fred@hypothes.is'
    annotation = _mock_annotation(
        deleted=True,
        user=user,
        permissions={
            'admin': [user, 'someone else'],
            'read': [user, 'someone else'],
            'update': ['someone else'],
            'delete': ['someone else']
        },
        group='foo'
    )
    fields = {
        'permissions': {
            'update': [user],
            'delete': [user]
        }
    }

    logic.update_annotation(annotation, fields, True, ['group:foo'])

    for action in annotation['permissions']:
        assert user not in annotation['permissions'][action]


@update_annotation_fixtures
def test_update_annotation_does_not_remove_userid_if_not_deleted():
    user = 'acct:fred@hypothes.is'
    annotation = _mock_annotation(
        deleted=False,
        user=user,
        permissions={
            'admin': [user, 'someone else'],
            'read': [user, 'someone else'],
            'update': ['someone else'],
            'delete': ['someone else']
        },
        group='foo'
    )
    fields = {
        'permissions': {
            'update': [user],
            'delete': [user]
        }
    }

    logic.update_annotation(annotation, fields, True, ['group:foo'])

    for action in annotation['permissions']:
        assert user in annotation['permissions'][action]


@update_annotation_fixtures
def test_update_annotation_if_deleted_does_not_remove_other_principals():
    user = 'acct:fred@hypothes.is'
    annotation = _mock_annotation(
        deleted=True,
        user=user,
        permissions={
            'admin': [user, 'someone else'],
            'read': [user, 'someone else'],
            'update': [user],
            'delete': [user]
        },
        group='foo'
    )
    fields = {
        'permissions': {
            'update': ['someone else'],
            'delete': ['someone else']
        }
    }

    logic.update_annotation(annotation, fields, True, ['group:foo'])

    for action in annotation['permissions']:
        assert 'someone else' in annotation['permissions'][action]


@update_annotation_fixtures
def test_update_annotation_calls_prepare(search_lib):
    annotation = _mock_annotation(group='foo')

    logic.update_annotation(annotation, {}, False, ['group:foo'])

    search_lib.prepare.assert_called_once_with(annotation)


@update_annotation_fixtures
def test_update_annotation_calls_save():
    annotation = _mock_annotation(group='foo')

    logic.update_annotation(annotation, {}, False, ['group:foo'])

    annotation.save.assert_called_once_with()


@update_annotation_fixtures
def test_update_annotation_does_not_crash_if_annotation_has_no_group():
    annotation = _mock_annotation()
    assert 'group' not in annotation

    logic.update_annotation(annotation, {}, False, [])


@update_annotation_fixtures
def test_update_annotation_does_not_crash_if_annotations_parent_has_no_group(
        Annotation):
    """It shouldn't crash if the parent annotation has no group.

    It shouldn't crash if the annotation is a reply and its parent annotation
    has no 'group' field.

    """
    # No group in the original annotation/reply itself.
    annotation = _mock_annotation()
    assert 'group' not in annotation

    # And no group in the parent annotation either.
    Annotation.fetch.return_value = {}

    logic.update_annotation(annotation, {}, False, [])


# The fixtures required to mock all of delete_annotation()'s dependencies.
delete_annotation_fixtures = pytest.mark.usefixtures('groups')


@delete_annotation_fixtures
def test_delete_annotation_calls_authorized_to_write_group(groups):
    annotation = mock.MagicMock()
    annotation_data = {'group': 'test-group'}
    annotation.get.side_effect = annotation_data.get
    annotation.__getitem__.side_effect = annotation_data.__getitem__
    effective_principals = mock.sentinel.effective_principals

    logic.delete_annotation(annotation, effective_principals)

    groups.authorized_to_write_group.assert_called_once_with(
        effective_principals, 'test-group')


@delete_annotation_fixtures
def test_delete_annotation_raises_if_user_is_not_authed_for_group(groups):
    groups.authorized_to_write_group.return_value = False

    with pytest.raises(RuntimeError):
        logic.delete_annotation({'group': 'test-group'}, [])


@delete_annotation_fixtures
def test_delete_does_not_crash_if_annotation_has_no_group():
    annotation = mock.MagicMock()
    annotation_data = {}  # No 'group' key.
    annotation.get.side_effect = annotation_data.get
    annotation.__getitem__.side_effect = annotation_data.__getitem__

    logic.delete_annotation(annotation, [])


@delete_annotation_fixtures
def test_delete_annotation_calls_delete():
    annotation = mock.MagicMock(group='test-group')

    logic.delete_annotation(annotation, [])

    annotation.delete.assert_called_once_with()


@pytest.fixture
def Annotation(request):
    patcher = mock.patch('h.api.logic.Annotation', autospec=True)
    request.addfinalizer(patcher.stop)
    return patcher.start()


@pytest.fixture
def nipsa(request):
    patcher = mock.patch('h.api.logic.nipsa', autospec=True)
    request.addfinalizer(patcher.stop)
    return patcher.start()


@pytest.fixture
def search_lib(request):
    patcher = mock.patch('h.api.logic.search_lib', autospec=True)
    request.addfinalizer(patcher.stop)
    return patcher.start()


@pytest.fixture
def groups(request):
    patcher = mock.patch('h.api.logic.groups', autospec=True)
    request.addfinalizer(patcher.stop)
    return patcher.start()
