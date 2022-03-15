import os
import sys
import platform
import enum
from collections import namedtuple
import vtk
from vtk.util import numpy_support
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtCore, QtWidgets
import numpy as np
import math
from scipy.spatial import Voronoi
import SimpleITK as sitk
from AOFileIO import write_points
import AOConfig as cfg

@enum.unique
class MouseOp(enum.IntEnum):
    Normal = 0
    Add = 1
    Remove = 2
    Move = 3
    EraseMulti = 4
    
UndoEntry = namedtuple('UndoEntry', ['m_del', 'm_more', 'pt'])
class UndoStack(object):
    ADD = 0
    DEL = 1
    IMG = 2
    def __init__(self, maxundo=1000):
        self.maxundo = maxundo
        #
        self.buf = []
    #
    def clear(self):
        self.buf[:] = []
    #
    def is_empty(self):
        return len(self.buf) == 0
    #
    def push_undo(self, pt, m_del=ADD, m_more=False):
        self.buf.insert(0, UndoEntry(m_del, m_more, pt))
        if len(self.buf) > self.maxundo:
            self.buf[self.maxundo:] = []
    #
    def pop_undo(self):
        if len(self.buf) == 0:
            return ADD, False, None
        ent = self.buf.pop(0)
        return ent.m_del, ent.m_more, ent.pt
    #

###### Winding number test for a point in a polygon
# Adapted from: http://geomalgorithms.com/a03-_inclusion.html

# isLeft(): tests if a point is Left|On|Right of an infinite line.
#    Input:  three points P0, P1, and P2
#    Return: >0 for P2 left of the line through P0 and P1
#            =0 for P2  on the line
#            <0 for P2  right of the line
#
# P1, P2, P3 are lists [x,y] or tuples (x,y)
def isLeft(P0, P1, P2):
    return (P1[0]-P0[0])*(P2[1]-P0[1]) - (P2[0]-P0[0])*(P1[1]-P0[1])

# wn_PnPoly(): winding number test for a point in a polygon
#      Input:   pt = a point, list or tuple (x,y)
#               poly = vertex points of a polygon, a collection of points, poly[0] == poly[-1]
#      Return:  wn = the winding number (=0 only when pt is outside)
def wn_PnPoly(pt, poly):
    n = len(poly) - 1
    wn = 0
    for i in range(n):
        if poly[i][1] < pt[1]:          # start y <= pt.y
            if poly[i+1][1] > pt[1]:    # an upward crossing
                if isLeft(poly[i], poly[i+1], pt) > 0:  # pt left of edge
                    wn += 1             # have a valid up intersect
        else:                           # start y > P.y (no test needed)
            if poly[i+1][1] <= pt[1]:   # a downward crossing
                if isLeft(poly[i], poly[i+1], pt) < 0:  # pt right of edge
                    wn -= 1             # have a valid down intersect
    return wn

def isPointInside(pt, contour):
    return wn_PnPoly(pt, contour) != 0

###### End of winding number algorithm

def dist(pt1, pt2):
    return math.sqrt((pt1[0]-pt2[0])**2 + (pt1[1]-pt2[1])**2)

# Optimize a contour by removing vertices too close to each other
def optimizeContour(contour, min_dist=1.5):
    n = len(contour)
    if n < 5:
        return contour
    pt1 = contour[0]
    res = [pt1]
    for i in range(1, n):
        pt2 = contour[i]
        cur_dist = dist(pt1, pt2)
        if cur_dist >= min_dist:
            res.append(pt2)
            pt1 = pt2
    return res

def boundingBox(contour):
    pt = contour[0]
    xmin = xmax = pt[0]
    ymin = ymax = pt[1]
    for pt in contour:
        if pt[0] < xmin: xmin = pt[0]
        if pt[0] > xmax: xmax = pt[0]
        if pt[1] < ymin: ymin = pt[1]
        if pt[1] > ymax: ymax = pt[1]
    return xmin, ymin, xmax, ymax

def isInBB(bb, pt):
    xmin, ymin, xmax, ymax = bb
    if pt[0] < xmin or pt[0] > xmax: return False
    return pt[1] >= ymin and pt[1] <= ymax

