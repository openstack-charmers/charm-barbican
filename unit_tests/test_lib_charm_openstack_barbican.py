from __future__ import absolute_import
from __future__ import print_function

import unittest

import mock

import charm.openstack.barbican as barbican


class Helper(unittest.TestCase):

    def setUp(self):
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch(self, obj, attr, return_value=None):
        mocked = mock.patch.object(obj, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)


class TestOpenStackBarbican(Helper):

    def test_install(self):
        self.patch(barbican.BarbicanCharm, 'singleton')
        barbican.install()
        self.singleton.install.assert_called_once_with()

    def test_setup_amqp_req(self):
        amqp = mock.MagicMock()
        self.patch(barbican.hookenv, 'config')
        reply = {
            'rabbit-user': 'user1',
            'rabbit-vhost': 'vhost1',
        }
        self.config.side_effect = lambda x: reply[x]
        barbican.setup_amqp_req(amqp)
        amqp.request_access.assert_called_once_with(
            username='user1', vhost='vhost1')

    def test_database(self):
        database = mock.MagicMock()
        self.patch(barbican.hookenv, 'config')
        reply = {
            'database': 'db1',
            'database-user': 'dbuser1',
        }
        self.config.side_effect = lambda x: reply[x]
        self.patch(barbican.hookenv, 'unit_private_ip', 'private_ip')
        barbican.setup_database(database)
        database.configure.assert_called_once_with(
            'db1', 'dbuser1', 'private_ip')

    def test_setup_endpoint(self):
        self.patch(barbican.BarbicanCharm, 'singleton')
        self.singleton.service_type = 'type1'
        self.singleton.region = 'region1'
        self.singleton.public_url = 'public_url'
        self.singleton.internal_url = 'internal_url'
        self.singleton.admin_url = 'admin_url'
        keystone = mock.MagicMock()
        barbican.setup_endpoint(keystone)
        keystone.register_endpoints.assert_called_once_with(
            'type1', 'region1', 'public_url', 'internal_url', 'admin_url')

    def test_render_configs(self):
        self.patch(barbican.BarbicanCharm, 'singleton')
        barbican.render_configs('interfaces-list')
        self.singleton.render_interfaces.assert_called_once_with(
            'interfaces-list')


class TestBarbicanConfigurationAdapter(Helper):

    def test_barbican_configuration_adapter(self):
        self.patch(barbican.hookenv, 'config')
        reply = {
            'keystone-api-version': '2',
        }
        self.config.side_effect = lambda: reply
        # Make one with no errors, api version 2
        a = barbican.BarbicanConfigurationAdapter()
        self.assertEqual(a.barbican_api_keystone_pipeline,
                         'keystone_authtoken context apiapp')
        self.assertEqual(a.barbican_api_pipeline,
                         'keystone_authtoken context apiapp')
        # Now test it with api version 3
        reply['keystone-api-version'] = '3'
        a = barbican.BarbicanConfigurationAdapter()
        self.assertEqual(a.barbican_api_keystone_pipeline,
                         'keystone_v3_authtoken context apiapp')
        self.assertEqual(a.barbican_api_pipeline,
                         'keystone_v3_authtoken context apiapp')
        # and a 'none' version
        reply['keystone-api-version'] = 'none'
        a = barbican.BarbicanConfigurationAdapter()
        self.assertEqual(a.barbican_api_keystone_pipeline,
                         'keystone_v3_authtoken context apiapp')
        self.assertEqual(a.barbican_api_pipeline,
                         'unauthenticated-context apiapp')
        # finally, try to create an invalid one.
        reply['keystone-api-version'] = None
        with self.assertRaises(ValueError):
            a = barbican.BarbicanConfigurationAdapter()


class TestBarbicanAdapters(Helper):

    def test_barbican_adapters(self):
        self.patch(barbican.hookenv, 'config')
        reply = {
            'keystone-api-version': '2',
        }
        self.config.side_effect = lambda: reply
        amqp_relation = mock.MagicMock()
        amqp_relation.relation_name = 'amqp'
        shared_db_relation = mock.MagicMock()
        shared_db_relation.relation_name = 'shared_db'
        other_relation = mock.MagicMock()
        other_relation.relation_name = 'other'
        other_relation.thingy = 'help'
        # verify that the class is created with a BarbicanConfigurationAdapter
        b = barbican.BarbicanAdapters([amqp_relation,
                                       shared_db_relation,
                                       other_relation])
        # ensure that the relevant things got put on.
        self.assertTrue(
            isinstance(
                b.other,
                barbican.charmers.openstack.adapters.OpenStackRelationAdapter))
        self.assertTrue(isinstance(b.options,
                                   barbican.BarbicanConfigurationAdapter))


class TestBarbicanCharm(Helper):

    def test__init__(self):
        self.patch(barbican.ch_utils, 'os_release')
        barbican.BarbicanCharm()
        self.os_release.assert_called_once_with('python-keystonemiddleware')

    def test_install(self):
        self.patch(barbican.charmhelpers.fetch, 'add_source')
        b = barbican.BarbicanCharm()
        self.patch(barbican.charmers.openstack.charm.OpenStackCharm,
                   'configure_source')
        self.patch(barbican.charmers.openstack.charm.OpenStackCharm,
                   'install')
        b.install()
        self.add_source.assert_called_once_with('ppa:gnuoy/barbican-alt')
        self.configure_source.assert_called_once_with()
        self.install.assert_called_once_with()