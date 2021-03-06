import pytest
import mock

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
    'Annotation', 'nipsa', 'search_lib',)


@create_annotation_fixtures
def test_create_annotation_pops_protected_fields(Annotation):
    """It should remove any protected fields before calling Annotation."""
    logic.create_annotation(
        fields={
            'foo': 'bar',
            'created': 'foo',
            'updated': 'foo',
            'user': 'foo',
            'consumer': 'foo',
            'id': 'foo'
        },
        user=mock.Mock())

    for field in ('created', 'updated', 'user', 'consumer', 'id'):
        assert field not in Annotation.call_args[0][0]


@create_annotation_fixtures
def test_create_annotation_calls_Annotation(Annotation):
    fields = mock.MagicMock()
    logic.create_annotation(fields, mock.Mock())

    Annotation.assert_called_once_with(fields)


@create_annotation_fixtures
def test_create_annotation_sets_user(Annotation):
    """It should set the annotation's 'user' field to the user's id."""
    user = mock.Mock()
    Annotation.return_value = _mock_annotation()

    annotation = logic.create_annotation({}, user)

    assert annotation['user'] == user.id


@create_annotation_fixtures
def test_create_annotation_sets_consumer(Annotation):
    """It should set the annotation's 'consumer' field to the consumer key."""
    user = mock.Mock()
    Annotation.return_value = _mock_annotation()

    annotation = logic.create_annotation({}, user)

    assert annotation['consumer'] == user.consumer.key


@create_annotation_fixtures
def test_create_annotation_calls_nipsa(nipsa):
    """It should call has_nipsa() once with the user's id."""
    user = mock.Mock()

    logic.create_annotation({}, user)

    nipsa.has_nipsa.assert_called_once_with(user.id)


@create_annotation_fixtures
def test_create_annotation_sets_nipsa_if_user_is_nipsad(Annotation, nipsa):
    Annotation.return_value = _mock_annotation()
    # The user is nipsa'd.
    nipsa.has_nipsa.return_value = True

    annotation = logic.create_annotation({}, mock.Mock())

    assert annotation['nipsa'] is True


@create_annotation_fixtures
def test_create_annotation_does_not_set_nipsa_if_user_is_not_nipsad(
        Annotation, nipsa):
    Annotation.return_value = _mock_annotation()
    # The user is not nipsa'd.
    nipsa.has_nipsa.return_value = False

    annotation = logic.create_annotation({}, mock.Mock())

    assert 'nipsa' not in annotation


@create_annotation_fixtures
def test_create_annotation_calls_prepare(Annotation, search_lib):
    """It should call prepare() once with the annotation."""
    logic.create_annotation({}, mock.Mock())

    search_lib.prepare.assert_called_once_with(Annotation.return_value)


@create_annotation_fixtures
def test_create_annotation_calls_save(Annotation):
    """It should call save() once."""
    logic.create_annotation({}, mock.Mock())

    Annotation.return_value.save.assert_called_once_with()


@create_annotation_fixtures
def test_create_annotation_returns_the_annotation(Annotation):
    assert logic.create_annotation({}, mock.Mock()) == Annotation.return_value


# The fixtures required to mock all of update_annotation()'s dependencies.
update_annotation_fixtures = pytest.mark.usefixtures('search_lib')


@update_annotation_fixtures
def test_update_annotation_does_not_pass_protected_fields_to_update():
    annotation = _mock_annotation()

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
        has_admin_permission=False)

    for field in ('created', 'updated', 'user', 'consumer', 'id'):
        assert field not in annotation.update.call_args[0][0]


@update_annotation_fixtures
def test_update_annotation_raises_if_non_admin_changes_perms():
    with pytest.raises(RuntimeError):
        logic.update_annotation(
            _mock_annotation(),
            fields={'permissions': 'changed'},
            has_admin_permission=False)


@update_annotation_fixtures
def test_update_annotation_admins_can_change_permissions():
    annotation = _mock_annotation(permissions='foo')

    logic.update_annotation(
        annotation,
        fields={'permissions': 'changed'},
        has_admin_permission=True)

    assert annotation['permissions'] == 'changed'


@update_annotation_fixtures
def test_update_annotation_non_admins_can_make_non_permissions_changes():
    annotation = _mock_annotation(foo='bar')

    logic.update_annotation(
        annotation,
        fields={'foo': 'changed'},
        has_admin_permission=False)

    assert annotation['foo'] == 'changed'


@update_annotation_fixtures
def test_update_annotation_calls_update():
    annotation = _mock_annotation()
    fields = {'foo': 'bar'}

    logic.update_annotation(annotation, fields, False)

    annotation.update.assert_called_once_with(fields)


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
        }
    )
    fields = {
        'permissions': {
            'update': [user],
            'delete': [user]
        }
    }

    logic.update_annotation(annotation, fields, True)

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
        }
    )
    fields = {
        'permissions': {
            'update': [user],
            'delete': [user]
        }
    }

    logic.update_annotation(annotation, fields, True)

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
        }
    )
    fields = {
        'permissions': {
            'update': ['someone else'],
            'delete': ['someone else']
        }
    }

    logic.update_annotation(annotation, fields, True)

    for action in annotation['permissions']:
        assert 'someone else' in annotation['permissions'][action]


@update_annotation_fixtures
def test_update_annotation_calls_prepare(search_lib):
    annotation = _mock_annotation()

    logic.update_annotation(annotation, {}, False)

    search_lib.prepare.assert_called_once_with(annotation)


@update_annotation_fixtures
def test_update_annotation_calls_save():
    annotation = _mock_annotation()

    logic.update_annotation(annotation, {}, False)

    annotation.save.assert_called_once_with()


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
