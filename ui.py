import bpy

from . import deps


class VMR_PT_panel(bpy.types.Panel):
    bl_label = "Video Mocap Retarget"
    bl_idname = "VMR_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mocap"

    def draw(self, context):
        s = context.scene.vmr
        layout = self.layout

        if not deps.have_deps():
            box = layout.box()
            box.label(text="AI dependencies not installed", icon='ERROR')
            box.operator("vmr.install_deps", icon='IMPORT')

        # --- Video Input -----------------------------------------------
        box = layout.box()
        box.label(text="Video Input", icon='FILE_MOVIE')
        box.prop(s, "video_path", text="")
        box.prop(s, "model_quality")

        # --- Analysis Controls ------------------------------------------
        box = layout.box()
        box.label(text="Analysis", icon='VIEWZOOM')
        row = box.row()
        row.scale_y = 1.4
        row.operator("vmr.analyze", icon='PLAY')
        row = box.row(align=True)
        row.operator("vmr.save_take", text="Save", icon='FILE_TICK')
        row.operator("vmr.load_take", text="Load", icon='FILE_FOLDER')
        if s.take_info:
            box.label(text=s.take_info, icon='CHECKMARK')

        # --- Target ------------------------------------------------------
        box = layout.box()
        box.label(text="Target Rig", icon='ARMATURE_DATA')
        box.prop(s, "target_armature", text="")
        box.prop(s, "preset")
        if s.preset == 'CUSTOM':
            box.prop(s, "mapping_text", text="Text Block")
        box.operator("vmr.export_mapping", icon='TEXT')
        box.prop(s, "forward_axis")

        # --- Animation Controls -------------------------------------------
        box = layout.box()
        box.label(text="Animation", icon='ACTION')
        row = box.row()
        row.scale_y = 1.4
        row.operator("vmr.apply", icon='ARMATURE_DATA')
        box.operator("vmr.undo_apply", icon='LOOP_BACK')
        row = box.row(align=True)
        row.prop(s, "start_frame")
        row.prop(s, "action_name", text="")

        # --- Motion Settings ------------------------------------------------
        box = layout.box()
        box.label(text="Motion Settings", icon='PREFERENCES')
        col = box.column(align=True)
        col.prop(s, "speed_multiplier")
        col.prop(s, "root_strength")
        col.prop(s, "smoothing")
        col.prop(s, "confidence")
        box.prop(s, "foot_locking")

        # --- Status ----------------------------------------------------------
        box = layout.box()
        box.label(text="Status", icon='INFO')
        if s.is_running:
            box.prop(s, "progress", text="Progress")
        col = box.column()
        col.scale_y = 0.8
        for chunk in _wrap(s.status, 38):
            col.label(text=chunk)
        if s.error:
            for chunk in _wrap("Error: " + s.error, 38):
                col.label(text=chunk, icon='ERROR')


def _wrap(text, width):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out or [""]


def register():
    bpy.utils.register_class(VMR_PT_panel)


def unregister():
    bpy.utils.unregister_class(VMR_PT_panel)