class SegmentClipper(object):
    Inside = 0
    Left = 1
    Right = 2
    Bottom = 4
    Top = 8
    def __init__(self, rect_dim):
        self.w = rect_dim[0]
        self.h = rect_dim[1]
        self.x0 = 0.001
        self.y0 = 0.001
        self.x1 = self.w - 0.001
        self.y1 = self.h - 0.001
    #
    def bnd_points(self):
        pts = []
        for y in (-self.h*10, self.h*0.5, self.h*11):
            for x in (-self.w*10, self.w*0.5, self.w*11):
                pt = (x, y)
                if self.outCode(pt) != self.Inside:
                    pts.append(pt)
        return pts
    #
    def clip(self, pt0, pt1):
        #return (pt0, pt1)
        oc0 = self.outCode(pt0)
        oc1 = self.outCode(pt1)
        if oc0 != self.Inside and oc1 != self.Inside:
            return None
        #while oc0 != self.Inside or oc1 != self.Inside:
        if oc0 != self.Inside:
            pt0 = self.intersect(pt1, pt0, oc0)
            if pt0 is None: return None
            oc0 = self.outCode(pt0)
        elif oc1 != self.Inside:
            pt1 = self.intersect(pt0, pt1, oc1)
            if pt1 is None: return None
            oc1 = self.outCode(pt1)
        return [pt0, pt1]
    #
    def intersect(self, pt0, pt1, oc):
        dx = pt1[0] - pt0[0]
        dy = pt1[1] - pt0[1]
        if oc & self.Left:
            y = pt0[1] + dy * (self.x0 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x0, y)
        if oc & self.Right:
            y = pt0[1] + dy * (self.x1 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x1, y)
        if oc & self.Top:
            x = pt0[0] + dx * (self.y0 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y0)
        if oc & self.Bottom:
            x = pt0[0] + dx * (self.y1 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y1)
        return None
    #
    def outCode(self, pt):
        oc = 0
        if pt[0] < self.x0:
            oc |= self.Left
        if pt[0] > self.x1:
            oc |= self.Right
        if pt[1] < self.y0:
            oc |= self.Top
        if pt[1] > self.y1:
            oc |= self.Bottom
        return oc
    #

