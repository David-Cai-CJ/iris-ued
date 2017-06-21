"""
Control bar for all Iris's controls

"""
from collections import Iterable
from contextlib import suppress
from pyqtgraph import QtGui, QtCore
from skued.baseline import ALL_COMPLEX_WAV, ALL_FIRST_STAGE

from pywt import Modes

class ControlBar(QtGui.QWidget):
    
    raw_data_request = QtCore.pyqtSignal(int, int)  # timedelay index, scan
    averaged_data_request = QtCore.pyqtSignal(int)  # timedelay index

    process_dataset = QtCore.pyqtSignal()
    promote_to_powder = QtCore.pyqtSignal()
    recompute_angular_average = QtCore.pyqtSignal()

    enable_peak_dynamics = QtCore.pyqtSignal(bool)
    baseline_removed = QtCore.pyqtSignal(bool)
    baseline_computation_parameters = QtCore.pyqtSignal(dict)
    time_zero_shift = QtCore.pyqtSignal(float)
    notes_updated = QtCore.pyqtSignal(str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.raw_dataset_controls = RawDatasetControl(parent = self)
        self.raw_dataset_controls.timedelay_widget.valueChanged.connect(self.request_raw_data)
        self.raw_dataset_controls.scan_widget.valueChanged.connect(self.request_raw_data)
        self.raw_dataset_controls.process_btn.clicked.connect(lambda x: self.process_dataset.emit())

        self.diffraction_dataset_controls = DiffractionDatasetControl(parent = self)
        self.diffraction_dataset_controls.timedelay_widget.valueChanged.connect(self.averaged_data_request)
        self.diffraction_dataset_controls.show_pd_btn.toggled.connect(self.enable_peak_dynamics)
        self.diffraction_dataset_controls.promote_to_powder_btn.clicked.connect(lambda x: self.promote_to_powder.emit())
        self.diffraction_dataset_controls.time_zero_shift_widget.valueChanged.connect(self.time_zero_shift)

        self.powder_diffraction_dataset_controls = PowderDiffractionDatasetControl(parent = self)
        self.powder_diffraction_dataset_controls.compute_baseline_btn.clicked.connect(self.request_baseline_computation)
        self.powder_diffraction_dataset_controls.baseline_removed_btn.toggled.connect(self.baseline_removed)
        self.powder_diffraction_dataset_controls.recompute_angular_average_btn.clicked.connect(self.recompute_angular_average.emit)

        self.metadata_widget = MetadataWidget(parent = self)

        self.notes_editor = NotesEditor(parent = self)
        self.notes_editor.notes_updated.connect(self.notes_updated)

        self.stack = QtGui.QTabWidget(parent = self)
        self.stack.addTab(self.metadata_widget, 'Dataset metadata')
        self.stack.addTab(self.notes_editor, 'Dataset notes')

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.raw_dataset_controls)
        layout.addWidget(self.diffraction_dataset_controls)
        layout.addWidget(self.powder_diffraction_dataset_controls)
        layout.addWidget(self.stack)
        self.setLayout(layout)

        for frame in (self.raw_dataset_controls, self.diffraction_dataset_controls, self.powder_diffraction_dataset_controls):
            frame.setFrameShadow(QtGui.QFrame.Sunken)
            frame.setFrameShape(QtGui.QFrame.Panel)

        self.setMaximumWidth(self.notes_editor.maximumWidth())
    
    @QtCore.pyqtSlot(dict)
    def update_raw_dataset_metadata(self, metadata):
        self.raw_dataset_controls.update_dataset_metadata(metadata)
    
    @QtCore.pyqtSlot(dict)
    def update_dataset_metadata(self, metadata):
        self.diffraction_dataset_controls.update_dataset_metadata(metadata)
        self.notes_editor.editor.setPlainText(metadata.pop('notes', 'No notes available'))
        self.metadata_widget.set_metadata(metadata)

    @QtCore.pyqtSlot(int)
    def update_processing_progress(self, value):
        self.raw_dataset_controls.processing_progress_bar.setValue(value)
    
    @QtCore.pyqtSlot(int)
    def update_powder_promotion_progress(self, value):
        self.diffraction_dataset_controls.promote_to_powder_progress.setValue(value)

    @QtCore.pyqtSlot(int)
    def update_angular_average_progress(self, value):
        self.powder_diffraction_dataset_controls.angular_average_progress.setValue(value)

    @QtCore.pyqtSlot(int)
    def request_raw_data(self, wtv):
        self.raw_data_request.emit(self.raw_dataset_controls.timedelay_widget.value(), 
                                   self.raw_dataset_controls.scan_widget.value() + 1) #scans are numbered starting at 1
    
    @QtCore.pyqtSlot()
    def request_baseline_computation(self):
        self.baseline_computation_parameters.emit(self.powder_diffraction_dataset_controls.baseline_parameters())
    
    @QtCore.pyqtSlot(bool)
    def enable_raw_dataset_controls(self, enable):
        self.raw_dataset_controls.setEnabled(enable)
    
    @QtCore.pyqtSlot(bool)
    def enable_diffraction_dataset_controls(self, enable):
        self.diffraction_dataset_controls.setEnabled(enable)
        self.stack.setEnabled(enable)
    
    @QtCore.pyqtSlot(bool)
    def enable_powder_diffraction_dataset_controls(self, enable):
        self.powder_diffraction_dataset_controls.setEnabled(enable)
        self.notes_editor.setEnabled(enable)
        self.metadata_widget.setEnabled(enable)

