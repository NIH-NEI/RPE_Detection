import os
import sys
import vtk
from vtk.util import numpy_support
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtCore, QtWidgets
import numpy as np
import math
import SimpleITK as sitk
from AOFileIO import write_points
import AOConfig as cfg

class MouseAnnotationInteractor(vtk.vtkInteractorStyleImage):
    def __init__(self, mouse_mode = 0, parent=None):
        self.AddObserver("LeftButtonPressEvent",self.leftButtonPressEvent)
        self.AddObserver("LeftButtonReleaseEvent", self.leftButtonReleaseEvent)
        self.AddObserver("MiddleButtonPressEvent", self.middleButtonPressEvent)
        self.AddObserver("MiddleButtonReleaseEvent", self.middleButtonReleaseEvent)
        self.AddObserver("MouseMoveEvent", self.mouseMoveEvent)
        self.AddObserver("EnterEvent", self.enterEvent)
        self.AddObserver("LeaveEvent", self.leaveEvent)
        self.AddObserver("KeyPressEvent", self.keyPressEvent)
        self.AddObserver("KeyReleaseEvent", self.keyReleaseEvent)

        self.parent = parent
        self._mouse_mode = mouse_mode
        self._annotations = None
        self._annotation_pts = None #used for VTK
        self._image_name = None
        self._tolerance = 0
        self._image_origin = None
        self._image_spacing = None
        #
        self._shift_down = False
        self._mouse_scroll = False
        self._mouse_in = False

    @staticmethod
    def pt_dist(pt1, pt2):
        dx = pt1[0] - pt2[0]
        dy = pt1[1] - pt2[1]
        return math.sqrt(dx*dx + dy*dy)

    @property
    def annotation_pts(self):
        return self._annotation_pts

    @annotation_pts.setter
    def annotation_pts(self, val):
        self._annotation_pts = val

    def set_image_name(self, name):
        self._image_name = name

    def set_image_origin(self, origin):
        self._image_origin = origin

    def set_image_spacing(self, spacing):
        self._image_spacing = spacing

    @property
    def tolerance(self):
        return self._tolerance

    @tolerance.setter
    def tolerance(self, val):
        self._tolerance = val

    def set_mouse_mode(self, mouse_mode):
        self._mouse_mode = mouse_mode

    def set_annotations(self, pts):
        self._annotations = pts

    def leftButtonPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            self._shift_down = False
            obj.OnLeftButtonDown()
            return
        self._mouse_scroll = False
        if self.GetInteractor().GetShiftKey():
            self._shift_down = self._mouse_scroll = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.SizeAllCursor)
            obj.OnLeftButtonDown()
            return
            
        # Add small negative value (-0.001) to Z-coordinate to make annotation
        # closer to the camera
        pick_value = self.GetInteractor().GetPicker().Pick(self.GetInteractor().GetEventPosition()[0],
                                                           self.GetInteractor().GetEventPosition()[1],
                                                           -0.001, self.GetDefaultRenderer())
        pick_pos = self.GetInteractor().GetPicker().GetPickPosition()
        if self._mouse_mode != 0 and pick_value == 1:
            old_len = len(self._annotations)
            if self._mouse_mode == 1:
                #append a point
                for pt in self._annotations:
                    if self.pt_dist(pt, pick_pos) < self._tolerance:
                        break
                else:
                    self._annotations.append(pick_pos)
            elif self._mouse_mode == 2:
                #erase a point
                for idx, pt in enumerate(self._annotations):
                    if self.pt_dist(pt, pick_pos) < self._tolerance:
                        del self._annotations[idx]
                        break
            #
            if len(self._annotations) != old_len:
                self._annotation_pts.Initialize()
                if len(self._annotations) is not 0:
                    self._annotation_pts.SetData(numpy_support.numpy_to_vtk(np.asarray(self._annotations)))
                self._annotation_pts.Modified()
    
                write_points(self._image_name, self._annotations, self._image_origin, self._image_spacing)
                if not self.parent is None:
                    self.parent.reset_view(False)
            return

        obj.OnLeftButtonDown()
    #
    def leftButtonReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if self._mouse_scroll:
            self._mouse_scroll = False
            if self._shift_down:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        obj.OnLeftButtonUp()
    def mouseMoveEvent(self, obj, event):
        obj.OnMouseMove()
    def middleButtonPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if self._mouse_in:
            self._mouse_scroll = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.SizeAllCursor)
        obj.OnMiddleButtonDown()
    def middleButtonReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        self._mouse_scroll = False
        if self._shift_down:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        obj.OnMiddleButtonUp()
    def enterEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            self._mouse_in = True
            if self._shift_down:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        else:
            # If a second OnEnter() received without a matching OnLeave(),
            # the QVTKWidget does not have keyboard focus and it won't receive OnKeyUp() for Shift either.
            # Like the user tried to drag the mouse from another widget while holding Shift down.
            self._shift_down = False
        obj.OnEnter()
    def leaveEvent(self, obj, event):
        self._mouse_in = False
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        obj.OnLeave()
    def keyPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            obj.OnKeyPress()
            return
        key = self.GetInteractor().GetKeySym()
        if key == 'Up':
            cfg.main_wnd.previous_image()
            return
        elif key == 'Down':
            cfg.main_wnd.next_image()
            return
        elif key == 'Shift_L':
            self._shift_down = True
            if not self._mouse_scroll:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        obj.OnKeyPress()
    def keyReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        key = self.GetInteractor().GetKeySym()
        if key == 'Up' or key == 'Down':
            return
        if key == 'Shift_L':
            self._shift_down = False
        obj.OnKeyRelease()
    #


