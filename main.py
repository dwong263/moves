from array import *

import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

import scipy as sp
import scipy.stats

import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets, uic

import os
import sys

qtCreatorFile = "ui/moves.ui"
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MouseInteractorHighLightActor(vtk.vtkInteractorStyleTrackballCamera):

	def __init__(self,parent=None):
		self.AddObserver("LeftButtonPressEvent",self.SelectRegion)
		self.AddObserver("RightButtonPressEvent",self.DeselectRegion)

		self.SelectedRegions = []
		self.DeselectedRegions = []

	def SelectRegion(self,obj,event):
		clickPos = self.GetInteractor().GetEventPosition()

		picker = vtk.vtkPropPicker()
		picker.Pick(clickPos[0], clickPos[1], 0, self.GetDefaultRenderer())

		NewPickedActor = picker.GetActor()
		if NewPickedActor:
			
			try:
				self.SelectedRegions.remove(NewPickedActor)
			except Exception as e:
				print('  |', e, '... nothing removed.')

			NewPickedActor.GetProperty().SetColor(214.0/255.0, 39.0/255.0, 40.0/255.0)
			NewPickedActor.GetProperty().SetOpacity(0.6)

			self.SelectedRegions.append(NewPickedActor)

			try:
				self.DeselectedRegions.remove(NewPickedActor)
			except Exception as e:
				print('  |', e, '... nothing removed.')

			self.SelectedVolume()

		self.OnLeftButtonDown()
		return

	def DeselectRegion(self,obj,event):
		clickPos = self.GetInteractor().GetEventPosition()
		
		picker = vtk.vtkPropPicker()
		picker.Pick(clickPos[0], clickPos[1], 0, self.GetDefaultRenderer())

		NewPickedActor = picker.GetActor()
		if NewPickedActor:
			
			try:
				self.DeselectedRegions.remove(NewPickedActor)
			except Exception as e:
				print('  |', e, '... nothing removed.')

			NewPickedActor.GetProperty().SetColor(31.0/255.0, 119.0/255.0, 180.0/255.0)
			NewPickedActor.GetProperty().SetOpacity(0.6)

			self.DeselectedRegions.append(NewPickedActor)

			try:
				self.SelectedRegions.remove(NewPickedActor)
			except Exception as e:
				print('  |', e, '... nothing removed.')

			self.SelectedVolume()

		self.OnRightButtonDown()
		return

	def SelectedVolume(self):
		vol = 0
		sa = 0
		for actor in self.SelectedRegions:
			data = vtk.vtkMassProperties()
			data.SetInputData(actor.GetMapper().GetInput())
			vol = vol + data.GetVolume()
			sa  = sa  + data.GetSurfaceArea()

		print('  | Selected Volume:      ', vol)
		print('  | Selected Surface Area:', sa)

		return vol, sa

	def Clear(self):
		self.SelectedRegions = []
		self.DeselectedRegions = []

