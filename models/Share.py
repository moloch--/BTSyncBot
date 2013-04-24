# -*- coding: utf-8 -*-
'''
Created on Mar 12, 2012

@author: moloch

Copyright [2012]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''


from models import dbsession
from sqlalchemy import Column, or_
from sqlalchemy.types import String
from models.BaseObject import BaseObject


class Share(BaseObject):

    name = Column(String(32), unique=True, nullable=False)
    private_key = Column(String(32), unique=True, nullable=False)
    description = Column(String(255), nullable=False)

    @classmethod
    def by_id(cls, sid):
        ''' Return the share object whose id is 'sid' '''
        return dbsession.query(cls).filter_by(id=sid).first()

    @classmethod
    def by_name(cls, sname):
        ''' Return the share object whose name is 'sname' '''
        return dbsession.query(cls).filter_by(name=sname).first()

    @classmethod
    def by_search(cls, search):
        return dbsession.query(cls).filter(
            or_(cls.name.like("%"+search+"%"), cls.description.like("%"+search+"%"))
        ).all()

    @property
    def read_only(self):
        return self.private_key.startswith('R')