class RawDatasetControl(QtGui.QFrame):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        #############################
        # Navigating through raw data
        self.td_label = QtGui.QLabel('Time-delay: ')
        self.td_label.setAlignment(QtCore.Qt.AlignCenter)
        self.timedelay_widget = QtGui.QSlider(QtCore.Qt.Horizontal, parent = self)
        self.timedelay_widget.setMinimum(0)
        self.timedelay_widget.setTracking(False)
        self.timedelay_widget.setTickPosition(QtGui.QSlider.TicksBelow)
        self.timedelay_widget.setTickInterval(1)
        self.timedelay_widget.sliderMoved.connect(
            lambda pos: self.td_label.setText('Time-delay: {:.3f}ps'.format(self.time_points[pos])))

        self.s_label = QtGui.QLabel('Scan: ')
        self.s_label.setAlignment(QtCore.Qt.AlignCenter)
        self.scan_widget = QtGui.QSlider(QtCore.Qt.Horizontal, parent = self)
        self.scan_widget.setMinimum(0)
        self.scan_widget.setTracking(False)
        self.scan_widget.setTickPosition(QtGui.QSlider.TicksBelow)
        self.scan_widget.setTickInterval(1)
        self.scan_widget.sliderMoved.connect(
            lambda pos: self.s_label.setText('Scan: {:d}'.format(self.nscans[pos])))

        prev_timedelay_btn = QtGui.QPushButton('<', self)
        prev_timedelay_btn.clicked.connect(self.goto_prev_timedelay)

        next_timedelay_btn = QtGui.QPushButton('>', self)
        next_timedelay_btn.clicked.connect(self.goto_next_timedelay)

        prev_scan_btn = QtGui.QPushButton('<', self)
        prev_scan_btn.clicked.connect(self.goto_prev_scan)

        next_scan_btn = QtGui.QPushButton('>', self)
        next_scan_btn.clicked.connect(self.goto_next_scan)

        time_layout = QtGui.QHBoxLayout()
        time_layout.addWidget(self.td_label)
        time_layout.addWidget(self.timedelay_widget)
        time_layout.addWidget(prev_timedelay_btn)
        time_layout.addWidget(next_timedelay_btn)

        scan_layout = QtGui.QHBoxLayout()
        scan_layout.addWidget(self.s_label)
        scan_layout.addWidget(self.scan_widget)
        scan_layout.addWidget(prev_scan_btn)
        scan_layout.addWidget(next_scan_btn)

        sliders = QtGui.QHBoxLayout()
        sliders.addLayout(time_layout)
        sliders.addLayout(scan_layout)

        self.process_btn = QtGui.QPushButton('Processing')
        self.processing_progress_bar = QtGui.QProgressBar(parent = self)

        processing = QtGui.QHBoxLayout()
        processing.addWidget(self.process_btn)
        processing.addWidget(self.processing_progress_bar)

        title = QtGui.QLabel('<h2>Raw dataset controls<\h2>')
        title.setTextFormat(QtCore.Qt.RichText)
        title.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(sliders)
        layout.addLayout(processing)
        self.setLayout(layout)
        self.resize(self.minimumSize())
    
    def update_dataset_metadata(self, metadata):
        self.time_points = metadata.get('time_points')
        self.nscans = metadata.get('nscans')

        self.timedelay_widget.setRange(0, len(self.time_points) - 1)
        self.scan_widget.setRange(0, len(self.nscans) - 1)
        self.timedelay_widget.triggerAction(5)
        self.timedelay_widget.sliderMoved.emit(0)
        self.scan_widget.triggerAction(5)
        self.scan_widget.sliderMoved.emit(0)

    @QtCore.pyqtSlot()
    def goto_prev_timedelay(self):
        self.timedelay_widget.setSliderDown(True)
        self.timedelay_widget.triggerAction(2)
        self.timedelay_widget.setSliderDown(False)
    
    @QtCore.pyqtSlot()
    def goto_next_timedelay(self):
        self.timedelay_widget.setSliderDown(True)
        self.timedelay_widget.triggerAction(1)
        self.timedelay_widget.setSliderDown(False)

    @QtCore.pyqtSlot()
    def goto_prev_scan(self):
        self.scan_widget.setSliderDown(True)
        self.scan_widget.triggerAction(2)
        self.scan_widget.setSliderDown(False)
    
    @QtCore.pyqtSlot()
    def goto_next_scan(self):
        self.scan_widget.setSliderDown(True)
        self.scan_widget.triggerAction(1)
        self.scan_widget.setSliderDown(False)

