import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       IntProperty, PointerProperty, StringProperty)


def _poll_armature(self, obj):
    return obj.type == 'ARMATURE'


class VMRSettings(bpy.types.PropertyGroup):
    # --- Video input --------------------------------------------------------
    video_path: StringProperty(
        name="Video File", subtype='FILE_PATH',
        description="MP4 (or any OpenCV-readable) reference video")

    model_quality: EnumProperty(
        name="Model", default='heavy',
        items=[('heavy', "Heavy (best)", "Most accurate, slowest"),
               ('full', "Full", "Balanced"),
               ('lite', "Lite", "Fastest, least accurate")],
        description="MediaPipe pose model quality")

    # --- Target -------------------------------------------------------------
    target_armature: PointerProperty(
        name="Armature", type=bpy.types.Object, poll=_poll_armature,
        description="Rigged character that receives the animation")

    preset: EnumProperty(
        name="Rig Preset", default='AUTO',
        items=[('AUTO', "Auto-detect", "Guess mapping from bone names"),
               ('RIGIFY_IK', "Rigify (IK legs)",
                "Rigify controls; feet driven by IK for solid foot plants"),
               ('RIGIFY_FK', "Rigify (FK legs)", "Rigify, all-FK limbs"),
               ('MIXAMO', "Mixamo", "mixamorig: skeletons"),
               ('UE_MANNEQUIN', "Unreal Mannequin", "UE4/UE5 mannequin"),
               ('CUSTOM', "Custom (JSON)",
                "Use the mapping in the text block below")],
        description="Bone-name mapping between detected motion and the rig")

    mapping_text: StringProperty(
        name="Mapping Text", default="VMR_mapping.json",
        description="Name of the text datablock holding a custom JSON "
                    "bone mapping")

    forward_axis: EnumProperty(
        name="Character Forward", default='NEG_Y',
        items=[('NEG_Y', "-Y (Blender default)", ""),
               ('POS_Y', "+Y", ""), ('POS_X', "+X", ""),
               ('NEG_X', "-X", "")],
        description="World axis the character faces in its rest pose")

    # --- Motion settings ----------------------------------------------------
    speed_multiplier: FloatProperty(
        name="Motion Speed", default=1.0, min=0.1, max=5.0,
        description="Playback speed multiplier (2.0 = twice as fast)")

    root_strength: FloatProperty(
        name="Root Motion Strength", default=1.0, min=0.0, max=2.0,
        description="Scale of horizontal root travel; 0 = in place")

    foot_locking: BoolProperty(
        name="Foot Locking", default=True,
        description="Pin feet to the ground during detected contacts")

    smoothing: FloatProperty(
        name="Smoothing Level", default=0.5, min=0.0, max=1.0,
        description="0 = raw and snappy, 1 = heavily smoothed")

    confidence: FloatProperty(
        name="Confidence Threshold", default=0.5, min=0.05, max=0.95,
        description="Landmarks below this visibility are treated as occluded "
                    "and reconstructed")

    start_frame: IntProperty(
        name="Start Frame", default=1,
        description="Scene frame where the animation begins")

    action_name: StringProperty(
        name="Action Name", default="Mocap",
        description="Name for the generated action")

    # --- Status (read-only UI feedback) --------------------------------------
    status: StringProperty(default="Idle")
    progress: FloatProperty(default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    error: StringProperty(default="")
    is_running: BoolProperty(default=False)
    has_take: BoolProperty(default=False)
    take_info: StringProperty(default="")


def register():
    bpy.utils.register_class(VMRSettings)
    bpy.types.Scene.vmr = PointerProperty(type=VMRSettings)


def unregister():
    del bpy.types.Scene.vmr
    bpy.utils.unregister_class(VMRSettings)
