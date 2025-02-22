"""QGIS Unit tests for QgsImageCache.

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
__author__ = '(C) 2018 by Nyall Dawson'
__date__ = '02/10/2018'
__copyright__ = 'Copyright 2018, The QGIS Project'

import http.server
import os
import socketserver
import threading
import time

from qgis.PyQt.QtCore import QCoreApplication, QDir, QSize
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.core import (
    QgsApplication,
    QgsMultiRenderChecker,
    QgsRenderChecker,
)
import unittest
from qgis.testing import start_app, QgisTestCase

from utilities import unitTestDataPath

start_app()
TEST_DATA_DIR = unitTestDataPath()


class SlowHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        time.sleep(1)
        return http.server.SimpleHTTPRequestHandler.do_GET(self)


class TestQgsImageCache(QgisTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Bring up a simple HTTP server, for remote SVG tests
        os.chdir(unitTestDataPath() + '')
        handler = SlowHTTPRequestHandler

        cls.httpd = socketserver.TCPServer(('localhost', 0), handler)
        cls.port = cls.httpd.server_address[1]

        cls.httpd_thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.httpd_thread.daemon = True
        cls.httpd_thread.start()

    def setUp(self):
        self.report = "<h1>Python QgsImageCache Tests</h1>\n"

        self.fetched = False
        QgsApplication.imageCache().remoteImageFetched.connect(self.imageFetched)

    def tearDown(self):
        report_file_path = f"{QDir.tempPath()}/qgistest.html"
        with open(report_file_path, 'a') as report_file:
            report_file.write(self.report)

    def imageFetched(self):
        self.fetched = True

    def waitForFetch(self):
        self.fetched = False
        while not self.fetched:
            QCoreApplication.processEvents()

    def testRemoteImage(self):
        """Test fetching remote image."""
        url = f'http://localhost:{str(TestQgsImageCache.port)}/qgis_local_server/sample_image.png'
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0)

        # first should be waiting image
        self.assertTrue(self.imageCheck('Remote Image', 'waiting_image', image))
        self.assertFalse(QgsApplication.imageCache().originalSize(url).isValid())
        self.waitForFetch()

        # second should be correct image
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0)

        self.assertTrue(self.imageCheck('Remote Image', 'remote_image', image))
        self.assertEqual(QgsApplication.imageCache().originalSize(url), QSize(511, 800), 1.0)

    def testRemoteImageMissing(self):
        """Test fetching remote image with bad url"""
        url = f'http://localhost:{str(TestQgsImageCache.port)}/qgis_local_server/xxx.png'  # oooo naughty
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0)

        self.assertTrue(self.imageCheck('Remote image missing', 'waiting_image', image))

    def testRemoteImageBlocking(self):
        """Test fetching remote image."""
        # remote not yet requested so not in cache
        url = f'http://localhost:{str(TestQgsImageCache.port)}/qgis_local_server/logo_2017.png'
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0, blocking=1)

        # first should be correct image
        self.assertTrue(self.imageCheck('Remote image sync', 'remote_image_blocking', image))

        # remote probably in cache
        url = f'http://localhost:{str(TestQgsImageCache.port)}/qgis_local_server/sample_image.png'
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0, blocking=1)

        self.assertTrue(self.imageCheck('Remote Image', 'remote_image', image))

        # remote probably in cache
        url = f'http://localhost:{str(TestQgsImageCache.port)}/qgis_local_server/xxx.png'  # oooo naughty
        image, in_cache = QgsApplication.imageCache().pathAsImage(url, QSize(100, 100), True, 1.0, blocking=1)

        self.assertTrue(self.imageCheck('Remote image missing', 'waiting_image', image))

    def imageCheck(self, name, reference_image, image):
        self.report += f"<h2>Render {name}</h2>\n"
        temp_dir = QDir.tempPath() + '/'
        file_name = temp_dir + 'image_' + name + ".png"

        output_image = QImage(image.size(), QImage.Format.Format_RGB32)
        QgsMultiRenderChecker.drawBackground(output_image)
        painter = QPainter(output_image)
        painter.drawImage(0, 0, image)
        painter.end()

        output_image.save(file_name, "PNG")
        checker = QgsRenderChecker()
        checker.setControlPathPrefix("image_cache")
        checker.setControlName("expected_" + reference_image)
        checker.setRenderedImage(file_name)
        checker.setColorTolerance(2)
        result = checker.compareImages(name, 20)
        self.report += checker.report()
        print(self.report)
        return result


if __name__ == '__main__':
    unittest.main()