class DiffractionDatasetControl(QtGui.QFrame):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        ################################
        # Diffraction dataset navigation
        self.td_label = QtGui.QLabel('Time-delay: ')
        self.td_label.setAlignment(QtCore.Qt.AlignCenter)
        self.timedelay_widget = QtGui.QSlider(QtCore.Qt.Horizontal, parent = self)
        self.timedelay_widget.setMinimum(0)
        self.timedelay_widget.setTracking(False)
        self.timedelay_widget.setTickPosition(QtGui.QSlider.TicksBelow)
        self.timedelay_widget.setTickInterval(1)
        self.timedelay_widget.sliderMoved.connect(
            lambda pos: self.td_label.setText('Time-delay: {:.3f}ps'.format(self.time_points[pos])))

        # Time-zero shift control
        self.time_zero_shift_widget = QtGui.QDoubleSpinBox(parent = self)
        self.time_zero_shift_widget.setRange(-100, 100)
        self.time_zero_shift_widget.setDecimals(3)
        self.time_zero_shift_widget.setSingleStep(0.5)
        self.time_zero_shift_widget.setSuffix(' ps')
        self.time_zero_shift_widget.setValue(0.0)

        prev_btn = QtGui.QPushButton('<', self)
        prev_btn.clicked.connect(self.goto_prev)

        next_btn = QtGui.QPushButton('>', self)
        next_btn.clicked.connect(self.goto_next)

        sliders = QtGui.QGridLayout()
        sliders.addWidget(self.td_label, 0, 0, 1, 1)
        sliders.addWidget(self.timedelay_widget, 0, 1, 1, 5)
        sliders.addWidget(prev_btn, 0, 6, 1, 1)
        sliders.addWidget(next_btn, 0, 7, 1, 1)

        ################################
        # Enable/disable time-series ROI
        self.show_pd_btn = QtGui.QPushButton('Show/hide peak dynamics', parent = self)
        self.show_pd_btn.setCheckable(True)
        self.show_pd_btn.setChecked(False)

        ################################
        # Promote DiffractionDataset to PowderDiffractionDataset
        self.promote_to_powder_btn = QtGui.QPushButton('To powder', parent = self)
        self.promote_to_powder_progress = QtGui.QProgressBar(parent = self)

        promote_layout = QtGui.QHBoxLayout()
        promote_layout.addWidget(self.promote_to_powder_btn)
        promote_layout.addWidget(self.promote_to_powder_progress)

        time_zero_shift_layout = QtGui.QFormLayout()
        time_zero_shift_layout.addRow('Time-zero shift: ', self.time_zero_shift_widget)

        title = QtGui.QLabel('<h2>Diffraction dataset controls<\h2>')
        title.setTextFormat(QtCore.Qt.RichText)
        title.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(sliders)
        layout.addLayout(time_zero_shift_layout)
        layout.addWidget(self.show_pd_btn)
        layout.addLayout(promote_layout)
        self.setLayout(layout)
        self.resize(self.minimumSize())
    
    def update_dataset_metadata(self, metadata):
        self.time_points = metadata.get('time_points')
        t0_shift = metadata.get('time_zero_shift')

        self.timedelay_widget.setRange(0, len(self.time_points) - 1)
        self.timedelay_widget.triggerAction(5) # SliderToMinimum
        self.timedelay_widget.sliderMoved.emit(0)

        self.time_zero_shift_widget.setValue(t0_shift)
    
    @QtCore.pyqtSlot()
    def goto_prev(self):
        self.timedelay_widget.setSliderDown(True)
        self.timedelay_widget.triggerAction(2)
        self.timedelay_widget.setSliderDown(False)
    
    @QtCore.pyqtSlot()
    def goto_next(self):
        self.timedelay_widget.setSliderDown(True)
        self.timedelay_widget.triggerAction(1)
        self.timedelay_widget.setSliderDown(False)