class ao_visualization(object):
    def __init__(self, vtk_widget, mouse_mode):
        self._vtk_widget = vtk_widget
        self._draw_image()

        self._annotation_size = 12
        self._draw_annotations()

        # scalarbar = vtk.vtkScalarBarActor()
        # scalarbar.SetLookupTable(self._prob_lut)
        # scalarbar.SetNumberOfLabels(4)

        self._render = vtk.vtkRenderer()
        self._render.AddActor(self._image_actor)
        self._render.AddActor(self._annotated_actor)
        self._render.ResetCamera()

        self._vtk_widget.GetRenderWindow().AddRenderer(self._render)
        self._style = MouseAnnotationInteractor(parent=self)
        self._style.SetDefaultRenderer(self._render)
        self._style.annotation_pts = self._annotated_points
        #self._vtk_widget.SetInteractorStyle(vtk.vtkInteractorStyleImage())
        self._vtk_widget.SetInteractorStyle(self._style)
        iren = self._vtk_widget.GetRenderWindow().GetInteractor()

        iren.Initialize()
        iren.Start()

    def _draw_image(self):
        self._image_data = vtk.vtkImageData()
        self._image_data.SetDimensions(1, 1, 1)
        if vtk.VTK_MAJOR_VERSION <= 5:
            self._image_data.SetNumberOfScalarComponents(1)
            self._image_data.SetScalarTypeToUnsignedChar()
        else:
            self._image_data.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)

        self._image_actor = vtk.vtkImageActor()
        self._image_actor.GetMapper().SetInputData(self._image_data)

    def _draw_annotations(self):
        self._annotated_points = vtk.vtkPoints()
        self._annotated_points.SetDataTypeToFloat()
        self._annotated_poly = vtk.vtkPolyData()
        self._annotated_poly.SetPoints(self._annotated_points)

        self._annotated_glyph_source = vtk.vtkGlyphSource2D()
        self._annotated_glyph_source.SetGlyphTypeToCross()
        self._annotated_glyph_source.SetScale(self._annotation_size)

        self._annotated_glyph = vtk.vtkGlyph3D()
        self._annotated_glyph.SetSourceConnection(self._annotated_glyph_source.GetOutputPort())
        self._annotated_glyph.SetInputData(self._annotated_poly)

        self._annotated_mapper = vtk.vtkDataSetMapper()
        self._annotated_mapper.SetInputConnection(self._annotated_glyph.GetOutputPort())
        self._annotated_mapper.ScalarVisibilityOff()

        self._annotated_actor = vtk.vtkActor()
        self._annotated_actor.SetMapper(self._annotated_mapper)
        self._annotated_actor.GetProperty().SetColor(0, 1, 0)

    def initialization(self):
        self._image_data.Initialize()
        self._image_data.Modified()

        self._annotated_points.Initialize()
        self._annotated_poly.Modified()

    def _change_camera_orientation(self):
        self._render.ResetCamera()
        fp = self._render.GetActiveCamera().GetFocalPoint()
        p = self._render.GetActiveCamera().GetPosition()
        dist = (fp[0]-p[0])*(fp[0]-p[0])+(fp[1]-p[1])*(fp[1]-p[1])+(fp[2]-p[2])*(fp[2]-p[2])
        dist = math.sqrt(dist)
        self._render.GetActiveCamera().SetPosition(fp[0], fp[1], fp[2]-dist)
        self._render.GetActiveCamera().SetViewUp(0.0, -1.0, 0.0)
        self._render.GetActiveCamera().SetParallelProjection(True)

    def reset_view(self, camera_flag=False):
        if camera_flag:
            self._change_camera_orientation()
        self._vtk_widget.GetRenderWindow().Render()
        
    def reset_color(self):
        self._image_actor.GetProperty().SetColorLevel(127.5)
        self._image_actor.GetProperty().SetColorWindow(255.)
        self._vtk_widget.GetRenderWindow().Render()

    def set_mouse_mode(self, mouse_mode):
        self._style.set_mouse_mode(mouse_mode)


    def _convert_nparray_to_vtk_image(self, itk_img, vtk_img):
        img_size = itk_img.GetSize()
        img_orig = itk_img.GetOrigin()
        img_spacing = itk_img.GetSpacing()
        n_array = sitk.GetArrayFromImage(itk_img)
        v_image = numpy_support.numpy_to_vtk(n_array.flat)
        vtk_img.SetOrigin(img_orig[0], img_orig[1], 0)
        vtk_img.SetSpacing(img_spacing[0], img_spacing[1], 1.0)
        vtk_img.SetDimensions(img_size[0], img_size[1], 1)
        vtk_img.AllocateScalars(numpy_support.get_vtk_array_type(n_array.dtype), 1)
        vtk_img.GetPointData().SetScalars(v_image)

    def set_image(self, itk_img):
        self._style.set_image_origin(itk_img.GetOrigin())
        self._style.set_image_spacing(itk_img.GetSpacing())

        self._image_data.Initialize()
        self._convert_nparray_to_vtk_image(itk_img, self._image_data)
        self._style.tolerance = 6*(itk_img.GetSpacing()[0]+itk_img.GetSpacing()[1])
        self._image_data.Modified()

    def set_annotations(self, pts):
        self._style.set_annotations(pts)
        self._annotated_points.Initialize()
        if len(pts) is not 0:
            self._annotated_points.SetData(numpy_support.numpy_to_vtk(np.asarray(pts)))
        # self._annotated_points.SetNumberOfPoints(len(pts))
        # for id, pt in enumerate(pts):
        #     self._annotated_points.SetPoint(id, pt[0], pt[1], 0)
        self._annotated_points.Modified()

    def set_image_name(self, img_name):
        self._style.set_image_name(img_name)

    @property
    def annotation_pts_visibility(self):
        return self._annotated_actor.GetVisibility()
    @annotation_pts_visibility.setter
    def annotation_pts_visibility(self, state):
        self._annotated_actor.SetVisibility(state)

    def set_annotation_pts_size(self, size):
        self._annotation_size = size
        self._annotated_glyph_source.SetScale(self._annotation_size)

