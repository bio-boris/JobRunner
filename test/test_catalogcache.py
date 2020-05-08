# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch
from mock import MagicMock

from JobRunner.CatalogCache import CatalogCache
from nose.plugins.attrib import attr
from copy import deepcopy
from .mock_data import CATALOG_GET_MODULE_VERSION, NJS_JOB_PARAMS,\
    CATALOG_LIST_VOLUME_MOUNTS, CATALOG_GET_SECURE_CONFIG_PARAMS


class CatalogCacheTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = os.environ.get('KB_AUTH_TOKEN', None)
        cls.admin_token = os.environ.get('KB_ADMIN_AUTH_TOKEN', None)
        cls.cfg = {}
        base = 'https://ci.kbase.us/services/'
        cls.cfg = {
            'catalog-service-url': base + 'catalog',
            'token': cls.token,
            'admin_token': cls.admin_token
        }

    @patch('JobRunner.CatalogCache.Catalog', autospec=True)
    def test_cache(self, mock_cc):
        cc = CatalogCache(self.cfg)
        cc.catalog.get_module_version.return_value = \
            CATALOG_GET_MODULE_VERSION
        out = cc.get_module_info('bogus', 'method')
        self.assertIn('git_commit_hash', out)
        self.assertIn('cached', out)
        self.assertFalse(out['cached'])
        out = cc.get_module_info('bogus', 'method')
        self.assertIn('git_commit_hash', out)
        self.assertIn('cached', out)
        self.assertTrue(out['cached'])
        self.assertIn('secure_config_params', out)

    @patch('JobRunner.CatalogCache.Catalog', autospec=True)
    def test_secure_params(self, mock_cc):
        cc = CatalogCache(self.cfg)
        cc.catalog.get_module_version.return_value = \
            CATALOG_GET_MODULE_VERSION
        cc.catalog.get_secure_config_params.return_value = \
            CATALOG_GET_SECURE_CONFIG_PARAMS
        out = cc.get_module_info('bogus', 'method')
        self.assertIn('git_commit_hash', out)
        self.assertIn('cached', out)
        self.assertFalse(out['cached'])
        out = cc.get_module_info('bogus', 'method')
        self.assertIn('secure_config_params', out)
        self.assertGreater(len(out['secure_config_params']), 0)

    @patch('JobRunner.CatalogCache.Catalog', autospec=True)
    def test_volume(self, mock_cc):
        cc = CatalogCache(self.cfg)
        vols = deepcopy(CATALOG_LIST_VOLUME_MOUNTS)
        cc.catalog.list_volume_mounts = MagicMock(return_value=vols)
        out = cc.get_volume_mounts('bogus', 'method', 'upload')
        self.assertTrue(len(out) > 0)
        self.assertIn('host_dir', out[0])