class MouseAnnotationInteractor(vtk.vtkInteractorStyleImage):
    def __init__(self, mouse_mode = 0, parent=None):
        self._win = platform.system().lower() == 'windows'
        self.AddObserver("LeftButtonPressEvent",self.leftButtonPressEvent)
        self.AddObserver("LeftButtonReleaseEvent", self.leftButtonReleaseEvent)
        self.AddObserver("MiddleButtonPressEvent", self.middleButtonPressEvent)
        self.AddObserver("MiddleButtonReleaseEvent", self.middleButtonReleaseEvent)
        self.AddObserver("MouseMoveEvent", self.mouseMoveEvent)
        self.AddObserver("EnterEvent", self.enterEvent)
        self.AddObserver("LeaveEvent", self.leaveEvent)
        self.AddObserver("KeyPressEvent", self.keyPressEvent)
        self.AddObserver("KeyReleaseEvent", self.keyReleaseEvent)
        self.AddObserver("CharEvent", self.charEvent)

        self.parent = parent
        self._mouse_mode = mouse_mode
        self._annotations = []
        self._annotation_pts = None #used for VTK
        self._image_name = None
        self._tolerance = 0
        self._image_origin = None
        self._image_spacing = None
        #
        self._mouse_down = False
        self._ctrl_down = False
        self._shift_down = False
        self._alt_down = False
        self._mouse_scroll = False
        self._mouse_in = False
        self._contour_pts = []
        #
        self.m_idx = -1
        self.m_xpos = 0
        self.m_ypos = 0
        #
        self.img_dim = None
        self.max_xpos = 0
        self.max_ypos = 0
        self.ci = (127.5, 255.)
        self.last_pick_value = 0
        #
        self._undo_stack = UndoStack()
    #

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
        
    def can_add(self, pick):
        for pt in self._annotations:
            if self.pt_dist(pt, pick) < self._tolerance:
                return False
        return True
    def find_point(self, pick, delta=0.001):
        for idx, pt in enumerate(self._annotations):
            if self.pt_dist(pt, pick) < delta:
                return idx
        return -1
    
    def closest_border(self, pt):
        pidx = 0
        x = 0.
        y = 0.
        dx0 = math.fabs(pt[0])
        dx1 = math.fabs(pt[0] - self.img_dim[0])
        dy0 = math.fabs(pt[1])
        dy1 = math.fabs(pt[1] - self.img_dim[1])
        if dx0 <= dx1 and dx0 <= dy0 and dx0 <= dy1:
            x = 0.
            y = pt[1]
        elif dx1 <= dy0 and dx1 <= dy1:
            x = float(self.img_dim[0])
            y = pt[1]
        elif dy0 <= dy1:
            x = pt[0]
            y = 0.
            pidx = 1
        else:
            x = pt[0]
            y = float(self.img_dim[1])
            pidx = 1
        return (x, y, -0.001), pidx
    def closest_border_2(self, pt):
        pt1, pidx1 = self.closest_border(pt)
        if len(self._contour_pts) > 0:
            pt0, pidx0 = self.closest_border(self._contour_pts[-1])
            if pidx0 != pidx1:
                pt2 = [0, 0, -0.001]
                pt2[pidx0] = pt0[pidx0]
                pt2[pidx1] = pt1[pidx1]
                self._contour_pts.append(tuple(pt2))
        return pt1
    
    def _update_annotations(self, upd_voronoi=True):
        self._annotation_pts.Initialize()
        if len(self._annotations) is not 0:
            self._annotation_pts.SetData(numpy_support.numpy_to_vtk(np.asarray(self._annotations)))
        self._annotation_pts.Modified()
        write_points(self._image_name, self._annotations, self._image_origin, self._image_spacing)
        if not self.parent is None:
            if upd_voronoi:
                self.parent.update_voronoi_segments()
            else:
                self.parent.reset_view(False)
    #
    def undo(self):
        has_more = not self._undo_stack.is_empty()
        dirty = False
        while has_more:
            m_del, has_more, pick = self._undo_stack.pop_undo()
            if pick is None: break
            if m_del == UndoStack.DEL:
                if self.can_add(pick):
                    self._annotations.append(pick)
                    dirty = True
            elif m_del == UndoStack.ADD:
                idx = self.find_point(pick)
                if idx >= 0:
                    del self._annotations[idx]
                    dirty = True
            elif m_del == UndoStack.IMG:
                self.parent.color_info = pick
                dirty = True
        if dirty:
            self._update_annotations()
    #
    def delete_points_inside(self):
        contour = [(pt[0], pt[1]) for pt in self._contour_pts]
        if len(contour) < 3: return
        contour.append(contour[0])
        annotations = []
        has_more = False
        contour = optimizeContour(contour)
        bb = boundingBox(contour)
        for pt in self._annotations:
            if isInBB(bb, pt) and isPointInside(pt, contour):
                self._undo_stack.push_undo(pt, UndoStack.DEL, has_more)
                has_more = True
            else:
                annotations.append(pt)
        if has_more:
            self._annotations[:] = annotations
            self._update_annotations()
    #

    def _GetControlKey(self):
        # Check for either Ctrl or Alt (Ctrl+mouse does not work on Mac)
        if self.GetInteractor().GetControlKey():
            return True
        return not self._win and self._alt_down
    def leftButtonPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            self._shift_down = False
            obj.OnLeftButtonDown()
            return
        inter = self.GetInteractor()
        self._mouse_scroll = False
        if inter.GetShiftKey():
            self._shift_down = self._mouse_scroll = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.SizeAllCursor)
            obj.OnLeftButtonDown()
            return
        
        self.img_dim = self.parent.get_image_dimensions()
        self.max_xpos = self.img_dim[0] - 0.5
        self.max_ypos = self.img_dim[1] - 0.5
        self.ci = self.parent.color_info
        self._contour_pts = []
        self._mouse_down = True
        op = self._mouse_mode
        if self._GetControlKey() and op in (MouseOp.Add, MouseOp.Move):
            op = MouseOp.Remove
            self._ctrl_down = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
            
        mx, my = inter.GetEventPosition()
        pick_value = inter.GetPicker().Pick(mx, my, -0.001, self.GetDefaultRenderer())
        if op in (MouseOp.Add, MouseOp.Move, MouseOp.Remove, MouseOp.EraseMulti):
            if pick_value == 0:
                return
            pick_pos = self.GetInteractor().GetPicker().GetPickPosition()
            dirty_ann = False
            dirty_cont = False
            if op == MouseOp.Add:
                # Add point
                if self.can_add(pick_pos):
                    self._annotations.append(pick_pos)
                    self._undo_stack.push_undo(pick_pos, UndoStack.ADD, False)
                    dirty_ann = True
            elif op == MouseOp.Remove:
                # Remove point
                idx = self.find_point(pick_pos, self._tolerance)
                if idx >= 0:
                    self._undo_stack.push_undo(self._annotations[idx], UndoStack.DEL, False)
                    del self._annotations[idx]
                    dirty_ann = True
            elif op == MouseOp.Move:
                self.m_idx = self.find_point(pick_pos, self._tolerance)
                if self.m_idx >= 0:
                    pt = self._annotations[self.m_idx]
                    self.m_xpos = pt[0]
                    self.m_ypos = pt[1]
            elif op == MouseOp.EraseMulti and not self.parent is None:
                self.last_pick_value = pick_value
                self._contour_pts = [pick_pos]
                dirty_cont = True
            
            if dirty_ann:
                self._update_annotations()
            if dirty_cont:
                self.parent.set_interactive_contour(self._contour_pts)
            if not self.parent is None and (dirty_ann or dirty_cont):
                self.parent.reset_view(False)
            return
        #
        obj.OnLeftButtonDown()
    #
    def leftButtonReleaseEvent(self, obj, event):
        self._mouse_down = False
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if self._mouse_scroll:
            self._mouse_scroll = False
            if self._shift_down:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
            obj.OnLeftButtonUp()
            return
        inter = self.GetInteractor()
        op = self._mouse_mode
        if self._GetControlKey() and op in (MouseOp.Add, MouseOp.Move):
            op = MouseOp.Remove
            self._ctrl_down = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        if op == MouseOp.Remove:
            return
        if op in (MouseOp.Move, MouseOp.EraseMulti):
            mx, my = inter.GetEventPosition()
            pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
            pick_pos = inter.GetPicker().GetPickPosition()
            if op == MouseOp.EraseMulti:
                if pick_value == 0 and len(self._contour_pts) > 0:
                    pt = self.closest_border_2(self._contour_pts[0])
                    pick_value = 1
                if pick_value == 0: return
                self._contour_pts.append(pick_pos)
                self.delete_points_inside()
                if self.parent is None: return
                self.parent.set_interactive_contour(None)
                self.parent.reset_view(False)
            elif op == MouseOp.Move and self.m_idx >= 0:
                pt = self._annotations[self.m_idx]
                old_pt = (self.m_xpos, self.m_ypos, -0.0001)
                if self.pt_dist(pt, old_pt) >= 0.001:
                    self._undo_stack.push_undo(old_pt, UndoStack.DEL, False)
                    self._undo_stack.push_undo(pt, UndoStack.ADD, True)
                self._update_annotations()
            return
        _ci = self.parent.color_info
        if math.fabs(_ci[0] - self.ci[0]) > 0.01 or math.fabs(_ci[1] - self.ci[1]) > 0.01:
            self._undo_stack.push_undo(self.ci, UndoStack.IMG, False)
        obj.OnLeftButtonUp()
    #
    def mouseMoveEvent(self, obj, event):
        if self._shift_down:
            obj.OnMouseMove()
            return
        if self._mouse_down:
            inter = self.GetInteractor()
            op = self._mouse_mode
            if op in (MouseOp.Move, MouseOp.EraseMulti):
                mx, my = inter.GetEventPosition()
                pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
                pick_pos = inter.GetPicker().GetPickPosition()
                if op == MouseOp.Move and pick_value != 0 and self.m_idx >= 0:
                    xpos, ypos = pick_pos[:2]
                    if xpos < 0.5: xpos = 0.5
                    if xpos > self.max_xpos: xpos = self.max_xpos
                    if ypos < 0.5: ypos = 0.5
                    if ypos > self.max_ypos: ypos = self.max_ypos
                    
                    self._annotations[self.m_idx] = (xpos, ypos, -0.0001)
                    self._update_annotations(False)
                elif op == MouseOp.EraseMulti:
                    dirty = False
                    if pick_value == 0:
                        if self.last_pick_value != 0 and len(self._contour_pts) > 0:
                            pt, _ = self.closest_border(self._contour_pts[-1])
                            self._contour_pts.append(pt)
                            dirty = True
                    else:
                        dirty = True
                        if self.last_pick_value == 0:
                            pt = self.closest_border_2(pick_pos)
                            self._contour_pts.append(pt)
                        self._contour_pts.append(pick_pos)
                    self.last_pick_value = pick_value
                    if dirty and not self.parent is None:
                        self.parent.set_interactive_contour(self._contour_pts)
                        self.parent.reset_view(False)
                return
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
    def charEvent(self, obj, event):
        key = self.GetInteractor().GetKeyCode()
        if key in 'xXyYzZrRwWfFpP':
            return
        obj.OnChar()
    def leaveEvent(self, obj, event):
        self._mouse_in = False
        self._alt_down = False
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        obj.OnLeave()
    def keyPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        key = self.GetInteractor().GetKeySym()
        if key == 'Alt_L':
            self._alt_down = True
            if not self._win: key = 'Control_L'
        if not self._mouse_in:
            obj.OnKeyPress()
            return
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
        elif key == 'Control_L':
            if self._mouse_mode in (MouseOp.Add, MouseOp.Move):
                self._ctrl_down = True
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
                return
        if not self._alt_down:
            obj.OnKeyPress()
    def keyReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        key = self.GetInteractor().GetKeySym()
        if key == 'Alt_L':
            self._alt_down = False
            if not self._win: key = 'Control_L'
        if key == 'Up' or key == 'Down':
            return
        if self._ctrl_down:
            if key == 'Control_L':
                self._ctrl_down = False
                return
        if key == 'Shift_L':
            self._shift_down = False
        obj.OnKeyRelease()
    #

