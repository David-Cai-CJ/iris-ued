
import unittest
from os.path import dirname, join

import numpy as np

from .. import imibread, mibheader, mibread

class TestMIBRead(unittest.TestCase):
    
    TEST_FILENAME       = join(dirname(__file__), 'test.mib')
    TEST_MULTI_FILENAME = join(dirname(__file__), 'test_multi.mib')

    def test_header(self):
        """ Test that header parsing of MIB files is working as intended """
        header = mibheader(self.TEST_FILENAME)

        true_value = {'ID'       :'MQ1',
                      'seq_num'  : 1,
                      'offset'   : 384,
                      'nchips'   : 1,
                      'shape'   : ( 256, 256 ),
                      'dtype'    : np.dtype('>u2')}

        self.assertDictEqual(header, true_value)
    
    def test_imibread(self):
        """ Test the generator version of mibread() """
        gen = imibread(self.TEST_FILENAME)
        arr = next(gen)
        self.assertEqual(arr.shape, (256, 256))
        self.assertEqual(arr.dtype,  np.dtype('>u2'))

    def test_mibread(self):
        """ Test that the array extracted from a test MIB files has the
        expected attributes """
        arr = mibread(self.TEST_FILENAME)
        self.assertEqual(arr.shape, (256, 256))
        self.assertEqual(arr.dtype, np.dtype('>u2'))
    
    def test_mibread_multi(self):
        """ Test that the array extracted from a test MIB files containing
        multi images has the expected attributes """
        arr = mibread(self.TEST_MULTI_FILENAME)
        self.assertEqual(arr.shape, (256, 256, 500))



if __name__ == '__main__':
    unittest.main()
