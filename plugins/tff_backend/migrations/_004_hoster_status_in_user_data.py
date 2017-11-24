# -*- coding: utf-8 -*-
# Copyright 2017 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.3@@
from google.appengine.ext import ndb

from framework.bizz.job import run_job
from plugins.tff_backend.bizz.hoster import set_hoster_status_in_user_data
from plugins.tff_backend.models.user import TffProfile


def migrate(dry_run=False):
    run_job(_get_all_tff_profiles, [], _set_status, [])


def _get_all_tff_profiles():
    return TffProfile.query()


def _set_status(profile_key):
    profile = profile_key.get()
    set_hoster_status_in_user_data(profile.app_user)