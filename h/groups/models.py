# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.orm import exc
import slugify

from h.db import Base


class Group(Base):
    __tablename__ = 'group'

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
    name = sa.Column(sa.Unicode(100), nullable=False)
    created = sa.Column(sa.DateTime,
                        server_default=sa.func.now(),
                        nullable=False)
    updated = sa.Column(sa.DateTime,
                        server_default=sa.func.now(),
                        onupdate=sa.func.now(),
                        nullable=False)

    # We store information about who created the group -- we don't use this
    # currently, but it seems careless to lose this information when in the
    # future these people may be the first admins of their groups.
    creator_id = sa.Column(
        sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    creator = sa.orm.relationship('User')

    # Group membership
    members = sa.orm.relationship('User',
                                  secondary='user_group',
                                  backref='groups')

    def __init__(self, name, creator):
        self.name = name
        self.creator = creator
        self.members.append(creator)

    @property
    def slug(self):
        """A version of this group's name suitable for use in a URL."""
        return slugify.slugify(self.name)

    def __repr__(self):
        return '<Group: %s>' % self.slug

    @classmethod
    def get_by_id(cls, id_):
        """Return the group with the given id, or None."""
        try:
            return cls.query.filter(
                cls.id == id_).one()
        except exc.NoResultFound:
            return None


USER_GROUP_TABLE = sa.Table(
    'user_group', Base.metadata,
    sa.Column('user_id',
              sa.Integer,
              sa.ForeignKey('user.id'),
              nullable=False),
    sa.Column('group_id',
              sa.Integer,
              sa.ForeignKey('group.id'),
              nullable=False)
)
