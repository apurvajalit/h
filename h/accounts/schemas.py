# -*- coding: utf-8 -*-
from pkg_resources import resource_stream

import colander
import deform
from horus import interfaces
from horus.schemas import email_exists, unique_email
from pyramid.session import check_csrf_token

from h.models import _
from h.accounts.models import User

USERNAME_BLACKLIST = None


@colander.deferred
def deferred_csrf_token(node, kw):
    request = kw.get('request')
    return request.session.get_csrf_token()


def get_blacklist():
    global USERNAME_BLACKLIST
    if USERNAME_BLACKLIST is None:
        USERNAME_BLACKLIST = set(
            l.strip().lower()
            for l in resource_stream(__package__, 'blacklist')
        )
    return USERNAME_BLACKLIST


def unique_username(node, value):
    '''Colander validator that ensures the username does not exist.'''
    request = node.bindings['request']
    user = User.get_by_username(request, value)
    if user:
        strings = request.registry.getUtility(interfaces.IUIStrings)
        raise colander.Invalid(node, strings.registration_username_exists)


def unblacklisted_username(node, value, blacklist=None):
    '''Colander validator that ensures the username is not blacklisted.'''
    if blacklist is None:
        blacklist = get_blacklist()
    if value.lower() in blacklist:
        # We raise a generic "user with this name already exists" error so as
        # not to make explicit the presence of a blacklist.
        req = node.bindings['request']
        str_ = req.registry.getUtility(interfaces.IUIStrings)
        raise colander.Invalid(node, str_.registration_username_exists)


def matching_emails(node, value):
    """Colander validator that ensures email and emailAgain fields match."""
    if value.get("email") != value.get("emailAgain"):
        exc = colander.Invalid(node)
        exc["emailAgain"] = _("The emails must match")
        raise exc


class CSRFSchema(colander.Schema):
    """
    A CSRFSchema backward-compatible with the one from the hem module.

    Unlike hem, this doesn't require that the csrf_token appear in the
    serialized appstruct.
    """

    csrf_token = colander.SchemaNode(colander.String(),
                                     widget=deform.widget.HiddenWidget(),
                                     default=deferred_csrf_token,
                                     missing=None)

    def validator(self, form, value):
        request = form.bindings['request']
        check_csrf_token(request)


class LoginSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String())
    password = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.PasswordWidget()
    )

    def validator(self, node, value):
        super(LoginSchema, self).validator(node, value)
        request = node.bindings['request']

        username = value.get('username')
        password = value.get('password')

        user = User.get_by_username(request, username)
        if user is None:
            user = User.get_by_email(request, username)

        if user is None:
            err = colander.Invalid(node)
            err['username'] = _('User does not exist.')
            raise err

        if not User.validate_user(user, password):
            err = colander.Invalid(node)
            err['password'] = _('Incorrect password. Please try again.')
            raise err

        if not user.is_activated:
            reason = _('Your account is not active. Please check your e-mail.')
            raise colander.Invalid(node, reason)

        value['user'] = user


class ForgotPasswordSchema(CSRFSchema):
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(colander.Email(), email_exists)
    )


def _new_password_schema_node():
    """Return a colander.SchemaNode for a new password.

    For use when registering a new account, changing the password of an
    existing account - whenever a new password is being created and needs to
    be validated.

    """
    return colander.SchemaNode(
        colander.String(),
        validator=colander.Length(min=2),
        widget=deform.widget.PasswordWidget()
    )


class RegisterSchema(CSRFSchema):
    username = colander.SchemaNode(
        colander.String(),
        validator=colander.All(
            colander.Length(min=3, max=15),
            colander.Regex('(?i)^[A-Z0-9._]+$'),
            unique_username,
            unblacklisted_username,
        ),
    )
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(
            colander.Email(),
            unique_email,
        ),
    )
    password = _new_password_schema_node()


class ResetPasswordSchema(CSRFSchema):
    username = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextInputWidget(template='readonly/textinput'),
        missing=colander.null,
    )
    password = _new_password_schema_node()


class ActivateSchema(CSRFSchema):
    code = colander.SchemaNode(
        colander.String(),
        title=_("Security Code")
    )
    password = _new_password_schema_node()
    password.title = _("New Password")


class ProfileSchema(CSRFSchema):

    """
    Validates a user profile form.

    This form is broken into multiple parts, for updating the email address,
    password, and subscriptions, so multiple fields are nullable.
    """

    username = colander.SchemaNode(colander.String())

    # This is the user's current password (not their new one, if they're
    # trying to change their password).
    pwd = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.PasswordWidget(),
        default='',
        missing=colander.null
    )
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.All(colander.Email(), unique_email),
        default='',
        missing=colander.null
    )
    emailAgain = colander.SchemaNode(
        colander.String(),
        default='',
        missing=colander.null,
    )

    # This is the user's new password, when they're trying to change their
    # password.
    password = _new_password_schema_node()
    password.title = _("Password")
    password.default = ''
    password.missing = colander.null

    subscriptions = colander.SchemaNode(
        colander.String(),
        missing=colander.null,
        default=''
    )

    def validator(self, node, value):
        super(ProfileSchema, self).validator(node, value)

        # Check that emails match
        matching_emails(node, value)


def includeme(config):
    registry = config.registry

    schemas = [
        (interfaces.ILoginSchema, LoginSchema),
        (interfaces.IRegisterSchema, RegisterSchema),
        (interfaces.IForgotPasswordSchema, ForgotPasswordSchema),
        (interfaces.IResetPasswordSchema, ResetPasswordSchema),
        (interfaces.IProfileSchema, ProfileSchema)
    ]

    for iface, imp in schemas:
        if not registry.queryUtility(iface):
            registry.registerUtility(imp, iface)
