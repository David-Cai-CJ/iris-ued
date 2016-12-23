
from ..utils import angular_average, shift, find_center, _find_center_full
import numpy as n
from scipy.ndimage import gaussian_filter
import unittest

class TestShift(unittest.TestCase):
    
    def test_no_shift(self):
        """ Shift by 0 pixels """
        array = n.ones(shape = (256, 256), dtype = n.float)
        self.assertTrue(n.allclose(array, shift(array, 0, 0)))
    
    def test_no_shift_in_each_direction(self):
        array = n.ones(shape = (256, 256), dtype = n.float)
        self.assertEqual(array.shape, shift(array, 0, -1).shape)
        self.assertEqual(array.shape, shift(array, 1, 0).shape)
    
    def test_output_format(self):
        array = n.ones(shape = (256, 256), dtype = n.float)
        shifted = shift(array, 1, 23)
        self.assertEqual(array.shape, shifted.shape)
        self.assertEqual(array.dtype, shifted.dtype)
    
    def test_shift_out_of_bounds(self):
        array = n.ones(shape = (256, 256), dtype = n.float)
        shifted_x = shift(array, 300, 0)
        self.assertTrue(shifted_x.mask.sum() == array.size)

        shifted_y = shift(array, 0, -451)
        self.assertTrue(shifted_y.mask.sum() == array.size)

class TestAngularAverage(unittest.TestCase):

    def test_trivial_array(self):
        image = n.zeros(shape = (256, 256), dtype = n.float)
        center = (image.shape[0]/2, image.shape[1]/2)
        s, i, e = angular_average(image, center, (0,0,0,0))
        self.assertTrue(i.sum() == 0)
        self.assertTrue(len(s) == len(i) == len(e))
    
    def test_ring_no_beamblock(self):
        image = n.zeros(shape = (256, 256), dtype = n.float)
        xc, yc = (128, 128)
        extent = n.arange(0, image.shape[0])
        xx, yy = n.meshgrid(extent, extent)
        rr = n.sqrt((xx - xc)**2 + (yy - yc)**2)
        image[n.logical_and(24 < rr,rr < 26)] = 1

        s, i, e = angular_average(image, (xc, yc), (0,0,0,0))
        self.assertTrue(i.max() == image.max())
    
    def test_ring_with_beamblock(self):
        image = n.zeros(shape = (256, 256), dtype = n.float)
        xc, yc = (128, 128)
        extent = n.arange(0, image.shape[0])
        xx, yy = n.meshgrid(extent, extent)
        rr = n.sqrt((xx - xc)**2 + (yy - yc)**2)
        image[n.logical_and(24 < rr,rr < 26)] = 1
        beamblock_rect = (120, 136, 120, 136)

        s, i, e = angular_average(image, (xc, yc), beamblock_rect)
        self.assertTrue(len(i) + 2 == 120)  # angular_average omits the largest and smallest radii

class TestFindCenter(unittest.TestCase):

    @unittest.skip('Not useful right now')
    def test_trivial_array(self):
        image = n.zeros(shape = (512, 512), dtype = n.float)
        xc, yc = find_center(image, guess_center = (256, 256), radius = 15, window_size = 10)
        self.assertTrue(0 <= xc < 512)
        self.assertTrue(0 <= yc < 512)
    
    def test_find_center_full(self):
        """ Finding the center on an image, without reducing the image size """
        image = n.zeros(shape = (512, 512), dtype = n.float)
        xc, yc = (258, 254)
        extent = n.arange(0, image.shape[0])
        xx, yy = n.meshgrid(extent, extent)
        rr = n.sqrt((xx - xc)**2 + (yy - yc)**2)
        image[rr == 50] = 10
        image = gaussian_filter(image, 3)

        corr_x, corr_y = _find_center_full(image, guess_center = (255, 251), radius = 50, window_size = 10)
        self.assertEqual(xc, corr_x)
        self.assertEqual(yc, corr_y)
    
    def test_perfect_guess(self):
        """ Using a perfect center guess """
        image = n.zeros(shape = (256, 256), dtype = n.float)
        xc, yc = (132, 155)
        extent = n.arange(0, image.shape[0])
        xx, yy = n.meshgrid(extent, extent)
        rr = n.sqrt((xx - xc)**2 + (yy - yc)**2)
        image[n.logical_and(24.5 < rr,rr < 25.5)] = 10
        image = gaussian_filter(image, 3)

        corr_x, corr_y = find_center(image, guess_center = (xc, yc), radius = 25)
        self.assertEqual(xc, corr_x)
        self.assertEqual(yc, corr_y)
    
    def test_ring(self):
        """ Finding the center on an image, reducing the image size """
        image = n.zeros(shape = (2048, 2048), dtype = n.float)
        xc, yc = (1024, 1024)
        extent = n.arange(0, image.shape[0])
        xx, yy = n.meshgrid(extent, extent)
        rr = n.sqrt((xx - xc)**2 + (yy - yc)**2)
        image[rr == 50] = 10
        image = gaussian_filter(image, 3)

        corr_x, corr_y = find_center(image, guess_center = (1023, 1027), radius = 50)
        self.assertEqual(xc, corr_x)
        self.assertEqual(yc, corr_y)

if __name__ == '__main__':
    unittest.main()