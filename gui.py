# -*- coding: utf-8 -*-

import sys
import os.path
import numpy as n
from PIL import Image

#Core functions
import core as fc

#plotting backends
from matplotlib.backends import qt_compat
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.backends.backend_qt4agg as qt4agg
from matplotlib.figure import Figure
use_pyside = qt_compat.QT_API == qt_compat.QT_API_PYSIDE

#GUI backends
if use_pyside:
    from PySide import QtGui, QtCore
else:
    from PyQt4 import QtGui, QtCore

# -----------------------------------------------------------------------------
#           IMAGE VIEWER CLASSES AND FUNCTIONS
# -----------------------------------------------------------------------------
    
def generateCircle(xc, yc, radius):
    """
    Generates scatter value for a cicle centered at [xc,yc] of radius 'radius'.
    """
    xvals = xc+ radius*n.cos(n.linspace(0,2*n.pi,100))
    yvals = yc+ radius*n.sin(n.linspace(0,2*n.pi,100))
    return [xvals,yvals]

class workThread(QtCore.QThread):
    """
    Object taking care of computations
    """
    def __init__(self, function, *args, **kwargs):
        QtCore.QThread.__init__(self)
        self.function = function
        self.args = args
        self.kwargs = kwargs
    
    def __del__(self):
        self.wait()
    
    def compute(self):
        return self.function(*self.args, **self.kwargs)

class ImageViewer(FigureCanvas):
    """
    Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.).
    This object displays any plot we want: TIFF image, radial-averaged pattern, etc.
    
    Non-plotting Attributes
    ----------------------- 
    last_click_position : list, shape (2,)
        [x,y] coordinates of the last click. Clicking outside the data of the ImageViewer set last_click = [0,0]
    
    """

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        
        #Non-plotting attributes
        self.parent = parent
        self.last_click_position = [0,0]
        self.guess_center = None
        self.guess_radius = None
        
        #plot setup
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.axes.hold(True)

        self.initialFigure()

        #
        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                                   QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        
        #Set toolbar
        
        #connect clicking events
        self.mpl_connect('button_press_event', self.click)
    
    def click(self, event):
        """
        Saves the position of the last click on the canvas
        """
        if event.xdata == None or event.ydata == None:
            self.last_click_position = [0,0]
        else:
            self.last_click_position = [event.xdata, event.ydata]
        
        if self.parent.state == 'data loaded':
            self.parent.guess_center = n.asarray(self.last_click_position)
            self.displayImage(self.parent.image, guess = self.parent.guess_center)
            self.parent.state = 'center guessed'
            
        elif self.parent.state == 'center guessed':
            ring_position = n.asarray(self.last_click_position)
            self.parent.guess_radius = n.linalg.norm(self.parent.guess_center - ring_position)           
            self.parent.state = 'radius guessed'
            
        elif self.parent.state == 'radial averaged':
            if len(self.parent.background_guesses) < 5:
                self.parent.background_guesses.append(self.last_click_position)
                print 'Background guess #' + str(len(self.parent.background_guesses))
                
            elif len(self.parent.background_guesses) >= 5:
                self.parent.background_guesses.append(self.last_click_position)
                print 'Background guess #' + str(len(self.parent.background_guesses))
                self.parent.state = 'background guessed'
                
        #Update message box
        self.parent.update()

    def initialFigure(self):
        """ Plots a placeholder image until an image file is selected """
        missing_image = n.zeros(shape = (1024,1024), dtype = n.uint8)
        self.axes.cla()     #Clear axes
        self.axes.imshow(missing_image)
 
    def displayImage(self, image, circle = None, guess = None):
        """ 
        This method displays a raw TIFF image from the instrument. Optional arguments can be used to overlay a circle.
        
        Parameters
        ----------
        filename : string
            Filename of the image to be displayed.
        cicle : list, optional, shape (2,)
            List of 2 ndarrays that decribe scatter points of a circle
        guess : list, optional,
            x and y coordinates of center guess
        """
        if image is None:
            self.initialFigure()
        else:
            self.axes.cla()     #Clear axes
            self.axes.imshow(image)
            if guess != None:
                self.axes.scatter(guess[0],guess[1])
                self.axes.set_xlim(0, image.shape[0])
                self.axes.set_ylim(image.shape[1],0)
            if circle != None:  #Overlay circle if provided
                xvals, yvals = circle
                self.axes.scatter(xvals, yvals)
                #Restrict view to the plotted circle (to better evaluate the fit)
                self.axes.set_xlim(xvals.min() - 10, xvals.max() + 10)
                self.axes.set_ylim(yvals.max() + 10, yvals.min() - 10)
            
            self.axes.set_title('Raw TIFF image')
            self.draw()
    
    def displayRadialPattern(self, *args):
        """
        Plots one or more diffraction patterns.
        
        Parameters
        ----------
        *args : lists of the form [s, pattern, name]
        """
        self.axes.cla()       

        for l in args:
            s, pattern, name = l       
            self.axes.plot(s, pattern, '.', label = name)
        
        #Plot parameters
        self.axes.set_xlim(args[0][0].min(), args[0][0].max())  #Set xlim and ylim on the first pattern args[0].
        self.axes.set_ylim(args[0][1].min(), args[0][1].max())
        self.axes.set_aspect('auto')
        self.axes.set_title('Diffraction pattern')
        self.axes.set_xlabel('radius (px)')
        self.axes.set_ylabel('Intensity')
        self.axes.legend( loc = 'upper right', numpoints = 1)
        self.draw()
            