class MyApp(QtWidgets.QWidget, Ui_MainWindow):
	def __init__(self):
		QtWidgets.QWidget.__init__(self)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		# Set up buttons.
		self.loadImagesButton.clicked.connect(self.loadImages)
		self.resetCameraButton.clicked.connect(self.resetCamera); self.resetCameraButton.setEnabled(False)
		self.finalizeButton.clicked.connect(self.finalizeSelection); self.finalizeButton.setEnabled(False)
		self.nextImageButton.clicked.connect(self.nextImage); self.nextImageButton.setEnabled(False)
		self.saveButton.clicked.connect(self.saveResults); self.saveButton.setEnabled(False)

		# Set up render window.
		self.vtkWidget = QVTKRenderWindowInteractor(self.vtkQWidget)
		self.vtkVL.addWidget(self.vtkWidget)

		self.renderer = vtk.vtkRenderer()
		self.renderer.SetBackground(1, 1, 1)

		self.vtkWidget.GetRenderWindow()
		self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)
		self.interactor = self.vtkWidget.GetRenderWindow().GetInteractor()

		self.style = MouseInteractorHighLightActor()
		self.style.SetDefaultRenderer(self.renderer)
		self.interactor.SetInteractorStyle(self.style)

		self.interactor.Initialize()

	def loadImages(self):
		self.imageList = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open Image Files', os.path.expanduser('~'), 'CSF Extracted Images (*_std_brain_csf.nii.gz)')[0]

		if len(self.imageList) > 0:

			# Set up to record results.
			self.IMG_PTR   = 0 	# pointer for current image
			self.MOUSE_IDs = [] # store mouse IDs
			self.CSF_VOLs  = [] # store CSF volumes
			self.CSF_SAs   = [] # store CSF surface areas
			self.VEN_VOLs  = [] # store ventricle volumes
			self.VEN_SAs   = [] # store ventricle surface areas

			self.NUM_IMGS  = np.size(self.imageList)

			# Set up the results table.
			self.resultsTable.setRowCount(np.size(self.imageList))
			for i, file in enumerate(self.imageList):
				ID = file.split('/')[-1].split('.')[0].replace('_std_brain_csf', '')
				self.MOUSE_IDs.append(str(ID))
				self.resultsTable.setItem(i, 0, QtWidgets.QTableWidgetItem(str(ID)))

			self.WORK_DIR  = self.imageList[self.IMG_PTR].replace(self.MOUSE_IDs[self.IMG_PTR] + '_std_brain_csf.nii.gz', '')

			# Render first image
			self.extractRegions(self.imageList[self.IMG_PTR])

			# Enable Buttons
			self.resetCameraButton.setEnabled(True)
			self.finalizeButton.setEnabled(True)
			self.saveButton.setEnabled(True)

	def extractRegions(self, image):
		# read image
		reader = vtk.vtkNIFTIImageReader()
		reader.SetFileName(image)
		reader.Update()

		# marching cubes to extract surfaces
		dmc = vtk.vtkDiscreteMarchingCubes()
		dmc.SetInputConnection(reader.GetOutputPort())
		dmc.ComputeNormalsOn()
		dmc.ComputeGradientsOn()
		dmc.Update()

		# find all isosurfaces
		pdcf_all = vtk.vtkPolyDataConnectivityFilter()
		pdcf_all.SetInputConnection(dmc.GetOutputPort())
		pdcf_all.SetExtractionModeToAllRegions()
		pdcf_all.Update()

		# measure CSF volume and CSF surface area
		data = vtk.vtkMassProperties()
		data.SetInputConnection(pdcf_all.GetOutputPort())
		self.resultsTable.setItem(self.IMG_PTR, 1, QtWidgets.QTableWidgetItem(str(data.GetVolume())))
		self.resultsTable.setItem(self.IMG_PTR, 2, QtWidgets.QTableWidgetItem(str(data.GetSurfaceArea())))

		# find sizes of all isosurfaces
		region_sizes_vtk = pdcf_all.GetRegionSizes()
		region_sizes_np  = array('l', [0]*region_sizes_vtk.GetSize())
		region_sizes_vtk.ExportToVoidPointer(region_sizes_np)

		print('\nProcessing image ...', image)
		# print('  |', region_sizes_np)

		# render potential isosurfaces belonging to ventricles
		for index, size in enumerate(np.sort(region_sizes_np)):
			pdcf_ven = vtk.vtkPolyDataConnectivityFilter()
			pdcf_ven.SetInputConnection(dmc.GetOutputPort())
			pdcf_ven.AddSpecifiedRegion(np.argsort(region_sizes_np)[index])
			pdcf_ven.SetExtractionModeToSpecifiedRegions()

			mapper = vtk.vtkPolyDataMapper()
			mapper.SetInputConnection(pdcf_ven.GetOutputPort())
			mapper.ScalarVisibilityOff()

			actor = vtk.vtkActor()
			actor.SetMapper(mapper)

			prop = vtk.vtkProperty()
			prop.SetColor(31.0/255.0, 119.0/255.0, 180.0/255.0)
			prop.SetOpacity(0.6)

			actor.SetProperty(prop)

			self.renderer.AddViewProp(actor)

		self.resetCamera()

	def resetCamera(self):
		self.camera = vtk.vtkCamera()
		self.renderer.SetActiveCamera(self.camera)
		self.camera.Roll(-100)
		self.camera.Azimuth(-50)
		self.camera.Elevation(30)
		self.renderer.ResetCamera()

	def finalizeSelection(self):
		print (' | Getting data from selected regions ...')
		selectedActors = self.style.SelectedRegions
		
		selectedVolume, selectedSA = self.style.SelectedVolume()
		self.resultsTable.setItem(self.IMG_PTR, 3, QtWidgets.QTableWidgetItem(str(selectedVolume)))
		self.resultsTable.setItem(self.IMG_PTR, 4, QtWidgets.QTableWidgetItem(str(selectedSA)))

		print (' | Resetting the camera ...')
		self.resetCamera()

		print (' | Clearing renderer and interactor ...')
		for actor in self.renderer.GetActors():
			self.renderer.RemoveViewProp(actor)
		self.style.Clear()

		print (' | Appending selected polydata to view ...')
		appender = vtk.vtkAppendPolyData()
		for actor in selectedActors:
			appender.AddInputData(actor.GetMapper().GetInput())

		print (' | Depth sort for proper visualization ...')
		# depth sort fixes visualization problems, but requires one actor for multiple meshes.
		# therefore, depth sorting is not yet fixed during selection process.
		# but proper depth sorting is used when the ventricle image is output
		depthSort = vtk.vtkDepthSortPolyData()
		depthSort.SetInputConnection(appender.GetOutputPort())
		depthSort.SetDirectionToBackToFront()
		depthSort.SetVector(1, 1, 1)
		depthSort.SetCamera(self.camera)
		depthSort.SortScalarsOn()
		depthSort.Update()

		mapper = vtk.vtkPolyDataMapper()
		mapper.SetInputConnection(depthSort.GetOutputPort())
		mapper.SetScalarRange(0, depthSort.GetOutput().GetNumberOfCells())
		mapper.ScalarVisibilityOff()

		actor = vtk.vtkActor()
		actor.SetMapper(mapper)

		prop = vtk.vtkProperty()
		prop.SetColor(31.0/255.0, 119.0/255.0, 180.0/255.0)
		prop.SetOpacity(0.6)
		
		actor.SetProperty(prop)
		self.renderer.AddViewProp(actor)
		self.resetCamera()

		self.resetCameraButton.setEnabled(False)
		self.finalizeButton.setEnabled(False)

		# Save Visualization
		print(' | Saving visualization ...')
		w2if = vtk.vtkWindowToImageFilter()
		w2if.SetInput(self.vtkWidget.GetRenderWindow())
		w2if.Update()
		 
		png_writer = vtk.vtkPNGWriter()
		png_writer.SetFileName(self.WORK_DIR + '/' + self.MOUSE_IDs[self.IMG_PTR] + '_brain_ventricle.png')
		png_writer.SetInputConnection(w2if.GetOutputPort())
		png_writer.Write()

		# If not the last image
		if not(self.IMG_PTR == self.NUM_IMGS - 1):
			self.nextImageButton.setEnabled(True)

	def nextImage(self):
		print('\nFetching next image ...')
		self.IMG_PTR = self.IMG_PTR + 1

		# Clear render
		print('  | Clearing renderer and interactor ...')
		for actor in self.renderer.GetActors():
			self.renderer.RemoveViewProp(actor)

		# Clear interactor
		self.style.Clear()

		# Load next image
		print('  | Load next image ...')
		self.extractRegions(self.imageList[self.IMG_PTR])

		self.nextImageButton.setEnabled(False)
		self.resetCameraButton.setEnabled(True)
		self.finalizeButton.setEnabled(True)

	def saveResults(self):
		save_filename = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save Results', self.WORK_DIR, 'Comma Separted Values (*.csv)')[0])
		if save_filename != '':
			save_file = open(save_filename, 'w')
			save_file.write(',ID,CSF Volume, CSF Surface Area, Ventricle Volume, Ventricle Surface Area\n')
			for i in range(0, self.NUM_IMGS):
				save_file.write(str(i) + ',')
				save_file.write(self.resultsTable.item(i, 0).text() + ',')
				save_file.write(self.resultsTable.item(i, 1).text() + ',')
				save_file.write(self.resultsTable.item(i, 2).text() + ',')
				save_file.write(self.resultsTable.item(i, 3).text() + ',')
				save_file.write(self.resultsTable.item(i, 4).text() + '\n')
			save_file.close()

		# Remove items from table
		self.resultsTable.setRowCount(0)

		# Enable load button
		self.loadImagesButton.setEnabled(True)
		self.saveButton.setEnabled(False)

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = MyApp()
	window.show()
	sys.exit(app.exec_())