class ao_visualization(object):
    def __init__(self, vtk_widget, mouse_mode):
        self._vtk_widget = vtk_widget
        self._draw_image()

        self._voronoi = False
        self._interactive_contour_width = 3
        self._voronoi_contour_width = 1.5
        self._annotation_size = 12
        self._draw_annotations()
        self._draw_interactive_contours()
        self._draw_voronoi_contours()

        # scalarbar = vtk.vtkScalarBarActor()
        # scalarbar.SetLookupTable(self._prob_lut)
        # scalarbar.SetNumberOfLabels(4)

        self._render = vtk.vtkRenderer()
        self._render.AddActor(self._image_actor)
        self._render.AddActor(self._annotated_actor)
        self._render.AddActor(self._interactive_contour_actor)
        self._render.AddActor(self._voronoi_contour_actor)
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

    def _draw_interactive_contours(self):
        self._interactive_contour_points = vtk.vtkPoints()
        self._interactive_contour_points.SetDataTypeToFloat()
        self._interactive_contour_lines = vtk.vtkCellArray()
        self._interactive_contour_poly = vtk.vtkPolyData()
        self._interactive_contour_poly.SetPoints(self._interactive_contour_points)
        self._interactive_contour_poly.SetLines(self._interactive_contour_lines)

        self._interactive_contour_mapper = vtk.vtkPolyDataMapper()
        self._interactive_contour_mapper.SetInputData(self._interactive_contour_poly)
        self._interactive_contour_mapper.ScalarVisibilityOff()

        self._interactive_contour_actor = vtk.vtkActor()
        self._interactive_contour_actor.SetMapper(self._interactive_contour_mapper)
        self._interactive_contour_actor.GetProperty().SetColor(217/255.0, 95.0/255.0, 14.0/255.0)
        self._interactive_contour_actor.GetProperty().SetLineWidth(self._interactive_contour_width)
        
    def _draw_voronoi_contours(self):
        self._voronoi_contour_points = vtk.vtkPoints()
        self._voronoi_contour_points.SetDataTypeToFloat()
        self._voronoi_contour_lines = vtk.vtkCellArray()
        self._voronoi_contour_poly = vtk.vtkPolyData()
        self._voronoi_contour_poly.SetPoints(self._voronoi_contour_points)
        self._voronoi_contour_poly.SetLines(self._voronoi_contour_lines)

        self._voronoi_contour_mapper = vtk.vtkPolyDataMapper()
        self._voronoi_contour_mapper.SetInputData(self._voronoi_contour_poly)
        self._voronoi_contour_mapper.ScalarVisibilityOff()

        self._voronoi_contour_actor = vtk.vtkActor()
        self._voronoi_contour_actor.SetMapper(self._voronoi_contour_mapper)
        self._voronoi_contour_actor.GetProperty().SetColor(5./255.0, 196.0/255.0, 196.0/255.0)
        self._voronoi_contour_actor.GetProperty().SetLineWidth(self._voronoi_contour_width)

    def initialization(self):
        self._image_data.Initialize()
        self._image_data.Modified()

        self._annotated_points.Initialize()
        self._annotated_poly.Modified()

        self._interactive_contour_points.Initialize()
        self._interactive_contour_lines.Initialize()
        self._interactive_contour_poly.Modified()

        self._voronoi_contour_points.Initialize()
        self._voronoi_contour_lines.Initialize()
        self._voronoi_contour_poly.Modified()

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
        
    @property
    def color_info(self):
        p = self._image_actor.GetProperty()
        return (p.GetColorLevel(), p.GetColorWindow())
    @color_info.setter
    def color_info(self, v):
        try:
            cval, cwin = v
        except Exception:
            cval = 127.5
            cwin = 255.
        self._image_actor.GetProperty().SetColorLevel(cval)
        self._image_actor.GetProperty().SetColorWindow(cwin)
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
        self._style._undo_stack.clear()
        
    def get_image_dimensions(self):
        s = self._image_data.GetSpacing()
        d = self._image_data.GetDimensions()
        return (s[0]*d[0], s[1]*d[1], 1.)

    def set_annotations(self, pts):
        self._style.set_annotations(pts)
        self._annotated_points.Initialize()
        if len(pts) is not 0:
            self._annotated_points.SetData(numpy_support.numpy_to_vtk(np.asarray(pts)))
        # self._annotated_points.SetNumberOfPoints(len(pts))
        # for id, pt in enumerate(pts):
        #     self._annotated_points.SetPoint(id, pt[0], pt[1], 0)
        self._annotated_points.Modified()
        self._style._undo_stack.clear()
        self.update_voronoi_segments()
        
    def is_undo_empty(self):
        return self._style._undo_stack.is_empty()
    
    def undo(self):
        self._style.undo()

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

    def set_interactive_contour(self, pts=None):
        self._interactive_contour_points.Initialize()
        self._interactive_contour_lines.Initialize()

        if not pts is None:
            self._interactive_contour_points.SetNumberOfPoints(len(pts))
            self._interactive_contour_lines.InsertNextCell(len(pts))
            for i, pt in enumerate(pts):
                self._interactive_contour_points.SetPoint(i, pt[0], pt[1], -0.001)
                self._interactive_contour_lines.InsertCellPoint(i)

        self._interactive_contour_points.Modified()
        self._interactive_contour_lines.Modified()
        self._interactive_contour_poly.Modified()
    #
    def set_voronoi_contours(self, contour_pts):
        self._voronoi_contour_points.Initialize()
        self._voronoi_contour_lines.Initialize()

        for i, pts in enumerate(contour_pts):
            if len(pts) == 0:
                continue

            self._voronoi_contour_lines.InsertNextCell(len(pts)+1)
            start_index = self._voronoi_contour_points.GetNumberOfPoints()
            for id, pt in enumerate(pts):
                self._voronoi_contour_points.InsertNextPoint(pt[0], pt[1], -0.001)
                self._voronoi_contour_lines.InsertCellPoint(id+start_index)
            self._voronoi_contour_lines.InsertCellPoint(start_index)

        self._voronoi_contour_points.Modified()
        self._voronoi_contour_lines.Modified()
        self._voronoi_contour_poly.Modified()
        self.reset_view()
    #
    @property
    def voronoi(self):
        return self._voronoi
    #
    @voronoi.setter
    def voronoi(self, flag):
        self._voronoi = flag
        self.update_voronoi_segments()
    #
    def update_voronoi_segments(self):
        _vor_contours = []
        if self.voronoi and len(self._style._annotations) >= 3:
            clip = SegmentClipper(self.get_image_dimensions())
            annos = [[p[0], p[1]] for p in self._style._annotations] + clip.bnd_points()
            vor = Voronoi(np.array(annos))
            vertices = [(v[0], v[1]) for v in vor.vertices]
            ptis = set()
            for rg in vor.regions:
                if len(rg) < 2: continue
                idx0 = -1
                for idx in rg:
                    if idx >=0 and idx0 >= 0:
                        pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                        ptis.add(pti)
                    idx0 = idx
                idx = rg[0]
                if idx >=0 and idx0 >= 0:
                    pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                    ptis.add(pti)
            #
            for (i0, i1) in ptis:
                pts = clip.clip(vertices[i0], vertices[i1])
                if pts:
                    _vor_contours.append(pts)
        self.set_voronoi_contours(_vor_contours)