# -----------------------------------------------------------------------------
#           MAIN WINDOW CLASS
# -----------------------------------------------------------------------------
    
class UEDpowder(QtGui.QMainWindow):
    """
    Main application window
    
    Attributes
    ----------
    image_center : list, shape (2,)
        [x,y]-coordinates of the image center
    image : ndarray, shape (N,N)
        ndarray corresponding to the data TIFF file
    radial_average = [r,i, name] : list, shape (3,)
        list of 2 ndarrays, shape (M,). r is the radius array, and i is the radially-averaged intensity. 'name' is a string used to make the plot legend.
    state : string
        Value describing in what state the software is. Possible values are:
            state in ['initial','data loaded', 'center guessed', 'radius guessed', 'center found', 'radial averaged', 'background guessed', 'background substracted']
    """
    def __init__(self):
        
        #Attributes
        self.image_center = list()
        self.image = None
        self.substrate_image = None
        self.raw_radial_average = list()    #Before inelastic background substraction
        self.radial_average = list()        #After inelastic background substraction
        self.background_guesses = list()
        self._state = 'initial'
        
        #Methods
        super(UEDpowder, self).__init__()     #inherit from the constructor of QMainWindow        
        self.initUI()
    
    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self, value):
        print 'Old state: ' + self._state
        self._state = value
        print 'New state: ' + self._state
        self.updateButtonAvailability()     #Update which buttons are valid
    
    def updateButtonAvailability(self):
        """
        """
        #Create list of buttons to be disabled and enables
        availableButtons = list()
        unavailableButtons = list()
        
        if self.state == 'initial':
            availableButtons = [self.imageLocatorBtn]
            unavailableButtons = [self.executeCenterBtn, self.executeInelasticBtn, self.acceptBtn, self.rejectBtn]
        elif self.state == 'data loaded':
            availableButtons = [self.imageLocatorBtn]
            unavailableButtons = [self.executeCenterBtn, self.executeInelasticBtn, self.acceptBtn, self.rejectBtn]
        elif self.state == 'radius guessed':
            availableButtons = [self.imageLocatorBtn, self.executeCenterBtn]
            unavailableButtons = [self.executeInelasticBtn, self.acceptBtn, self.rejectBtn]
        elif self.state == 'center found':
            availableButtons = [self.imageLocatorBtn, self.acceptBtn, self.rejectBtn]
            unavailableButtons = [self.executeCenterBtn, self.executeInelasticBtn]
        elif self.state == 'radial averaged':
            availableButtons = [self.imageLocatorBtn]
            unavailableButtons = [self.acceptBtn, self.rejectBtn, self.executeCenterBtn, self.executeInelasticBtn]  
        elif self.state == 'background guessed':
            availableButtons = [self.imageLocatorBtn, self.executeInelasticBtn]
            unavailableButtons = [self.acceptBtn, self.rejectBtn, self.executeCenterBtn]
        elif self.state == 'background substracted':
            availableButtons = [self.imageLocatorBtn, self.acceptBtn, self.rejectBtn]
            unavailableButtons = [self.executeInelasticBtn, self.executeCenterBtn]
        
        #Act!
        for btn in availableButtons:
            btn.setEnabled(True)
        for btn in unavailableButtons:
            btn.setEnabled(False)
        
    def initUI(self):
        
        # ---------------------------------------------------------------------
        #       WIDGETS
        # ---------------------------------------------------------------------
        
        self.statusBar()    #Top status bar
        
        #Set up state buttons
        self.acceptBtn = QtGui.QPushButton('Accept', self)
        self.acceptBtn.setIcon(QtGui.QIcon('images\checkmark.png'))
        
        self.rejectBtn = QtGui.QPushButton('Reject', self)
        self.rejectBtn.setIcon(QtGui.QIcon('images\cancel.png'))
        
        self.turboBtn = QtGui.QPushButton('Turbo Mode', self)
        self.turboBtn.setIcon(QtGui.QIcon('images\close.png'))
        self.turboBtn.setCheckable(True)
        
        #Set up message boxes
        self.initial_message = QtGui.QLabel('Step 1: select TIFF image.')
        self.center_message = QtGui.QLabel('')
        
        #For initial state box
        initial_box = QtGui.QVBoxLayout()
        initial_box.addWidget(self.initial_message)
        self.imageLocatorBtn = QtGui.QPushButton('Locate diffraction image', self)
        self.imageLocatorBtn.setIcon(QtGui.QIcon('images\locator.png'))
        initial_box.addWidget(self.imageLocatorBtn)
        
        #For image center select box
        center_box = QtGui.QVBoxLayout()
        center_box.addWidget(QtGui.QLabel('Step 2: find the center of the image'))
        self.executeCenterBtn = QtGui.QPushButton('Find center', self)
        self.executeCenterBtn.setIcon(QtGui.QIcon('images\science.png'))
        center_box.addWidget(self.executeCenterBtn)
        
        #For the inelastic scattering correction
        inelastic_box = QtGui.QVBoxLayout()
        inelastic_box.addWidget(QtGui.QLabel('Step 3: Remove inelastic scattering background and substrate effects'))
        self.executeInelasticBtn = QtGui.QPushButton('Execute', self)
        self.executeInelasticBtn.setIcon(QtGui.QIcon('images\science.png'))
        inelastic_box.addWidget(self.executeInelasticBtn)
        
        #For instructions and printing
        instruction_box = QtGui.QVBoxLayout()
        instruction_box.addWidget(QtGui.QLabel('Instructions:'))
        self.instructions = QtGui.QListWidget()
        instruction_box.addWidget(self.instructions)

        #Set up ImageViewer
        self.image_viewer = ImageViewer(parent = self)
        self.file_dialog = QtGui.QFileDialog()
        
        # ---------------------------------------------------------------------
        #       SIGNALS
        # ---------------------------------------------------------------------
        
        #Connect the image locator button to the file dialog
        self.imageLocatorBtn.clicked.connect(self.imageLocator)
        self.acceptBtn.clicked.connect(self.acceptState)
        self.rejectBtn.clicked.connect(self.rejectState)
        self.executeCenterBtn.clicked.connect(self.executeStateOperation)
        self.executeInelasticBtn.clicked.connect(self.executeStateOperation)
        
        # ---------------------------------------------------------------------
        #       LAYOUT
        # ---------------------------------------------------------------------
        
        #Accept - reject buttons combo
        state_controls = QtGui.QHBoxLayout()
        state_controls.addWidget(self.acceptBtn)
        state_controls.addWidget(self.rejectBtn)
        state_controls.addWidget(self.turboBtn)
        
        # State boxes ---------------------------------------------------------
        state_boxes = QtGui.QVBoxLayout()
        state_boxes.addLayout(initial_box)
        state_boxes.addLayout(center_box)
        state_boxes.addLayout(inelastic_box)
        state_boxes.addLayout(instruction_box)
        state_boxes.addLayout(state_controls)
        
        #Image viewer pane ----------------------------------------------------
        right_pane = QtGui.QVBoxLayout()
        right_pane.addWidget(self.image_viewer)
        
        #Master Layout --------------------------------------------------------
        grid = QtGui.QHBoxLayout()
        grid.addLayout(state_boxes)
        grid.addLayout(right_pane)
        
        #Set master layout  ---------------------------------------------------
        self.central_widget = QtGui.QWidget()
        self.central_widget.setLayout(grid)
        self.setCentralWidget(self.central_widget)
        
        #Window settings ------------------------------------------------------
        self.setGeometry(600, 600, 350, 300)
        self.setWindowTitle('UED Powder Analysis Software')
        self.centerWindow()
        self.show()
        
    def imageLocator(self):
        """ File dialog that selects the TIFF image file to be processed. """
        filename = self.file_dialog.getOpenFileName(self, 'Open image', 'C:\\')
        self.loadImage(filename)
        self.image_viewer.displayImage(self.image)     #display raw image
        
    def acceptState(self):
        """ Master accept function that validates a state and proceeds to the next one. """
        
        if self.state == 'center found':
            self.raw_radial_average = fc.radialAverage(self.image, self.image_center)
            self.raw_radial_average.append('Raw radial average')
            self.image_viewer.displayRadialPattern(self.raw_radial_average)
            self.state = 'radial averaged'
        elif self.state == 'background substracted':
            pass
    
    def rejectState(self):
        """ Master reject function that invalidates a state and reverts to an appropriate state. """
        if self.state == 'center found':
            #Go back to the data loaded state and forget the guessed for the center and radius
            self.state = 'data loaded'
            self.image_viewer.guess_center, self.image_viewer.guess_radius = None, None
            self.image_viewer.displayImage(self.image)
        if self.state == 'background substracted':
            #Go back to choosing the guesses for the background
            self.image_viewer.displayRadialPattern(self.raw_radial_average)
            self.background_guesses = list() #Clear guesses
            self.state = 'radial averaged'

    def executeStateOperation(self):
        """ Placeholder function to confirm that computation may proceed in certain cases """
        if self.state == 'center guessed':        
           pass
        if self.state == 'radius guessed':
            #Compute center
            xg, yg = self.guess_center
            rg = self.guess_radius
            center = fc.fCenter(xg,yg,rg,self.image)
            
            #Save center and plot to confirm
            self.image_center = center[0:2]
            circle = generateCircle(center[0], center[1], center[2])
            self.state = 'center found'
            self.image_viewer.displayImage(self.image, circle)
        
        if self.state == 'background guessed':
            #Create guess data
            self.radial_average = fc.inelasticBGSubstract(self.raw_radial_average[0], self.raw_radial_average[1], self.background_guesses)
            self.state = 'background substracted'
            self.image_viewer.displayRadialPattern(self.raw_radial_average, self.radial_average)
            
    def centerWindow(self):
        """ Centers the window """
        qr = self.frameGeometry()
        cp = QtGui.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    def loadImage(self, filename):
        """ Loads an image (and the associated background image) and sets the first state. """
        #Load image
        self.image = n.array(Image.open(filename))        
        #Load substrate image
        substrate_filename = os.path.normpath(os.path.join(os.path.dirname(filename), 'subs.tif'))
        self.substrate_image = n.array(Image.open(substrate_filename))
        self.state = 'data loaded'
        
    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()
        
#Run
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    analysisWindow = UEDpowder()
    analysisWindow.showMaximized()
    sys.exit(app.exec_())
