#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: profitbricks_snapshot
short_description: Create or Restore a Snapshot.
description:
     - This module allows you to create or restore a volume snapshot. This module has a dependency on profitbricks >= 1.0.0
version_added: "1.9"
options:
  datacenter:
    description:
      - The datacenter in which to operate.
    required: true
    default: null
  volume:
    description:
      - The volume name or ID.
    required: true
    default: null
  snapshot:
    description:
      - The snapshot name or ID. This is used during a restore.
    required: true
    default: null
  description:
    description:
      - The description of the snapshot. Used in a create.
    required: false
    default: null
  snapshot_name:
    description:
      - The name of the snapshot.
    required: false
    default: null
  subscription_user:
    description:
      - The ProfitBricks username. Overrides the PB_SUBSCRIPTION_ID environement variable.
    required: false
    default: null
  subscription_password:
    description:
      - THe ProfitBricks password. Overrides the PB_PASSWORD environement variable.
    required: false
    default: null
  wait:
    description:
      - wait for the operation to complete before returning
    required: false
    default: "yes"
    choices: [ "yes", "no" ]
    aliases: []
  wait_timeout:
    description:
      - how long before wait gives up, in seconds
    default: 600
    aliases: []
  state:
    description:
      - Indicate desired state of the resource
    required: false
    default: 'present'
    aliases: []

requirements: [ "profitbricks" ]
author: Matt Baldwin (baldwin@stackpointcloud.com)
'''

EXAMPLES = '''

# Create a Basic Snapshot
- profitbricks_snapshot:
    datacenter: Tardis One
    volume: vol01
    wait_timeout: 500
    state: present

# Create a Snapshot with a name and description
- profitbricks_snapshot:
    datacenter: Tardis One
    volume: vol01
    snapshot_name: my super snapshot
    description: pre-deployment
    wait_timeout: 500
    state: present

# Remove a snapshot by name
- profitbricks_snapshot:
    snapshot: my super snapshot
    wait_timeout: 500
    state: absent

# Remove a snapshot
- profitbricks_snapshot:
    snapshot: 076017e1-cc53-48c3-b8fb-1841b6d773b5
    wait_timeout: 500
    state: absent

'''

import re
import uuid
import time
import json
import sys

try:
    from profitbricks.client import ProfitBricksService, Volume
except ImportError:
    print "failed=True msg='profitbricks required for this module'"
    sys.exit(1)

uuid_match = re.compile(
    '[\w]{8}-[\w]{4}-[\w]{4}-[\w]{4}-[\w]{12}', re.I)


def _wait_for_completion(profitbricks, promise, wait_timeout, msg):
    if not promise: return
    wait_timeout = time.time() + wait_timeout
    while wait_timeout > time.time():
        time.sleep(5)
        operation_result = profitbricks.get_request(
            request_id=promise['requestId'],
            status=True)

        if operation_result['metadata']['status'] == "DONE":
            return
        elif operation_result['metadata']['status'] == "FAILED":
            raise Exception('Request failed to complete ' + msg + ' "' + str(promise['requestId']) + '" to complete.')

    raise Exception('Timed out waiting for async operation ' + msg + ' "' + str(promise['requestId']) + '" to complete.')

def create_snapshot(module, profitbricks):
    """
    Creates a snapshot from a volume.

    module : AnsibleModule object
    profitbricks: authenticated profitbricks object.

    Returns:
        True if the snapshot succeeds, false otherwise
    """
    datacenter = module.params.get('datacenter')
    volume = module.params.get('volume')
    snapshot_name = module.params.get('snapshot_name')
    description = module.params.get('description')

    # Locate UUID for Datacenter
    if not (uuid_match.match(datacenter)):
        datacenter_list = profitbricks.list_datacenters()
        for d in datacenter_list['items']:
            dc = profitbricks.get_datacenter(d['id'])
            if datacenter == dc['properties']['name']:
                datacenter = d['id']
                break

    # Locate UUID for Volume
    if not (uuid_match.match(volume)):
        volume_list = profitbricks.list_volumes(datacenter)
        for v in volume_list['items']:
            if volume == v['properties']['name']:
                volume = v['id']
                break

    return profitbricks.create_snapshot(datacenter, volume, snapshot_name, description)

def remove_snapshot(module, profitbricks):
    """
    Removes a snapshot

    module : AnsibleModule object
    profitbricks: authenticated profitbricks object.

    Returns:
        True if the snapshot was removed, false otherwise
    """
    snapshot = module.params.get('snapshot')

    # Locate UUID for Snapshot
    if not (uuid_match.match(snapshot)):
        snapshot_list = profitbricks.list_snapshots()
        for s in snapshot_list['items']:
            if snapshot == s['properties']['name']:
                snapshot = s['id']
                break

    return profitbricks.remove_snapshot(snapshot)

def main():
    module = AnsibleModule(
        argument_spec=dict(
            datacenter=dict(),
            volume=dict(),
            snapshot=dict(),
            snapshot_name=dict(),
            description=dict(),
            subscription_user=dict(),
            subscription_password=dict(),
            wait=dict(type='bool', default=True),
            wait_timeout=dict(default=600),
            state=dict(default='present'),
        )
    )

    if not module.params.get('subscription_user'):
        module.fail_json(msg='subscription_user parameter is required')
    if not module.params.get('subscription_password'):
        module.fail_json(msg='subscription_password parameter is required')

    subscription_user = module.params.get('subscription_user')
    subscription_password = module.params.get('subscription_password')

    profitbricks = ProfitBricksService(
        username=subscription_user,
        password=subscription_password)

    state = module.params.get('state')

    if state == 'absent':
        if not module.params.get('snapshot'):
            module.fail_json(msg='snapshot parameter is required')

        (changed) = remove_snapshot(module, profitbricks)

        module.exit_json(
            changed=changed)

    elif state == 'present':
        if not module.params.get('datacenter'):
            module.fail_json(msg='datacenter parameter is required')
        if not module.params.get('volume'):
            module.fail_json(msg='volume parameter is required')

        (snapshot_dict) = create_snapshot(module, profitbricks)

        module.exit_json(
            snapshot=snapshot_dict)

from ansible.module_utils.basic import *

main()