import unittest


class tempdir(object):

    def __enter__(self):
        import tempfile
        self.tempdir = tempfile.mkdtemp()
        return self.tempdir

    def __exit__(self, type, value, traceback):
        import shutil
        shutil.rmtree(self.tempdir)


class TestUniquifyGenerator(unittest.TestCase):

    enqueued_list = set()

    def fake_enqueue(self, value):
        self.enqueued_list.add(value)

    def fake_enqueue_batch(self, values):
        n = 0
        for value in values:
            n += 1
            self.fake_enqueue(value)
        return n, 0

    def test_uniquify_generator(self):
        from tilequeue.command import uniquify_generator
        from itertools import cycle, islice, tee
        gen = islice(cycle(xrange(5)), 10)
        gen, gencopy = tee(gen)
        uniqued_gen = uniquify_generator(gencopy)
        self.assertEqual(range(5) + range(5), list(gen))
        self.assertEqual(range(5), list(uniqued_gen))

    def test_tilequeue_intersect_removes_expired_list_file(self):
        from mock import MagicMock
        from tilequeue.command import tilequeue_intersect
        import os
        import shutil
        cfg_mock = MagicMock()
        cfg_mock.queue_type = 'sqs'
        periperals_mock = MagicMock()
        queue_mock = MagicMock()
        periperals_mock.queue = queue_mock
        queue_mock.enqueue = self.fake_enqueue
        queue_mock.enqueue_batch = self.fake_enqueue_batch
        sample_file = os.getcwd() + \
            "/tests/fixtures/sample_expire_list"
        import os
        with tempdir() as expired_tiles_location:
            expected_file = os.path.join(expired_tiles_location,
                                         'expire_list.txt')
            shutil.copy2(sample_file, expected_file)
            cfg_mock.intersect_expired_tiles_location = expired_tiles_location
            cfg_mock.logconfig = None
            self.assertTrue(os.path.isfile(expected_file))
            tilequeue_intersect(cfg_mock, periperals_mock)
            self.assertFalse(os.path.isfile(expected_file))

    def test_tilequeue_intersect_does_not_enqueue_coords(self):
        from mock import MagicMock
        from tilequeue.command import tilequeue_intersect
        from ModestMaps.Core import Coordinate
        from tilequeue.tile import serialize_coord
        cfg_mock = MagicMock()
        cfg_mock.queue_type = 'sqs'
        periperals_mock = MagicMock()
        c0 = Coordinate(row=0, column=0, zoom=0)
        c1 = Coordinate(row=1, column=1, zoom=1)
        periperals_mock.redis_cache_index = MagicMock(
            intersect=lambda x, y: ([]))
        queue_mock = MagicMock()
        periperals_mock.queue = queue_mock
        queue_mock.enqueue = self.fake_enqueue
        queue_mock.enqueue_batch = self.fake_enqueue_batch
        import os
        with tempdir() as expired_tiles_location:
            expected_file = os.path.join(expired_tiles_location,
                                         'expire_list.txt')
            with open(expected_file, "w+") as fp:
                fp.write(serialize_coord(c0) + "\n" + serialize_coord(c1))
            cfg_mock.intersect_expired_tiles_location = expired_tiles_location
            cfg_mock.logconfig = None
            tilequeue_intersect(cfg_mock, periperals_mock)
        self.assertNotIn(c0, self.enqueued_list)
        self.assertNotIn(c1, self.enqueued_list)

    def test_tilequeue_intersect_enqueues_coords(self):
        from mock import MagicMock
        from tilequeue.command import tilequeue_intersect
        from ModestMaps.Core import Coordinate
        from tilequeue.tile import serialize_coord
        from tilequeue.tile import coord_marshall_int
        cfg_mock = MagicMock()
        cfg_mock.queue_type = 'sqs'
        periperals_mock = MagicMock()
        c0 = Coordinate(row=0, column=0, zoom=0)
        c1 = Coordinate(row=1, column=1, zoom=1)
        coords = (c0, c1)
        periperals_mock.redis_cache_index = MagicMock(
            fetch_tiles_of_interest=lambda: set(
                map(coord_marshall_int, coords)))
        queue_mock = MagicMock()
        periperals_mock.queue = queue_mock
        queue_mock.enqueue = self.fake_enqueue
        queue_mock.enqueue_batch = self.fake_enqueue_batch
        import os
        with tempdir() as expired_tiles_location:
            expected_file = os.path.join(expired_tiles_location,
                                         'expire_list.txt')
            with open(expected_file, "w+") as fp:
                fp.write('\n'.join(map(serialize_coord, coords)))
            cfg_mock.intersect_expired_tiles_location = expired_tiles_location
            cfg_mock.logconfig = None
            tilequeue_intersect(cfg_mock, periperals_mock)
        self.assertIn(c0, self.enqueued_list)
        self.assertIn(c1, self.enqueued_list)

    def test_tilequeue_explode_and_intersect(self):
        from tilequeue.command import explode_and_intersect
        from tilequeue.tile import coord_marshall_int
        from tilequeue.tile import coord_unmarshall_int
        from ModestMaps.Core import Coordinate
        sample_coord = Coordinate(zoom=14, column=250, row=250)
        sample_coord_int = coord_marshall_int(sample_coord)
        tiles_of_interest = [sample_coord_int]
        for i in (10, 11, 12, 13):
            coord = sample_coord.zoomTo(i)
            coord_int = coord_marshall_int(coord)
            tiles_of_interest.append(coord_int)
        exploded = explode_and_intersect([sample_coord_int], tiles_of_interest,
                                         until=11)
        coord_ints = list(exploded)
        for coord_int in coord_ints:
            coord = coord_unmarshall_int(coord_int)
            self.failUnless(coord.zoom > 10)

        self.assertEqual(4, len(coord_ints))