class PowderDiffractionDatasetControl(QtGui.QFrame):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.recompute_angular_average_btn = QtGui.QPushButton('Recompute angular average', parent = self)
        self.angular_average_progress = QtGui.QProgressBar(parent = self)

        angular_average_layout = QtGui.QHBoxLayout()
        angular_average_layout.addWidget(self.recompute_angular_average_btn)
        angular_average_layout.addWidget(self.angular_average_progress)

        ######################
        # baseline computation
        self.first_stage_cb = QtGui.QComboBox()
        self.first_stage_cb.addItems(ALL_FIRST_STAGE)
        if 'sym6' in ALL_FIRST_STAGE:
            self.first_stage_cb.setCurrentText('sym6')

        self.wavelet_cb = QtGui.QComboBox()
        self.wavelet_cb.addItems(ALL_COMPLEX_WAV)
        if 'qshift3' in ALL_COMPLEX_WAV:
            self.wavelet_cb.setCurrentText('qshift3')

        self.mode_cb = QtGui.QComboBox()
        self.mode_cb.addItems(Modes.modes)
        if 'smooth' in Modes.modes:
            self.mode_cb.setCurrentText('constant')
        
        self.max_iter_widget = QtGui.QSpinBox()
        self.max_iter_widget.setRange(0, 1000)
        self.max_iter_widget.setValue(100)

        self.compute_baseline_btn = QtGui.QPushButton('Compute baseline', parent = self)

        self.baseline_removed_btn = QtGui.QPushButton('Show baseline-removed', parent = self)
        self.baseline_removed_btn.setCheckable(True)
        self.baseline_removed_btn.setChecked(False)

        baseline_controls_col1 = QtGui.QFormLayout()
        baseline_controls_col1.addRow('First stage wavelet: ', self.first_stage_cb)
        baseline_controls_col1.addRow('Dual-tree wavelet: ', self.wavelet_cb)
        baseline_controls_col1.addRow(self.compute_baseline_btn)

        baseline_controls_col2 = QtGui.QFormLayout()
        baseline_controls_col2.addRow('Extensions mode: ', self.mode_cb)
        baseline_controls_col2.addRow('Iterations: ', self.max_iter_widget)
        baseline_controls_col2.addRow(self.baseline_removed_btn)

        baseline_controls = QtGui.QHBoxLayout()
        baseline_controls.addLayout(baseline_controls_col1)
        baseline_controls.addLayout(baseline_controls_col2)

        # TODO: add callback and progressbar for computing the baseline?

        title = QtGui.QLabel('<h2>Powder dataset controls<\h2>')
        title.setTextFormat(QtCore.Qt.RichText)
        title.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(baseline_controls)
        layout.addLayout(angular_average_layout)
        self.setLayout(layout)
        self.resize(self.minimumSize())
    
    def baseline_parameters(self):
        """ Returns a dictionary of baseline-computation parameters """
        return {'first_stage': self.first_stage_cb.currentText(),
                'wavelet': self.wavelet_cb.currentText(),
                'mode': self.mode_cb.currentText(),
                'max_iter': self.max_iter_widget.value(),
                'level': None,
                'callback': lambda : self.baseline_removed_btn.setChecked(True)}

class MetadataWidget(QtGui.QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        title = QtGui.QLabel('<h2>Dataset metadata<\h2>', parent = self)
        title.setTextFormat(QtCore.Qt.RichText)
        title.setAlignment(QtCore.Qt.AlignCenter)

        self.table = QtGui.QTableWidget(parent = self)
        self.table.setColumnCount(2)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)   #no edit triggers, see QAbstractItemViews

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.resize(self.minimumSize())
    
    @QtCore.pyqtSlot(dict)
    def set_metadata(self, metadata):
        self.table.clear()
        self.table.setRowCount(len(metadata) - 1 if 'notes' in metadata else len(metadata))
        for row, (key, value) in enumerate(metadata.items()):
            if isinstance(value, Iterable) and key not in ('acquisition_date', 'sample_type'):
                if len(value) > 4:
                    key += ' (length)'
                    value = len(tuple(value))

            self.table.setItem(row, 0, QtGui.QTableWidgetItem(key))
            self.table.setItem(row, 1, QtGui.QTableWidgetItem(str(value)))
        
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)


class NotesEditor(QtGui.QFrame):

    notes_updated = QtCore.pyqtSignal(str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        title = QtGui.QLabel('<h2>Dataset notes and remarks<\h2>', parent = self)
        title.setTextFormat(QtCore.Qt.RichText)
        title.setAlignment(QtCore.Qt.AlignCenter)

        update_btn = QtGui.QPushButton('Update notes', self)
        update_btn.clicked.connect(self.update_notes)

        self.editor = QtGui.QTextEdit(parent = self)

        # Set editor size such that 60 characters will fit
        font_info = QtGui.QFontInfo(self.editor.currentFont())
        self.editor.setMaximumWidth(60 * font_info.pixelSize())
        self.editor.setLineWrapMode(QtGui.QTextEdit.WidgetWidth)  # widget width

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.editor)
        layout.addWidget(update_btn)
        self.setLayout(layout)
        self.setMaximumWidth(self.editor.maximumWidth())
        self.resize(self.minimumSize())
    
    @QtCore.pyqtSlot()
    def update_notes(self):
        self.notes_updated.emit(self.editor.toPlainText())