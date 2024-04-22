'''
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


bl_info = {
    "name": "Multi-Mesh Slicer",
    "description": "Allows you to slice selected objects in parts base on the bound box",
    "author": "haseeb295",
    "version": (0, 0, 1),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > Multi-Mesh Slicer",
    "warning": "This addon is still in development.",
    "category": "Object",
    "tracker_url":"https://github.com/haseebahmed295/Multi-Mesh-Slicer/issues"
}

import bpy
import bmesh
from mathutils import Vector
import inspect
import sys

def get_classes():
    current_module = sys.modules[__name__]
    classes = []
    for name, obj in inspect.getmembers(current_module):
        if inspect.isclass(obj) and obj.__module__ == __name__:
            classes.append(obj)
    return classes

class Cutter(bpy.types.Operator):
    bl_idname = "object.multi_object_slicer"
    bl_label = "Slicer"
    bl_description = "slice selected objects in parts based on the bound box"
    bl_options = {"REGISTER"}
    bl_info = {'UNDO': False}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        selected_obj = list(bpy.context.selected_objects)
        other_obj = {}
        for obj in bpy.data.objects:
            if not obj.type == 'MESH' or obj not in selected_obj:
                other_obj[obj] = obj.hide_viewport
                obj.hide_viewport = True

        bounding_box_name = "Block_Bound_L"
        # Create a new mesh object
        mesh = bpy.data.meshes.new(name=bounding_box_name)
        bound_obj = bpy.data.objects.new(bounding_box_name, mesh)
        x_cuts = context.scene.x_Cuts+1
        y_cuts = context.scene.y_Cuts+1
        z_cuts = context.scene.z_Cuts+1
        # Link it to the scene
        scene = bpy.context.scene
        scene.collection.objects.link(bound_obj)

        # Get all the meshes in the scene
        meshes = [o for o in selected_obj]

        # Calculate the min and max coordinates for the bounding box
        min_coord = Vector((min((o.matrix_world @ Vector(b)).xyz[i] for o in meshes for b in o.bound_box) for i in range(3)))
        max_coord = Vector((max((o.matrix_world @ Vector(b)).xyz[i] for o in meshes for b in o.bound_box) for i in range(3)))

        # Create the bounding box
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1)
        scale = max_coord - min_coord
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
        bmesh.ops.translate(bm, vec=min_coord + scale / 2, verts=bm.verts)
        bm.to_mesh(mesh)
        bm.free()

        bpy.context.view_layer.objects.active = bound_obj

        x1, x2, y1, y2, z1, z2 = min_coord[0], max_coord[0], min_coord[1], max_coord[1], min_coord[2], max_coord[2]

        x_points = self.find_division_point_x(x1, x2, obj.location[1], obj.location[2], self.find_pairs_summing_to(x_cuts))
        y_points = self.find_division_point_y(obj.location[0], y1, y2, obj.location[2], self.find_pairs_summing_to(y_cuts))
        z_points = self.find_division_point_z(obj.location[0], obj.location[1], z1, z2, self.find_pairs_summing_to(z_cuts))

        if context.scene.preserve_normals:
            normal_objs = []
            bpy.ops.object.select_all(action='DESELECT')
            for obj in selected_obj:
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.duplicate()
                    normal_objs.append(bpy.context.object)
                    modifier = obj.modifiers.new("Slicer Normal","DATA_TRANSFER")
                    modifier.object = bpy.context.object
                    modifier.use_loop_data = True
                    modifier.data_types_loops = {'CUSTOM_NORMAL'}
                    bpy.context.object.hide_viewport = True
                    bpy.ops.object.select_all(action='DESELECT')

        bpy.context.view_layer.objects.active = bound_obj


        for p in x_points:
            self.select_ob()
            self.slice_mesh(point=p, plane=(1, 0, 0))
            self.delete_empty_ob()
        for p in y_points:
            self.select_ob()
            self.slice_mesh(point=p, plane=(0, 1, 0))
            self.delete_empty_ob()
        for p in z_points:
            self.select_ob()
            self.slice_mesh(point=p, plane=(0, 0, 1))
            self.delete_empty_ob()

        if context.scene.preserve_normals:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in bpy.context.visible_objects:
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                for modifier in obj.modifiers:
                    if modifier.name== 'Slicer Normal':
                        bpy.ops.object.modifier_apply(modifier=modifier.name)
                bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.select_all(action='DESELECT')
            for obj in normal_objs:
                obj.hide_viewport = False
                obj.select_set(True)
            bpy.ops.object.delete()

        self.del_bound_box(bounding_box_name)
        for obj in other_obj:
            obj.hide_viewport = other_obj[obj]

        bpy.context.view_layer.objects.active = bpy.data.objects[0]
        bpy.data.objects[0].select_set(True)
        return {"FINISHED"}


    def del_bound_box(self,n_box):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if n_box in obj.name:
                obj.select_set(True)
        bpy.ops.object.delete()
        
    def delete_empty_ob(self):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
        # Check if the object is of type 'MESH' and has no geometry
            if obj.type == 'MESH':
                if not list(obj.data.vertices):
                # Select the empty object
                    obj.select_set(True)
        bpy.ops.object.delete(use_global=False, confirm=False)
    def select_ob(self):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                obj.select_set(True)

    def find_division_point_x(self , x1,x2, y,z, pairs):
        # Calculate the x and y coordinates of the division point
        points = []
        for pair in pairs:
            n= pair[0]
            m= pair[1]
            x = ((n * x1) + (m * x2)) / (m + n)
            points.append((x,y,z))
        return points
    def find_division_point_y(self , x,y1,y2,z,pairs):
        # Calculate the x and y coordinates of the division point
        points = []
        for pair in pairs:
            n= pair[0]
            m= pair[1]
            y = ((n * y1) + (m * y2)) / (m + n)
            points.append((x,y,z))
        return points
    def find_division_point_z(self , x , y , z1,z2,pairs):
        # Calculate the x and y coordinates of the division point
        points = []
        for pair in pairs:
            n= pair[0]
            m= pair[1]
            z = ((n * z1) + (m * z2)) / (m + n)
            points.append((x,y,z))
        return points
    def find_pairs_summing_to(self , target):
        # Initialize an empty list to store the pairs
        pairs = []
        
        # Iterate through all possible pairs of numbers up to the target
        for i in range(1, target):
            for j in range(i, target):
                # Check if the sum of the current pair equals the target
                if i + j == target:
                    # If it does, add the pair to the list
                    pairs.append([i, j])
                    # Check if the reverse proportional pair is not already in the list
                    if [j, i] not in pairs:
                        # If it's not, add the reverse proportional pair
                        pairs.append([j, i])
        
        return pairs

    def slice_mesh(self , point = (0,0,0) , plane  = (0, 0, 1)):
        ob = bpy.context.object
        selected_ob = bpy.context.selected_objects
        bpy.ops.object.duplicate()
        new_object = bpy.context.active_object
        new_slelected_objects = bpy.context.selected_objects
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.bisect(plane_co=point, plane_no=plane, flip=False , clear_inner=True , clear_outer=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = ob
        for objec in selected_ob:
            objec.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.bisect(plane_co=point, plane_no=plane, flip=False , clear_inner=False , clear_outer=True)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        return list(new_slelected_objects)
    

class Cutter_Panel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_tools_cutter"
    bl_label = "Slicer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category ="Slicer"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "x_Cuts")
        layout.prop(context.scene, "y_Cuts")
        layout.prop(context.scene, "z_Cuts")
        layout.prop(context.scene, "preserve_normals")
        layout.operator(Cutter.bl_idname , text = "Slice")


def register():
    bpy.types.Scene.x_Cuts = bpy.props.IntProperty(name ="X Cuts" , default=1)
    bpy.types.Scene.y_Cuts = bpy.props.IntProperty(name ="Y Cuts" , default=1)
    bpy.types.Scene.z_Cuts = bpy.props.IntProperty(name ="Z Cuts" , default=1)
    bpy.types.Scene.preserve_normals = bpy.props.BoolProperty(name ="Preserve Normals" , default=True)
    for cls in get_classes():
        bpy.utils.register_class(cls)
    
def unregister():
    for cls in get_classes():
        bpy.utils.unregister_class(cls)
    
if __name__ == "__main__":
    register()
    





